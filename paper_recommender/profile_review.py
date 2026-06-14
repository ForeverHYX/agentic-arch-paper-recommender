"""LLM-reviewed profile overlay for feedback-driven recommendation tuning."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from urllib.request import Request, urlopen

from paper_recommender.llm_errors import LLMProviderError, format_llm_error
from paper_recommender.summarizer import DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_USER_AGENT


ProfileReview = dict[str, Any]


def parse_profile_review_response(content: str) -> ProfileReview:
    raw = str(content).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    if not raw.startswith("{"):
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise ValueError(f"画像复核响应中没有 JSON 对象：{raw[:160]}")
        raw = match.group(0)
    return _normalize_review(json.loads(raw))


def request_profile_review(
    profile: dict[str, Any],
    payload: dict[str, Any],
    api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    opener: Callable[[Request], Any] = urlopen,
    timeout: int = 120,
) -> ProfileReview:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 2048,
        "thinking": {"type": "disabled"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "你正在复核一名计算机体系结构研究者的每日论文推荐画像。"
                    "根据当前画像、近期反馈和当天推荐，提出保守的画像调整建议。"
                    "不要直接改写画像；只输出一个 JSON 对象。"
                    "JSON keys 必须是 summary_zh, positive_adjustments, negative_adjustments, "
                    "exploration_notes, risk_notes, apply_to_runtime。"
                    "所有文本使用简体中文。apply_to_runtime 必须为 false。"
                    "如果反馈不足，请明确写入风险提示，不要过度推断。"
                    "不要把单个英文语法词、泛论文套话词、数字区间或无上下文的普通词当成兴趣关键词；"
                    "只引用明确的领域概念、工具链、系统类型、硬件/编译器/运行时主题或多词短语。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Current profile JSON:\n{_compact_json(profile, 6000)}\n\n"
                    f"Feedback summary:\n{_compact_json(payload.get('feedback_summary', {}), 4000)}\n\n"
                    f"Final recommendations:\n{_recommendations_text(payload.get('recommendations', []))}"
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
        response_payload = json.loads(response.read().decode("utf-8"))
    review = parse_profile_review_response(_chat_completion_content(response_payload))
    review["model"] = model
    review["generated_at"] = _utc_now()
    return review


def enrich_payload_with_profile_review(
    payload: dict[str, Any],
    profile: dict[str, Any],
    api_key: str = "",
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    opener: Callable[[Request], Any] = urlopen,
    require_api: bool = False,
) -> dict[str, Any]:
    if not api_key:
        if require_api:
            raise LLMProviderError(
                format_llm_error(
                    RuntimeError("OPENAI_API_KEY is not configured"),
                    base_url=base_url,
                    model=model,
                )
            )
        review = _unavailable_review(model)
    else:
        try:
            review = request_profile_review(
                profile,
                payload,
                api_key=api_key,
                base_url=base_url,
                model=model,
                opener=opener,
            )
        except Exception as exc:
            if require_api:
                raise LLMProviderError(format_llm_error(exc, base_url=base_url, model=model, api_key=api_key)) from exc
            review = _unavailable_review(model, reason=str(exc))

    enriched = dict(payload)
    enriched["profile_review"] = review
    return enriched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 LLM 画像复核 overlay。")
    parser.add_argument("--profile", required=True, help="兴趣画像 JSON 路径。")
    parser.add_argument("--recommendations", required=True, help="推荐 JSON 路径，会写回 profile_review 字段。")
    parser.add_argument("--output", required=True, help="画像复核 JSON 输出路径。")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--require-api", action="store_true", help="API 已配置时调用失败则退出，不写本地兜底。")
    args = parser.parse_args(argv)

    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    recommendations_path = Path(args.recommendations)
    payload = json.loads(recommendations_path.read_text(encoding="utf-8"))
    enriched = enrich_payload_with_profile_review(
        payload,
        profile,
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url=args.base_url,
        model=args.model,
        require_api=args.require_api,
    )
    review = enriched["profile_review"]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    recommendations_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入画像复核：{args.output}")
    return 0


def _normalize_review(value: dict[str, Any]) -> ProfileReview:
    return {
        "summary_zh": _short_text(value.get("summary_zh"), "模型没有返回画像复核摘要。", max_chars=320),
        "positive_adjustments": _short_list(value.get("positive_adjustments")),
        "negative_adjustments": _short_list(value.get("negative_adjustments")),
        "exploration_notes": _short_list(value.get("exploration_notes")),
        "risk_notes": _short_list(value.get("risk_notes")),
        "apply_to_runtime": False,
    }


def _unavailable_review(model: str, reason: str = "") -> ProfileReview:
    risk = "未启用 LLM，未生成画像复核。"
    if reason:
        risk = f"画像复核未生成：{_short_text(reason, '未知错误', max_chars=180)}"
    review = _normalize_review(
        {
            "summary_zh": "本次没有可用的 LLM 画像复核；系统不会自动调整主兴趣画像。",
            "positive_adjustments": [],
            "negative_adjustments": [],
            "exploration_notes": [],
            "risk_notes": [risk],
            "apply_to_runtime": False,
        }
    )
    review["model"] = model
    review["generated_at"] = _utc_now()
    review["status"] = "unavailable"
    return review


def _short_list(value: Any, limit: int = 6, max_chars: int = 140) -> list[str]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        text = _short_text(item, "", max_chars=max_chars)
        if text:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _short_text(value: Any, fallback: str, max_chars: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        text = fallback
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text


def _chat_completion_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM 响应缺少 choices")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ValueError("LLM 响应 choice 格式无效")
    message = choice.get("message")
    if isinstance(message, dict):
        content = _content_text(message.get("content"))
        if content:
            return content
    content = _content_text(choice.get("text"))
    if content:
        return content
    finish_reason = str(choice.get("finish_reason", ""))
    raise ValueError(f"LLM 返回空画像复核内容：finish_reason={finish_reason or 'unknown'}")


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return " ".join(" ".join(parts).split())
    return ""


def _recommendations_text(recommendations: Any, limit: int = 20) -> str:
    if not isinstance(recommendations, list):
        return "[]"
    lines = []
    for item in recommendations[:limit]:
        if not isinstance(item, dict):
            continue
        sections = ", ".join(str(section) for section in item.get("sections", []) if str(section))
        judgement = item.get("ai_judgement") if isinstance(item.get("ai_judgement"), dict) else {}
        lines.append(
            " | ".join(
                part
                for part in [
                    f"title: {item.get('title', '')}",
                    f"sections: {sections}",
                    f"ai_score: {judgement.get('score', item.get('ai_score', ''))}",
                    f"reason: {judgement.get('reason', '')}",
                ]
                if str(part).strip()
            )
        )
    return "\n".join(lines) if lines else "[]"


def _compact_json(value: Any, max_chars: int) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
