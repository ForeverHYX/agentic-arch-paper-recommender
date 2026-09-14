"""TLDR enrichment for recommendation payloads."""

from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from paper_recommender.llm_errors import LLMProviderError, format_llm_error
from paper_recommender.llm_config import DEFAULT_BASE_URL, DEFAULT_MODEL, api_key, base_url, model
from paper_recommender.llm_retry import call_with_transient_retries


DEFAULT_USER_AGENT = "agentic-arch-paper-recommender/1.0"
TLDR_MAX_ATTEMPTS = 2
SUMMARY_LLM_RETRY_ATTEMPTS = 3
KEY_POINT_LABELS = ("Problem", "Method", "Evidence", "Impact", "Limitation")
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
    return request_paper_summary(
        item,
        api_key=api_key,
        base_url=base_url,
        model=model,
        opener=opener,
        timeout=timeout,
        retry_short_output=retry_short_output,
        previous_tldr=previous_tldr,
    )["tldr"]


def request_paper_summary(
    item: dict[str, Any],
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    opener: Callable[[Request], Any] = urlopen,
    timeout: int = 180,
    retry_short_output: bool = False,
    previous_tldr: str = "",
) -> dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    system_prompt = _system_prompt_for_item(item)
    if retry_short_output:
        system_prompt += (
            " The previous output was too thin. Rewrite it with a complete headline, "
            "at least three key_points with distinct labels, and a key_figure when the paper has one. "
            "Keep the JSON schema unchanged."
        )
    user_prompt = _user_prompt_for_item(item)
    structure = extract_paper_structure(item, opener=opener)
    if structure["sections"] or structure["figures"]:
        user_prompt += "\nPaper structure extracted from the public HTML copy:\n" + json.dumps(structure, ensure_ascii=False)
    if previous_tldr:
        user_prompt += f"\nPrevious thin brief to replace: {_truncate(previous_tldr, 180)}"
    body = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 1500,
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
    return _parse_paper_summary(content)


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
        if (
            not updated.get("tldr")
            or "key_points" not in updated
            or "section_summaries" not in updated
            or "figure_explanations" not in updated
        ):
            summary = _safe_summary(
                updated,
                api_key=api_key,
                base_url=base_url,
                model=model,
                opener=opener,
                require_api=require_api,
            )
            updated.update(summary)
        recommendations.append(updated)
    enriched["recommendations"] = recommendations
    return enriched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="为推荐 JSON 补充 TLDR 解读。")
    parser.add_argument("--input", required=True, help="输入推荐 JSON 路径。")
    parser.add_argument("--output", required=True, help="输出推荐 JSON 路径。")
    parser.add_argument("--base-url", default=base_url())
    parser.add_argument("--model", default=model())
    parser.add_argument("--require-api", action="store_true", help="API 已配置时调用失败则退出，不使用本地兜底。")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    enriched = enrich_payload_with_tldrs(
        payload,
        api_key=api_key(),
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
    return _safe_summary(item, api_key, base_url, model, opener, require_api)["tldr"]


def _safe_summary(
    item: dict[str, Any],
    api_key: str,
    base_url: str,
    model: str,
    opener: Callable[[Request], Any],
    require_api: bool = False,
) -> dict[str, Any]:
    if not api_key:
        if require_api:
            raise LLMProviderError(
                format_llm_error(
                    RuntimeError("DEEPSEEK_API_KEY is not configured"),
                    base_url=base_url,
                    model=model,
                )
            )
        return _fallback_summary(item, extract_paper_structure(item, opener=opener))
    last_quality_error: ValueError | None = None
    try:
        previous_tldr = ""
        for attempt in range(TLDR_MAX_ATTEMPTS):
            summary = call_with_transient_retries(
                lambda: request_paper_summary(
                    item,
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    opener=opener,
                    retry_short_output=attempt > 0,
                    previous_tldr=previous_tldr,
                ),
                attempts=SUMMARY_LLM_RETRY_ATTEMPTS,
                on_retry=lambda error, delay, retry_attempt: print(
                    f"LLM summary request failed ({error}); retrying in {delay:g}s "
                    f"({retry_attempt}/{SUMMARY_LLM_RETRY_ATTEMPTS})"
                ),
            )
            if _is_usable_summary(summary):
                return summary
            previous_tldr = summary.get("tldr", "")
            last_quality_error = _summary_quality_error(summary)
        raise last_quality_error or ValueError("summary brief is too thin")
    except Exception as exc:
        if require_api:
            raise LLMProviderError(format_llm_error(exc, base_url=base_url, model=model, api_key=api_key)) from exc
        return _fallback_summary(item, extract_paper_structure(item, opener=opener))


def _parse_paper_summary(content: Any) -> dict[str, Any]:
    raw = str(content).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = {"tldr": raw}
    if not isinstance(value, dict):
        value = {"tldr": raw}
    headline = _short_text(value.get("headline", ""), 240)
    key_points = []
    for entry in value.get("key_points", []) if isinstance(value.get("key_points", []), list) else []:
        if isinstance(entry, dict) and str(entry.get("text", "")).strip():
            label = _short_text(entry.get("label", "Note"), 40)
            key_points.append({"label": label, "text": _short_text(entry["text"], 360)})
    sections = []
    for entry in value.get("sections", []) if isinstance(value.get("sections", []), list) else []:
        if isinstance(entry, dict) and str(entry.get("title", "")).strip() and str(entry.get("summary", "")).strip():
            sections.append({"title": _short_text(entry["title"], 120), "summary": _short_text(entry["summary"], 360)})
    figures = []
    for entry in value.get("figures", []) if isinstance(value.get("figures", []), list) else []:
        if isinstance(entry, dict) and str(entry.get("caption", "")).strip():
            figures.append({"label": _short_text(entry.get("label", "Figure"), 80), "caption": _short_text(entry["caption"], 240), "explanation": _short_text(entry.get("explanation", ""), 360)})
    key_figure = {}
    raw_key_figure = value.get("key_figure")
    if isinstance(raw_key_figure, dict) and (
        str(raw_key_figure.get("caption", "")).strip() or str(raw_key_figure.get("explanation", "")).strip()
    ):
        key_figure = {
            "label": _short_text(raw_key_figure.get("label", "Figure"), 80),
            "caption": _short_text(raw_key_figure.get("caption", ""), 240),
            "explanation": _short_text(raw_key_figure.get("explanation", ""), 360),
        }
    legacy_tldr = " ".join(str(value.get("tldr", "")).split())
    tldr = _derive_tldr(headline, key_points) or legacy_tldr
    return {
        "tldr": tldr,
        "headline": headline,
        "key_points": key_points[:5],
        "key_figure": key_figure,
        "section_summaries": sections[:6],
        "figure_explanations": figures[:6],
    }


def _derive_tldr(headline: str, key_points: list[dict[str, Any]]) -> str:
    if not headline:
        return ""
    parts = [headline] + [str(point.get("text", "")) for point in key_points[:3]]
    return " ".join(" ".join(parts).split())


def _is_usable_summary(summary: dict[str, Any]) -> bool:
    headline = str(summary.get("headline", "")).strip()
    key_points = [
        point
        for point in summary.get("key_points", [])
        if isinstance(point, dict) and str(point.get("text", "")).strip()
    ]
    return len(headline) >= 30 and len(key_points) >= 3


def _summary_quality_error(summary: dict[str, Any]) -> ValueError:
    headline = str(summary.get("headline", "")).strip()
    key_points = summary.get("key_points", [])
    return ValueError(
        "summary brief is too thin: "
        f"headline_chars={len(headline)}, key_points={len(key_points)}"
    )


def _fallback_summary(item: dict[str, Any], structure: dict[str, Any]) -> dict[str, Any]:
    result = {
        "tldr": fallback_tldr(item),
        "headline": _fallback_headline(item),
        "key_points": _fallback_key_points(item),
        "key_figure": {},
        "section_summaries": [],
        "figure_explanations": [],
    }
    figures = structure.get("figures", [])
    if figures:
        first = figures[0]
        result["key_figure"] = {
            "label": first.get("label", "Figure"),
            "caption": first.get("caption", ""),
            "explanation": "No model explanation available; read the caption together with the paper.",
        }
    for title in structure.get("sections", [])[:6]:
        result["section_summaries"].append({"title": title, "summary": "未启用模型，暂无该段落的可靠摘要；请打开原文查看。"})
    for figure in structure.get("figures", [])[:6]:
        result["figure_explanations"].append({"label": figure.get("label", "Figure"), "caption": figure.get("caption", ""), "explanation": "未启用模型，暂无图表解读；请结合图注和正文查看。"})
    return result


def _fallback_headline(item: dict[str, Any]) -> str:
    title = _short_text(item.get("title", ""), 200)
    topic = _topic_hint(item)
    return (
        f'Model brief unavailable: "{title}" may fit {topic}; '
        "open the paper to verify its actual contribution."
    )


def _fallback_key_points(item: dict[str, Any]) -> list[dict[str, str]]:
    relevance = _relevance_reason(item)
    return [
        {
            "label": "Problem",
            "text": "Without the model brief, the specific problem can only be inferred from the title and metadata.",
        },
        {
            "label": "Method",
            "text": "The fallback avoids inventing details; open the paper to inspect the method and system design.",
        },
        {
            "label": "Impact",
            "text": relevance,
        },
    ]


class _StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current_tag = ""
        self.buffer: list[str] = []
        self.sections: list[str] = []
        self.figures: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        if normalized in {"h2", "h3", "h4", "figcaption", "caption"}:
            self.current_tag = normalized
            self.buffer = []

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized != self.current_tag:
            return
        text = " ".join("".join(self.buffer).split())
        if normalized in {"h2", "h3", "h4"} and text and len(self.sections) < 8:
            self.sections.append(text[:120])
        if normalized in {"figcaption", "caption"} and text and len(self.figures) < 8:
            self.figures.append({"label": "Figure", "caption": text[:240]})
        self.current_tag = ""
        self.buffer = []

    def handle_data(self, data: str) -> None:
        if self.current_tag:
            self.buffer.append(data)


def extract_paper_structure(item: dict[str, Any], opener: Callable[[Request], Any] = urlopen) -> dict[str, Any]:
    if _is_repository_item(item):
        return {"sections": [], "figures": []}
    paper_id = str(item.get("paper_id", "")).strip()
    if not paper_id or not any(char.isdigit() for char in paper_id):
        return {"sections": [], "figures": []}
    request = Request(f"https://ar5iv.labs.arxiv.org/html/{paper_id}", headers={"User-Agent": DEFAULT_USER_AGENT})
    try:
        response_context = opener(request, timeout=20)
    except Exception:
        try:
            response_context = opener(request)
        except Exception:
            return {"sections": [], "figures": []}
    try:
        with response_context as response:
            try:
                raw = response.read(600_000)
            except TypeError:
                raw = response.read()
            html = raw.decode("utf-8", errors="replace")
    except Exception:
        return {"sections": [], "figures": []}
    parser = _StructureParser()
    try:
        parser.feed(html)
    except Exception:
        return {"sections": [], "figures": []}
    return {"sections": parser.sections, "figures": parser.figures}


def _short_text(value: Any, max_chars: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


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
            "Write a quick-read brief in English for a GitHub repository, for a computer architecture researcher. "
            "Return only valid JSON with keys headline, key_points, sections, key_figure, figures. "
            "headline: one sentence stating what the repository implements and why it matters (max 30 words). "
            "key_points: 3-5 objects with label (one of Problem, Method, Evidence, Impact, Limitation) and text; "
            "Evidence should cover the star trend and original paper links. "
            "sections and figures must be empty arrays and key_figure must be null. "
            "Do not invent information absent from the README or repository metadata; preserve system names, tool names, and acronyms."
        )
    return (
        "Write a quick-read brief in English for a computer architecture researcher who wants to grasp the paper fast. "
        "Return only valid JSON with keys headline, key_points, sections, key_figure, figures. "
        "headline: one sentence stating the paper's core contribution or result (max 30 words). "
        "key_points: array of 3-5 objects, each with label (one of Problem, Method, Evidence, Impact, Limitation) "
        "and a single concise sentence of text. Evidence states what experiments or results are reported; "
        "if the abstract discloses none, say that explicitly. "
        "key_figure: the single figure or table that best carries the paper's message, "
        "as an object with label, caption, and a one-sentence explanation of what it shows; null if none is evident. "
        "sections: array of up to 6 objects with title and concise summary for deep reading. "
        "figures: array of up to 6 objects with label, caption, and a concise explanation of what the chart/diagram shows. "
        "Do not invent details beyond the abstract and extracted structure; preserve system names, tool names, and acronyms."
    )


def _user_prompt_for_item(item: dict[str, Any]) -> str:
    prompt = (
        f"Title: {item.get('title', '')}\n"
        f"Abstract: {item.get('abstract', '')}\n"
        f"Paper URL: {item.get('url', '')}\n"
        f"PDF URL: {item.get('pdf_url', '')}\n"
        f"Recommendation sections: {', '.join(str(value) for value in item.get('sections', []))}\n"
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
