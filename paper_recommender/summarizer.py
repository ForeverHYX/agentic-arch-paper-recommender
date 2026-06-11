"""TLDR enrichment for recommendation payloads."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_MODEL = "deepseek-v4-flash"


def fallback_tldr(item: dict[str, Any], max_chars: int = 180) -> str:
    title = str(item.get("title", "")).strip()
    abstract = str(item.get("abstract", "")).strip()
    text = f"{title}: {abstract}" if title and abstract else title or abstract
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def request_tldr(
    item: dict[str, Any],
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    opener: Callable[[Request], Any] = urlopen,
    timeout: int = 45,
) -> str:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    body = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 120,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You summarize arXiv papers for a computer architecture researcher. "
                    "Write one concise Simplified Chinese TLDR, at most 45 Chinese characters. "
                    "Focus on method, system, architecture insight, or evaluation angle."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Title: {item.get('title', '')}\n"
                    f"Abstract: {item.get('abstract', '')}\n"
                    f"Categories: {', '.join(str(value) for value in item.get('categories', []))}"
                ),
            },
        ],
    }
    request = Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        response_context = opener(request, timeout=timeout)
    except TypeError:
        response_context = opener(request)
    with response_context as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = payload["choices"][0]["message"]["content"]
    return " ".join(str(content).split())


def enrich_payload_with_tldrs(
    payload: dict[str, Any],
    api_key: str = "",
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    opener: Callable[[Request], Any] = urlopen,
) -> dict[str, Any]:
    enriched = dict(payload)
    recommendations = []
    for item in payload.get("recommendations", []):
        updated = dict(item)
        if not updated.get("tldr"):
            updated["tldr"] = _safe_tldr(updated, api_key=api_key, base_url=base_url, model=model, opener=opener)
        recommendations.append(updated)
    enriched["recommendations"] = recommendations
    return enriched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enrich recommendation JSON with TLDR summaries.")
    parser.add_argument("--input", required=True, help="Input recommendation JSON path.")
    parser.add_argument("--output", required=True, help="Output recommendation JSON path.")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    enriched = enrich_payload_with_tldrs(
        payload,
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url=args.base_url,
        model=args.model,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Enriched {len(enriched.get('recommendations', []))} recommendations with TLDRs")
    return 0


def _safe_tldr(
    item: dict[str, Any],
    api_key: str,
    base_url: str,
    model: str,
    opener: Callable[[Request], Any],
) -> str:
    if not api_key:
        return fallback_tldr(item)
    try:
        return request_tldr(item, api_key=api_key, base_url=base_url, model=model, opener=opener)
    except Exception:
        return fallback_tldr(item)


if __name__ == "__main__":
    raise SystemExit(main())
