"""LLM-based relevance judgement and reranking for recommendation payloads."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from urllib.request import Request, urlopen

from paper_recommender.feedback import AI_INFRA_LEARNING_SCOPE, CORE_LEARNING_SCOPE
from paper_recommender.llm_errors import LLMProviderError, format_llm_error
from paper_recommender.summarizer import DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_USER_AGENT


Judgement = dict[str, Any]
REPOSITORY_LIMIT = 2


def parse_judgement_response(content: str) -> Judgement:
    raw = str(content).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    if not raw.startswith("{"):
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            return _parse_plain_text_judgement(raw)
        raw = match.group(0)
    try:
        return _normalize_judgement(json.loads(raw))
    except json.JSONDecodeError:
        return _parse_partial_json_judgement(raw)


def fallback_judgement(item: dict[str, Any]) -> Judgement:
    rule_score = _float_value(item.get("score"), 0.0)
    normalized_score = max(0.0, min(10.0, rule_score))
    decision = "keep" if normalized_score >= 1.0 else "drop"
    sections = ", ".join(str(section) for section in item.get("sections", []) if str(section))
    suffix = f"，栏目：{sections}" if sections else ""
    return {
        "score": normalized_score,
        "reason": f"规则得分兜底：原始得分 {rule_score:g}{suffix}。",
        "decision": decision,
    }


def request_judgement(
    item: dict[str, Any],
    api_key: str,
    profile_name: str = "",
    section_labels: dict[str, str] | None = None,
    feedback_summary: dict[str, Any] | None = None,
    seed_papers: list[dict[str, Any]] | None = None,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    opener: Callable[[Request], Any] = urlopen,
    timeout: int = 60,
) -> Judgement:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    section_text = _section_text(item, section_labels or {})
    feedback_text = _feedback_text(feedback_summary or {})
    seed_text = _seed_papers_text(seed_papers or [])
    repository_text = _repository_text(item)
    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 4096,
        "thinking": {"type": "disabled"},
        "messages": [
            {
                "role": "system",
                "content": _system_prompt_for_item(item),
            },
            {
                "role": "user",
                "content": (
                    f"Profile: {profile_name}\n"
                    f"Learned feedback profile: {feedback_text}\n"
                    f"Representative seed papers: {seed_text}\n"
                    f"Current rule sections: {section_text}\n"
                    f"Rule score: {item.get('score', '')}\n"
                    f"Title: {item.get('title', '')}\n"
                    f"Abstract: {item.get('abstract', '')}\n"
                    f"Affiliations: {', '.join(str(value) for value in item.get('affiliations', []))}\n"
                    f"Categories: {', '.join(str(value) for value in item.get('categories', []))}\n"
                    f"{repository_text}"
                    f"Positive keyword matches: {', '.join(str(value) for value in item.get('positive_matches', []))}\n"
                    f"Negative keyword matches: {', '.join(str(value) for value in item.get('negative_matches', []))}"
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
    content = _chat_completion_content(payload)
    return parse_judgement_response(content)


def enrich_payload_with_judgements(
    payload: dict[str, Any],
    api_key: str = "",
    limit: int = 15,
    exploration_limit: int = 0,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    opener: Callable[[Request], Any] = urlopen,
    require_api: bool = False,
) -> dict[str, Any]:
    profile_name = str(payload.get("profile_name", ""))
    section_labels = payload.get("section_labels") or {}
    feedback_summary = payload.get("feedback_summary") or {}
    seed_papers = _payload_seed_papers(payload)
    judged = []
    for item in payload.get("recommendations", []):
        updated = dict(item)
        judgement = updated.get("ai_judgement")
        if judgement:
            judgement = _normalize_judgement(judgement)
        else:
            judgement = _safe_judgement(
                updated,
                api_key=api_key,
                profile_name=profile_name,
                section_labels=section_labels,
                feedback_summary=_feedback_summary_for_item(updated, feedback_summary),
                seed_papers=seed_papers,
                base_url=base_url,
                model=model,
                opener=opener,
                require_api=require_api,
            )
        updated["ai_judgement"] = judgement
        updated["ai_score"] = judgement["score"]
        judged.append(updated)

    judged.sort(key=_ranking_key)
    kept = [item for item in judged if item["ai_judgement"]["decision"] != "drop"]
    dropped = [item for item in judged if item["ai_judgement"]["decision"] == "drop"]
    ai_infra_kept = [item for item in kept if _is_ai_infra_item(item)]
    core = [item for item in kept if not _is_ai_infra_item(item)]
    repositories = [item for item in ai_infra_kept if _is_repository_item(item)]
    selected_repositories = repositories[:REPOSITORY_LIMIT]
    selected_repository_ids = {str(item.get("paper_id", "")) for item in selected_repositories}
    non_repository_ai_infra = [
        item
        for item in ai_infra_kept
        if not _is_repository_item(item) and str(item.get("paper_id", "")) not in selected_repository_ids
    ]
    ai_infra_limit = max(0, exploration_limit)
    selected_ai_infra = (selected_repositories + non_repository_ai_infra)[:ai_infra_limit]
    core_limit = max(0, limit - len(selected_ai_infra))
    selected = core[:core_limit] + selected_ai_infra
    selected.sort(key=_ranking_key)
    for rank, item in enumerate(selected, start=1):
        item["rank"] = rank

    enriched = dict(payload)
    enriched["recommendations"] = selected
    enriched["count"] = len(selected)
    enriched["judge_summary"] = {
        "model": model,
        "candidate_count": len(judged),
        "kept_count": len(kept),
        "dropped_count": len(dropped),
        "limit": limit,
        "core_limit": core_limit,
        "exploration_limit": exploration_limit,
        "core_kept_count": len(core),
        "exploration_kept_count": len(ai_infra_kept),
        "exploration_selected_count": len(selected_ai_infra),
        "repository_limit": REPOSITORY_LIMIT,
        "repository_kept_count": len(repositories),
        "repository_selected_count": len(selected_repositories),
    }
    return enriched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="使用 LLM 判断并重排推荐 JSON。")
    parser.add_argument("--input", required=True, help="输入推荐 JSON 路径。")
    parser.add_argument("--output", required=True, help="输出推荐 JSON 路径。")
    parser.add_argument("--limit", type=int, default=15, help="AI 判断后最多保留推荐数。")
    parser.add_argument("--exploration-limit", type=int, default=0, help="AI 判断后额外保留探索论文数。")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    parser.add_argument("--require-api", action="store_true", help="API 已配置时调用失败则退出，不使用规则兜底。")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    enriched = enrich_payload_with_judgements(
        payload,
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        limit=args.limit,
        exploration_limit=args.exploration_limit,
        base_url=args.base_url,
        model=args.model,
        require_api=args.require_api,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "已判断 "
        f"{enriched.get('judge_summary', {}).get('candidate_count', 0)} 条候选，"
        f"保留 {enriched.get('count', 0)} 条推荐"
    )
    return 0


def _safe_judgement(
    item: dict[str, Any],
    api_key: str,
    profile_name: str,
    section_labels: dict[str, str],
    feedback_summary: dict[str, Any],
    seed_papers: list[dict[str, Any]],
    base_url: str,
    model: str,
    opener: Callable[[Request], Any],
    require_api: bool = False,
) -> Judgement:
    if not api_key:
        if require_api:
            raise LLMProviderError(
                format_llm_error(
                    RuntimeError("OPENAI_API_KEY is not configured"),
                    base_url=base_url,
                    model=model,
                )
            )
        return fallback_judgement(item)
    try:
        return request_judgement(
            item,
            api_key=api_key,
            profile_name=profile_name,
            section_labels=section_labels,
            feedback_summary=feedback_summary,
            seed_papers=seed_papers,
            base_url=base_url,
            model=model,
            opener=opener,
        )
    except Exception as exc:
        if require_api:
            raise LLMProviderError(format_llm_error(exc, base_url=base_url, model=model, api_key=api_key)) from exc
        return fallback_judgement(item)


def _normalize_judgement(value: dict[str, Any]) -> Judgement:
    score = max(0.0, min(10.0, _float_value(value.get("score"), 0.0)))
    reason = " ".join(str(value.get("reason", "")).split())[:240]
    decision = str(value.get("decision", "keep")).strip().lower()
    if decision not in {"keep", "drop"}:
        decision = "keep" if score >= 4.0 else "drop"
    if not reason:
        reason = "模型未返回原因，使用分数排序。"
    return {"score": score, "reason": reason, "decision": decision}


def _system_prompt_for_item(item: dict[str, Any]) -> str:
    repository_guidance = ""
    if _is_repository_item(item):
        repository_guidance = (
            "当前候选可能是 GitHub 仓库；判断时关注仓库核心内容、README 描述、topics、"
            "star 上涨趋势、是否实现真实系统或工具、是否链接原始论文。"
            "不要因为它不是 arXiv 论文就降分，但要降低泛 agent 工具、应用模板和无硬件/系统线索仓库。"
        )
    return (
        "你正在为一名计算机体系结构研究者判断 arXiv 论文或 GitHub 仓库相关性。"
        "核心兴趣包括 agentic computer architecture design、自动架构设计空间探索、"
        "全栈软硬件协同设计、CPU/GPU 微架构、体系结构模拟器，以及与 HPC、编译器、"
        "运行时和性能可移植性的交叉方向。降低泛 AI agent、Web/RAG benchmark、"
        "软件架构和无关机器学习论文的分数。作者单位只能作为弱质量信号，不能因为缺失单位就丢弃。"
        f"{repository_guidance}"
        "当 Current rule sections 包含 exploration 时，它属于额外 exploration 板块，目标是发现"
        "和当前画像不完全重合但可能值得关注的 AI/ML 系统、加速器、GPU、编译器、运行时、"
        "推理服务、训练系统或硬件感知机器学习论文；这是隔离的小配额探索通道，不代表主画像。"
        "只有存在 GPU/CUDA/加速器/编译器/运行时/调度/内存层次/互连等系统线索时才保留；纯 LLM 理论、"
        "纯应用、纯 benchmark、泛 Web/RAG agent 或完全缺少系统/硬件线索时 drop。"
        "仅在论文明显无关、过泛或质量过低时使用 decision=drop。"
        "只返回一行 JSON，不要 Markdown，不要解释。"
        "JSON keys 必须是 score, reason, decision；score 是 0-10；"
        "decision 只能是 keep 或 drop；reason 使用简体中文，80 个汉字以内。"
    )


def _is_repository_item(item: dict[str, Any]) -> bool:
    return str(item.get("item_type", "")).strip().lower() == "repository"


def _repository_text(item: dict[str, Any]) -> str:
    if not _is_repository_item(item):
        return ""
    return (
        f"Repository URL: {item.get('repository_url') or item.get('url', '')}\n"
        f"Stars today: {item.get('repository_stars_today', 0)}\n"
        f"Total stars: {item.get('repository_stars', 0)}\n"
        f"Forks: {item.get('repository_forks', 0)}\n"
        f"Language: {item.get('repository_language', '')}\n"
        f"Topics: {', '.join(str(value) for value in item.get('repository_topics', []))}\n"
        f"Original paper links: {_paper_links_text(item.get('paper_links') or [])}\n"
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


def _parse_plain_text_judgement(raw: str) -> Judgement:
    text = " ".join(str(raw).split())
    score_match = re.search(
        r"(?:score|分数|评分|相关性)[^\d]{0,20}([0-9]+(?:\.[0-9]+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if not score_match:
        preview = text[:160]
        raise ValueError(f"LLM 响应中没有 JSON 对象或可解析分数：{preview}")
    score = _float_value(score_match.group(1), 0.0)
    lowered = text.lower()
    if re.search(r"\b(drop|reject|discard)\b|丢弃|不保留|不推荐|无关", lowered):
        decision = "drop"
    elif re.search(r"\b(keep|accept|retain)\b|保留|推荐|相关", lowered):
        decision = "keep"
    else:
        decision = "keep" if score >= 4.0 else "drop"
    reason = re.sub(
        r"(?i)\b(score|decision|reason)\b\s*[:：]?",
        "",
        text,
    ).strip(" -;；：:")
    return _normalize_judgement({"score": score, "reason": reason or text, "decision": decision})


def _parse_partial_json_judgement(raw: str) -> Judgement:
    score = _json_number_field(raw, "score")
    if score is None:
        return _parse_plain_text_judgement(raw)
    reason = _json_string_field(raw, "reason") or "模型返回了可解析分数，但说明文本不完整。"
    decision = _json_string_field(raw, "decision").lower()
    if decision not in {"keep", "drop"}:
        decision = "keep" if score >= 4.0 else "drop"
    return _normalize_judgement({"score": score, "reason": reason, "decision": decision})


def _json_number_field(raw: str, field: str) -> float | None:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*([0-9]+(?:\.[0-9]+)?)', raw)
    if not match:
        return None
    return _float_value(match.group(1), 0.0)


def _json_string_field(raw: str, field: str) -> str:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*"((?:\\.|[^"\\])*)', raw, flags=re.DOTALL)
    if not match:
        return ""
    value = match.group(1)
    try:
        return str(json.loads(f'"{value}"'))
    except json.JSONDecodeError:
        return value.replace(r"\"", '"').replace(r"\\", "\\").strip()


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
    choice_keys = ", ".join(sorted(str(key) for key in choice.keys()))
    message_keys = ""
    reasoning_chars = 0
    if isinstance(message, dict):
        message_keys = ", ".join(sorted(str(key) for key in message.keys()))
        reasoning_chars = len(_content_text(message.get("reasoning_content") or message.get("reasoning")))
    raise ValueError(
        "LLM 返回空 judgement 内容："
        f"finish_reason={finish_reason or 'unknown'}; "
        f"choice_keys={choice_keys or 'none'}; "
        f"message_keys={message_keys or 'none'}; "
        f"reasoning_chars={reasoning_chars}"
    )


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


def _ranking_key(item: dict[str, Any]) -> tuple[float, float, str]:
    return (
        -_float_value(item.get("ai_score"), 0.0),
        -_float_value(item.get("score"), 0.0),
        str(item.get("paper_id", "")),
    )


def _is_ai_infra_item(item: dict[str, Any]) -> bool:
    scope = str(item.get("learning_scope", "")).strip().lower()
    if scope == CORE_LEARNING_SCOPE:
        return False
    if scope == AI_INFRA_LEARNING_SCOPE:
        return True
    sections = {str(section) for section in item.get("sections", [])}
    return bool(sections & {"exploration", "github_arch_ai_infra", "exploratory"})


def _feedback_summary_for_item(item: dict[str, Any], feedback_summary: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(feedback_summary, dict):
        return {}
    if _is_ai_infra_item(item):
        ai_infra_summary = feedback_summary.get(AI_INFRA_LEARNING_SCOPE)
        if isinstance(ai_infra_summary, dict):
            return ai_infra_summary
        legacy_summary = feedback_summary.get("ai_infra_exploration")
        if isinstance(legacy_summary, dict):
            return legacy_summary
    return feedback_summary


def _section_text(item: dict[str, Any], section_labels: dict[str, str]) -> str:
    labels = []
    for section in item.get("sections", []):
        section_key = str(section)
        labels.append(str(section_labels.get(section_key, section_key)))
    return ", ".join(labels)


def _feedback_text(feedback_summary: dict[str, Any]) -> str:
    section_weights = _weight_dict(feedback_summary.get("section_weights", {}))
    keyword_weights = _weight_dict(feedback_summary.get("keyword_weights", {}))
    author_weights = _weight_dict(feedback_summary.get("author_weights", {}))
    affiliation_weights = _weight_dict(feedback_summary.get("affiliation_weights", {}))
    toolchain_weights = _weight_dict(feedback_summary.get("toolchain_weights", {}))
    prefer_sections = _top_weight_names(section_weights, positive=True)
    avoid_sections = _top_weight_names(section_weights, positive=False)
    prefer_keywords = _top_weight_names(keyword_weights, positive=True)
    avoid_keywords = _top_weight_names(keyword_weights, positive=False)
    prefer_authors = _top_weight_names(author_weights, positive=True)
    avoid_authors = _top_weight_names(author_weights, positive=False)
    prefer_affiliations = _top_weight_names(affiliation_weights, positive=True)
    avoid_affiliations = _top_weight_names(affiliation_weights, positive=False)
    prefer_toolchains = _top_weight_names(toolchain_weights, positive=True)
    avoid_toolchains = _top_weight_names(toolchain_weights, positive=False)
    parts = [
        f"Prefer sections: {', '.join(prefer_sections) if prefer_sections else 'none'}",
        f"Avoid sections: {', '.join(avoid_sections) if avoid_sections else 'none'}",
        f"Prefer keywords: {', '.join(prefer_keywords) if prefer_keywords else 'none'}",
        f"Avoid keywords: {', '.join(avoid_keywords) if avoid_keywords else 'none'}",
        f"Prefer authors: {', '.join(prefer_authors) if prefer_authors else 'none'}",
        f"Avoid authors: {', '.join(avoid_authors) if avoid_authors else 'none'}",
        f"Prefer affiliations: {', '.join(prefer_affiliations) if prefer_affiliations else 'none'}",
        f"Avoid affiliations: {', '.join(avoid_affiliations) if avoid_affiliations else 'none'}",
        f"Prefer toolchains: {', '.join(prefer_toolchains) if prefer_toolchains else 'none'}",
        f"Avoid toolchains: {', '.join(avoid_toolchains) if avoid_toolchains else 'none'}",
    ]
    return "; ".join(parts)


def _payload_seed_papers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    profile_context = payload.get("profile_context")
    if not isinstance(profile_context, dict):
        return []
    seed_papers = profile_context.get("seed_papers", [])
    if not isinstance(seed_papers, list):
        return []
    return [item for item in seed_papers if isinstance(item, dict)]


def _seed_papers_text(seed_papers: list[dict[str, Any]], limit: int = 6) -> str:
    lines = []
    for item in seed_papers[:limit]:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        notes = " ".join(str(item.get("notes", "")).split())
        keywords = ", ".join(str(value) for value in item.get("keywords", []) if str(value))
        parts = [title]
        if keywords:
            parts.append(f"keywords: {keywords}")
        if notes:
            parts.append(f"notes: {notes}")
        lines.append(" | ".join(parts))
    return "\n".join(lines) if lines else "none"


def _top_weight_names(weights: dict[str, float], positive: bool, limit: int = 8) -> list[str]:
    filtered = [
        (name, weight)
        for name, weight in weights.items()
        if (weight > 0 if positive else weight < 0)
    ]
    filtered.sort(key=lambda item: (-abs(item[1]), item[0]))
    return [name for name, _ in filtered[:limit]]


def _weight_dict(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    weights = {}
    for key, raw_weight in value.items():
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            continue
        if weight != 0:
            weights[str(key)] = weight
    return weights


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    raise SystemExit(main())
