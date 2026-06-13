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
SECTION_LABELS = {
    "agentic_architecture": "Agentic 架构与自动设计空间探索",
    "full_stack_codesign": "全栈软硬件协同设计",
    "microarchitecture_simulators": "CPU/GPU 微架构与模拟器",
    "hpc_cross_over": "HPC、编译器与运行时交叉方向",
}


def fallback_tldr(item: dict[str, Any], max_chars: int = 520) -> str:
    topic = _topic_hint(item)
    relevance = _relevance_reason(item)
    text = (
        f"研究问题：模型没有生成可用中文解读，本地只能根据分类和命中信号判断它可能属于{topic}。"
        "核心方法：为避免误导，本地兜底不会复述英文摘要；需要打开论文原文确认方法、系统设计和实验设置。"
        "关键结论：缺少模型输出时无法可靠提炼贡献和实验发现，应以论文 PDF 和作者摘要为准。"
        f"推荐理由：{relevance}"
    )
    return _truncate(" ".join(text.split()), max_chars=max_chars)


def request_tldr(
    item: dict[str, Any],
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    opener: Callable[[Request], Any] = urlopen,
    timeout: int = 180,
) -> str:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    body = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 8192,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你为计算机体系结构研究者写简体中文 TLDR。"
                    "只输出最终答案，不要解释。"
                    "写 4 句，总计 180-260 个汉字，覆盖研究问题、核心方法、关键结论或实验发现、推荐理由。"
                    "不要逐句翻译摘要；系统名、工具名和缩写可以保留英文。"
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
    try:
        tldr = request_tldr(item, api_key=api_key, base_url=base_url, model=model, opener=opener)
        if _is_usable_tldr(tldr):
            return tldr
        raise ValueError("模型返回的 TLDR 过短或不是中文")
    except Exception as exc:
        if require_api:
            raise LLMProviderError(format_llm_error(exc, base_url=base_url, model=model, api_key=api_key)) from exc
        return fallback_tldr(item)


def _is_usable_tldr(text: str) -> bool:
    normalized = " ".join(str(text).split())
    if len(normalized) < 80:
        return False
    chinese_chars = sum(1 for char in normalized if "\u4e00" <= char <= "\u9fff")
    return chinese_chars >= 40


def _topic_hint(item: dict[str, Any]) -> str:
    sections = [str(value) for value in item.get("sections", []) if str(value)]
    labels = [SECTION_LABELS.get(section, "") for section in sections]
    labels = [label for label in labels if label]
    if labels:
        return "、".join(labels[:2])
    categories = [str(value) for value in item.get("categories", []) if str(value)]
    if categories:
        return "、".join(categories[:2]) + " 相关方向"
    return "计算机体系结构或相关交叉方向"


def _relevance_reason(item: dict[str, Any]) -> str:
    sections = [str(value) for value in item.get("sections", []) if str(value)]
    labels = [SECTION_LABELS.get(section, section) for section in sections]
    categories = [str(value) for value in item.get("categories", []) if str(value)]
    if labels:
        return "它命中 " + "、".join(labels[:2]) + " 等兴趣方向，适合进一步判断是否值得精读。"
    if categories:
        return "它属于 " + "、".join(categories[:2]) + " 分类，适合作为探索性论文快速筛查。"
    return "它来自当前候选池，适合作为探索性论文快速筛查。"


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


if __name__ == "__main__":
    raise SystemExit(main())
