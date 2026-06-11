"""LLM-based relevance judgement and reranking for recommendation payloads."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from urllib.request import Request, urlopen

from paper_recommender.summarizer import DEFAULT_BASE_URL, DEFAULT_MODEL


Judgement = dict[str, Any]


def parse_judgement_response(content: str) -> Judgement:
    raw = str(content).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    if not raw.startswith("{"):
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise ValueError("LLM response did not contain a JSON object")
        raw = match.group(0)
    return _normalize_judgement(json.loads(raw))


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
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    opener: Callable[[Request], Any] = urlopen,
    timeout: int = 60,
) -> Judgement:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    section_text = _section_text(item, section_labels or {})
    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 220,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are judging arXiv paper relevance for a computer architecture researcher. "
                    "The user's main interests are agentic computer architecture design, automated "
                    "architecture design-space exploration, full-stack hardware/software co-design, "
                    "CPU/GPU microarchitecture, architecture simulators, and intersections with HPC, "
                    "compilers, runtimes, and performance portability. Penalize generic AI agents, "
                    "web/RAG benchmarks, software architecture, and unrelated ML papers. "
                    "Use author affiliations as a weak quality/context signal when present, but do not "
                    "drop a paper solely because affiliations are missing. "
                    "Return only JSON with keys score, reason, decision. score is 0-10; decision is keep or drop."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Profile: {profile_name}\n"
                    f"Current rule sections: {section_text}\n"
                    f"Rule score: {item.get('score', '')}\n"
                    f"Title: {item.get('title', '')}\n"
                    f"Abstract: {item.get('abstract', '')}\n"
                    f"Affiliations: {', '.join(str(value) for value in item.get('affiliations', []))}\n"
                    f"Categories: {', '.join(str(value) for value in item.get('categories', []))}\n"
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
    return parse_judgement_response(content)


def enrich_payload_with_judgements(
    payload: dict[str, Any],
    api_key: str = "",
    limit: int = 15,
    base_url: str = DEFAULT_BASE_URL,
    model: str = DEFAULT_MODEL,
    opener: Callable[[Request], Any] = urlopen,
) -> dict[str, Any]:
    profile_name = str(payload.get("profile_name", ""))
    section_labels = payload.get("section_labels") or {}
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
                base_url=base_url,
                model=model,
                opener=opener,
            )
        updated["ai_judgement"] = judgement
        updated["ai_score"] = judgement["score"]
        judged.append(updated)

    judged.sort(key=_ranking_key)
    kept = [item for item in judged if item["ai_judgement"]["decision"] != "drop"]
    dropped = [item for item in judged if item["ai_judgement"]["decision"] == "drop"]
    selected = (kept + dropped)[:limit]
    for rank, item in enumerate(selected, start=1):
        item["rank"] = rank

    enriched = dict(payload)
    enriched["recommendations"] = selected
    enriched["count"] = len(selected)
    enriched["judge_summary"] = {
        "model": model,
        "candidate_count": len(judged),
        "kept_count": len(kept),
        "limit": limit,
    }
    return enriched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Judge and rerank recommendation JSON with an LLM.")
    parser.add_argument("--input", required=True, help="Input recommendation JSON path.")
    parser.add_argument("--output", required=True, help="Output recommendation JSON path.")
    parser.add_argument("--limit", type=int, default=15, help="Maximum recommendations after AI judgement.")
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    enriched = enrich_payload_with_judgements(
        payload,
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        limit=args.limit,
        base_url=args.base_url,
        model=args.model,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "Judged "
        f"{enriched.get('judge_summary', {}).get('candidate_count', 0)} candidates "
        f"and kept {enriched.get('count', 0)} recommendations"
    )
    return 0


def _safe_judgement(
    item: dict[str, Any],
    api_key: str,
    profile_name: str,
    section_labels: dict[str, str],
    base_url: str,
    model: str,
    opener: Callable[[Request], Any],
) -> Judgement:
    if not api_key:
        return fallback_judgement(item)
    try:
        return request_judgement(
            item,
            api_key=api_key,
            profile_name=profile_name,
            section_labels=section_labels,
            base_url=base_url,
            model=model,
            opener=opener,
        )
    except Exception:
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


def _ranking_key(item: dict[str, Any]) -> tuple[float, float, str]:
    return (
        -_float_value(item.get("ai_score"), 0.0),
        -_float_value(item.get("score"), 0.0),
        str(item.get("paper_id", "")),
    )


def _section_text(item: dict[str, Any], section_labels: dict[str, str]) -> str:
    labels = []
    for section in item.get("sections", []):
        section_key = str(section)
        labels.append(str(section_labels.get(section_key, section_key)))
    return ", ".join(labels)


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    raise SystemExit(main())
