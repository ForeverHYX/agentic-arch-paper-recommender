"""TLDR enrichment for recommendation payloads."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from paper_recommender.llm_errors import LLMProviderError, format_llm_error


DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_USER_AGENT = "agentic-arch-paper-recommender/1.0"
TLDR_MAX_ATTEMPTS = 3
SECTION_LABELS = {
    "agentic_architecture": "agentic architecture and automated design-space exploration",
    "full_stack_codesign": "full-stack hardware/software co-design",
    "microarchitecture_simulators": "CPU/GPU microarchitecture and simulators",
    "hpc_cross_over": "HPC, compiler, and runtime co-design",
}


def fallback_tldr(item: dict[str, Any], max_chars: int = 520) -> str:
    if _is_repository_item(item):
        return _fallback_repository_tldr(item, max_chars=max_chars)
    topic = _topic_hint(item)
    relevance = _relevance_reason(item)
    text = (
        f"Problem: The model did not return a usable TLDR, so the local fallback can only infer that this item may fit {topic}. "
        "Method: To avoid inventing details, the fallback does not restate claims beyond the available metadata; open the paper to inspect the method, system design, and experiments. "
        "Finding: Without model output, the contribution and empirical results cannot be summarized reliably. "
        f"Why it matters: {relevance}"
    )
    return " ".join(text.split())


def request_tldr(
    item: dict[str, Any],
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    opener: Callable[[Request], Any] = urlopen,
    timeout: int = 180,
    retry_short_output: bool = False,
    previous_tldr: str = "",
) -> str:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    system_prompt = _system_prompt_for_item(item)
    if retry_short_output:
        system_prompt += (
            " The previous output was too short. Rewrite it as four complete English sentences, "
            "with at least 120 words in total. Do not use bullets, headings, or Markdown."
        )
    user_prompt = _user_prompt_for_item(item)
    if previous_tldr:
        user_prompt += f"\nPrevious short TLDR to replace: {_truncate(previous_tldr, 180)}"
    body = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 8192,
        "thinking": {"type": "disabled"},
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
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
            "User-Agent": DEFAULT_USER_AGENT,
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
    require_api: bool = False,
) -> dict[str, Any]:
    enriched = dict(payload)
    recommendations = []
    for item in payload.get("recommendations", []):
        updated = dict(item)
        if not updated.get("tldr"):
            updated["tldr"] = _safe_tldr(
                updated,
                api_key=api_key,
                base_url=base_url,
                model=model,
                opener=opener,
                require_api=require_api,
            )
        recommendations.append(updated)
    enriched["recommendations"] = recommendations
    return enriched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="为推荐 JSON 补充 TLDR 解读。")
    parser.add_argument("--input", required=True, help="输入推荐 JSON 路径。")
    parser.add_argument("--output", required=True, help="输出推荐 JSON 路径。")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--require-api", action="store_true", help="API 已配置时调用失败则退出，不使用本地兜底。")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    enriched = enrich_payload_with_tldrs(
        payload,
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url=args.base_url,
        model=args.model,
        require_api=args.require_api,
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
    require_api: bool = False,
) -> str:
    if not api_key:
        if require_api:
            raise LLMProviderError(
                format_llm_error(
                    RuntimeError("OPENAI_API_KEY is not configured"),
                    base_url=base_url,
                    model=model,
                )
            )
        return fallback_tldr(item)
    last_quality_error: ValueError | None = None
    try:
        previous_tldr = ""
        for attempt in range(TLDR_MAX_ATTEMPTS):
            tldr = request_tldr(
                item,
                api_key=api_key,
                base_url=base_url,
                model=model,
                opener=opener,
                retry_short_output=attempt > 0,
                previous_tldr=previous_tldr,
            )
            if _is_usable_tldr(tldr):
                return tldr
            previous_tldr = tldr
            last_quality_error = _tldr_quality_error(tldr)
        raise last_quality_error or ValueError("TLDR is too short or not usable")
    except Exception as exc:
        if require_api:
            raise LLMProviderError(format_llm_error(exc, base_url=base_url, model=model, api_key=api_key)) from exc
        return fallback_tldr(item)


def _is_usable_tldr(text: str) -> bool:
    normalized = " ".join(str(text).split())
    if len(normalized) < 120:
        return False
    words = normalized.split()
    return len(words) >= 18


def _tldr_quality_error(text: str) -> ValueError:
    normalized = " ".join(str(text).split())
    words = normalized.split()
    return ValueError(f"TLDR is too short or not usable: chars={len(normalized)}, words={len(words)}")


def _topic_hint(item: dict[str, Any]) -> str:
    sections = [str(value) for value in item.get("sections", []) if str(value)]
    labels = [SECTION_LABELS.get(section, "") for section in sections]
    labels = [label for label in labels if label]
    if labels:
        return " and ".join(labels[:2])
    categories = [str(value) for value in item.get("categories", []) if str(value)]
    if categories:
        return " or ".join(categories[:2]) + " related architecture work"
    return "computer architecture or a related systems direction"


def _relevance_reason(item: dict[str, Any]) -> str:
    sections = [str(value) for value in item.get("sections", []) if str(value)]
    labels = [SECTION_LABELS.get(section, section) for section in sections]
    categories = [str(value) for value in item.get("categories", []) if str(value)]
    if labels:
        return "It matches " + " and ".join(labels[:2]) + ", so it is worth a closer relevance check."
    if categories:
        return "It appears under " + " and ".join(categories[:2]) + ", making it useful for exploratory triage."
    return "It came from the current candidate pool and is useful for exploratory triage."


def _is_repository_item(item: dict[str, Any]) -> bool:
    return str(item.get("item_type", "")).strip().lower() == "repository"


def _fallback_repository_tldr(item: dict[str, Any], max_chars: int = 520) -> str:
    stars_today = int(item.get("repository_stars_today") or 0)
    trend = f"about {stars_today} stars today" if stars_today else "it appeared in GitHub Trending"
    paper_links = _paper_links_text(item.get("paper_links") or [])
    paper_text = f"the parsed paper links include {paper_links}" if paper_links else "no explicit paper link was parsed from the README"
    text = (
        f"Problem: This repository may implement an open-source system or tool related to the current research profile, and {trend}. "
        "Method: The fallback only uses the repository description, README snippets, topics, and language, without inventing unpublished design details. "
        f"Finding: {paper_text}. "
        "Why it matters: It matches architecture, hardware/software co-design, simulator, or HPC interests, so its README, examples, and paper links are worth checking first."
    )
    return " ".join(text.split())


def _system_prompt_for_item(item: dict[str, Any]) -> str:
    if _is_repository_item(item):
        return (
            "Write an English TLDR for a GitHub repository for a computer architecture researcher. "
            "Return the final answer only; do not explain. "
            "Write four complete sentences covering what it implements, why it relates to agentic architecture "
            "or hardware/software co-design, its star trend, and any original paper links. "
            "Do not invent information absent from the README or repository metadata; preserve system names, tool names, and acronyms."
        )
    return (
        "Write an English TLDR for a computer architecture researcher. "
        "Return the final answer only; do not explain. "
        "Write four complete sentences covering Problem, Method, Finding or experimental evidence, and Why it matters. "
        "If the abstract does not report experimental results, say that the abstract does not disclose them. "
        "Do not translate sentence by sentence; preserve system names, tool names, and acronyms."
    )


def _user_prompt_for_item(item: dict[str, Any]) -> str:
    prompt = (
        f"Title: {item.get('title', '')}\n"
        f"Abstract: {item.get('abstract', '')}\n"
        f"Categories: {', '.join(str(value) for value in item.get('categories', []))}"
    )
    if not _is_repository_item(item):
        return prompt
    return "\n".join(
        [
            prompt,
            f"Repository URL: {item.get('repository_url') or item.get('url', '')}",
            f"Stars today: {item.get('repository_stars_today', 0)}",
            f"Total stars: {item.get('repository_stars', 0)}",
            f"Forks: {item.get('repository_forks', 0)}",
            f"Language: {item.get('repository_language', '')}",
            f"Topics: {', '.join(str(value) for value in item.get('repository_topics', []))}",
            f"Original paper links: {_paper_links_text(item.get('paper_links') or [])}",
        ]
    )


def _paper_links_text(links: list[Any]) -> str:
    parts = []
    for link in links:
        if isinstance(link, dict):
            url = str(link.get("url", "")).strip()
            label = str(link.get("label", "Paper")).strip() or "Paper"
        else:
            url = str(link).strip()
            label = "Paper"
        if url:
            parts.append(f"{label} {url}")
    return ", ".join(parts)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


if __name__ == "__main__":
    raise SystemExit(main())
