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


def fallback_tldr(item: dict[str, Any], max_chars: int = 520) -> str:
    title = str(item.get("title", "")).strip()
    abstract = str(item.get("abstract", "")).strip()
    normalized = " ".join(abstract.split())
    sentences = _abstract_sentences(normalized)
    problem = sentences[0] if sentences else title or "论文摘要信息不足"
    method = sentences[1] if len(sentences) > 1 else problem
    conclusion = sentences[-1] if len(sentences) > 2 else method
    relevance = _relevance_reason(item)
    text = (
        f"研究问题：这篇论文关注 {problem} "
        f"核心方法：作者的主要做法是 {method} "
        f"关键结论：摘要显示 {conclusion} "
        f"推荐理由：{relevance}"
    )
    return _truncate(" ".join(text.split()), max_chars=max_chars)


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
        "max_tokens": 480,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你为一名计算机体系结构研究者解读 arXiv 论文。"
                    "请只使用简体中文写 4 句较长 TLDR，约 180-260 个汉字；"
                    "必须依次覆盖：研究问题、核心方法、关键结论或实验发现、推荐理由。"
                    "不要只复述标题，不要逐句翻译摘要，不要粘贴英文原句。"
                    "必要的系统名、工具名、术语和缩写可以保留英文原名。"
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
    parser = argparse.ArgumentParser(description="为推荐 JSON 补充 TLDR 解读。")
    parser.add_argument("--input", required=True, help="输入推荐 JSON 路径。")
    parser.add_argument("--output", required=True, help="输出推荐 JSON 路径。")
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
    print(f"已为 {len(enriched.get('recommendations', []))} 条推荐补充 TLDR")
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
        tldr = request_tldr(item, api_key=api_key, base_url=base_url, model=model, opener=opener)
        return tldr or fallback_tldr(item)
    except Exception:
        return fallback_tldr(item)


def _abstract_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = []
    for part in text.replace("?", ".").replace("!", ".").split("."):
        cleaned = part.strip(" ;:\n\t")
        if cleaned:
            parts.append(cleaned)
    return parts


def _relevance_reason(item: dict[str, Any]) -> str:
    sections = [str(value) for value in item.get("sections", []) if str(value)]
    positives = [str(value).split(":", 1)[-1] for value in item.get("positive_matches", []) if str(value)]
    categories = [str(value) for value in item.get("categories", []) if str(value)]
    clues = positives[:3] or sections[:2] or categories[:2]
    if clues:
        return "它命中 " + "、".join(clues) + " 等兴趣信号，适合进一步判断是否值得精读。"
    return "它来自当前候选池，适合作为探索性论文快速筛查。"


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


if __name__ == "__main__":
    raise SystemExit(main())
