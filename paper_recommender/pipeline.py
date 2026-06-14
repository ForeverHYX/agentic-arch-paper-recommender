"""Pipeline helpers for turning paper records into recommendation payloads."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote_plus

from paper_recommender.domain import Classification, InterestProfile, Paper, classify_paper, load_interest_profile, rank_papers
from paper_recommender.feedback import (
    affiliation_feedback_weights,
    author_feedback_weights,
    entity_feedback_adjustment,
    FeedbackEvent,
    feedback_metrics,
    load_feedback_json,
    section_feedback_weights,
    text_feedback_adjustment,
    text_feedback_weights,
    toolchain_feedback_adjustment,
    toolchain_feedback_weights,
)
from paper_recommender.history import RecommendationRun, history_counts, load_history_json


EXPLORATION_SECTION = "exploration"
EXPLORATION_LABEL = "Exploration / AI+体系结构探索"
EXPLORATION_CATEGORIES = frozenset({"cs.AI", "cs.LG", "cs.AR", "cs.PF", "cs.DC", "cs.PL"})
EXPLORATION_AI_ML_KEYWORDS = (
    "ai model",
    "attention",
    "deep learning",
    "foundation model",
    "inference",
    "language model",
    "llm",
    "machine learning",
    "neural network",
    "quantization",
    "training",
    "transformer",
)
EXPLORATION_SYSTEMS_KEYWORDS = (
    "accelerator",
    "asic",
    "compiler",
    "consumer gpu",
    "energy efficient",
    "fpga",
    "fp8",
    "gpu",
    "hardware",
    "hardware aware",
    "hardware-aware",
    "inference serving",
    "interconnect",
    "int8",
    "bitwidth",
    "low-bit",
    "machine learning systems",
    "memory hierarchy",
    "ml compiler",
    "performance model",
    "quantization",
    "runtime",
    "serving system",
    "systolic",
    "systems for machine learning",
    "tensor",
    "training system",
)


def paper_from_record(record: dict[str, Any]) -> Paper:
    paper_id = _first_text(record, ("paper_id", "id", "arxiv_id", "entry_id", "url"))
    title = _first_text(record, ("title",))
    abstract = _first_text(record, ("abstract", "summary", "description"))
    authors = _authors_from_record(record.get("authors", []))
    affiliations = _affiliations_from_record(record)
    categories = _categories_from_record(record.get("categories", record.get("category", [])))
    url = _first_text(record, ("url", "abs_url", "paper_url"))
    pdf_url = _first_text(record, ("pdf_url",))
    if not pdf_url and url:
        pdf_url = _pdf_url_from_abs_url(url)
    code_urls = _code_urls_from_record(record)
    code_search_url = _code_search_url(title=title, paper_id=paper_id)
    item_type = _first_text(record, ("item_type",)) or "paper"
    source = _first_text(record, ("source",)) or ("github_trending" if item_type == "repository" else "arxiv")
    repository_url = _first_text(record, ("repository_url", "repo_url"))
    repository_full_name = _first_text(record, ("repository_full_name", "full_name"))
    repository_language = _first_text(record, ("repository_language", "language"))
    repository_topics = _string_list(record.get("repository_topics", record.get("topics", [])))
    repository_homepage = _first_text(record, ("repository_homepage", "homepage"))
    repository_pushed_at = _first_text(record, ("repository_pushed_at", "pushed_at"))

    return Paper(
        paper_id=paper_id,
        title=title,
        abstract=abstract,
        authors=authors,
        categories=categories,
        affiliations=affiliations,
        url=url,
        pdf_url=pdf_url,
        code_urls=code_urls,
        code_search_url=code_search_url,
        item_type=item_type,
        source=source,
        repository_url=repository_url,
        repository_full_name=repository_full_name,
        repository_stars=_int_value(record.get("repository_stars", record.get("stargazers_count"))),
        repository_forks=_int_value(record.get("repository_forks", record.get("forks_count"))),
        repository_stars_today=_int_value(record.get("repository_stars_today", record.get("stars_today"))),
        repository_language=repository_language,
        repository_topics=repository_topics,
        repository_pushed_at=repository_pushed_at,
        repository_homepage=repository_homepage,
        paper_links=_paper_links_from_record(record),
    )


def load_papers_jsonl(path: str | Path) -> list[Paper]:
    papers: list[Paper] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            papers.append(paper_from_record(json.loads(stripped)))
    return papers


def recommendation_payload(
    papers: list[Paper],
    run_date: str | None = None,
    limit: int | None = None,
    profile: InterestProfile | None = None,
    feedback_events: list[FeedbackEvent] | None = None,
    history_runs: list[RecommendationRun] | None = None,
    min_count: int = 0,
    exploration_count: int = 0,
) -> dict[str, Any]:
    resolved_profile = profile or load_interest_profile()
    resolved_feedback_events = feedback_events or []
    feedback_weights = section_feedback_weights(resolved_feedback_events)
    keyword_weights = text_feedback_weights(resolved_feedback_events)
    author_weights = author_feedback_weights(resolved_feedback_events)
    affiliation_weights = affiliation_feedback_weights(resolved_feedback_events)
    toolchain_weights = toolchain_feedback_weights(resolved_feedback_events)
    shown_counts = history_counts(history_runs or [])
    ranked = _apply_feedback_weights(
        rank_papers(papers, profile=resolved_profile),
        feedback_weights,
        keyword_weights,
        author_weights,
        affiliation_weights,
        toolchain_weights,
        shown_counts,
    )
    if min_count:
        ranked = _with_exploratory_fill(
            ranked,
            papers,
            resolved_profile,
            min_count,
            feedback_weights,
            keyword_weights,
            author_weights,
            affiliation_weights,
            toolchain_weights,
            shown_counts,
        )
    if limit is not None:
        ranked = ranked[:limit]
    if exploration_count:
        ranked = ranked + _exploration_candidates(
            ranked,
            papers,
            resolved_profile,
            exploration_count,
            feedback_weights,
            keyword_weights,
            author_weights,
            affiliation_weights,
            toolchain_weights,
            shown_counts,
        )

    recommendations = []
    for rank, result in enumerate(ranked, start=1):
        paper = result.paper
        recommendations.append(
            {
                "rank": rank,
                "paper_id": paper.paper_id,
                "title": paper.title,
                "abstract": paper.abstract,
                "authors": paper.authors,
                "affiliations": paper.affiliations,
                "categories": paper.categories,
                "url": paper.url,
                "pdf_url": paper.pdf_url,
                "code_urls": paper.code_urls,
                "code_search_url": paper.code_search_url,
                "item_type": paper.item_type,
                "source": paper.source,
                "repository_url": paper.repository_url,
                "repository_full_name": paper.repository_full_name,
                "repository_stars": paper.repository_stars,
                "repository_forks": paper.repository_forks,
                "repository_stars_today": paper.repository_stars_today,
                "repository_language": paper.repository_language,
                "repository_topics": paper.repository_topics,
                "repository_pushed_at": paper.repository_pushed_at,
                "repository_homepage": paper.repository_homepage,
                "paper_links": paper.paper_links,
                "score": result.score,
                "sections": list(result.sections),
                "positive_matches": list(result.positive_matches),
                "negative_matches": list(result.negative_matches),
            }
        )

    resolved_run_date = run_date or date.today().isoformat()
    section_labels = dict(resolved_profile.section_labels)
    section_labels[EXPLORATION_SECTION] = EXPLORATION_LABEL
    return {
        "run_date": resolved_run_date,
        "profile_name": resolved_profile.name,
        "section_labels": section_labels,
        "profile_context": {
            "seed_papers": [seed.to_dict() for seed in resolved_profile.seed_papers],
        },
        "feedback_summary": {
            "section_weights": feedback_weights,
            "keyword_weights": keyword_weights,
            "author_weights": author_weights,
            "affiliation_weights": affiliation_weights,
            "toolchain_weights": toolchain_weights,
            "metrics": feedback_metrics(resolved_feedback_events),
        },
        "history_summary": {
            "shown_counts": shown_counts,
        },
        "count": len(recommendations),
        "recommendations": recommendations,
    }


def write_recommendations_json(
    papers: list[Paper],
    output_path: str | Path,
    run_date: str | None = None,
    limit: int | None = None,
    profile: InterestProfile | None = None,
    feedback_events: list[FeedbackEvent] | None = None,
    history_runs: list[RecommendationRun] | None = None,
    min_count: int = 0,
    exploration_count: int = 0,
) -> dict[str, Any]:
    payload = recommendation_payload(
        papers,
        run_date=run_date,
        limit=limit,
        profile=profile,
        feedback_events=feedback_events,
        history_runs=history_runs,
        min_count=min_count,
        exploration_count=exploration_count,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从论文 JSONL 生成推荐 JSON。")
    parser.add_argument("--input", required=True, help="输入论文 JSONL 记录。")
    parser.add_argument("--output", required=True, help="输出推荐 JSON 路径。")
    parser.add_argument("--run-date", default=None, help="写入输出的运行日期。")
    parser.add_argument("--limit", type=int, default=None, help="最多输出推荐数。")
    parser.add_argument("--profile", default=None, help="兴趣画像 JSON 路径。")
    parser.add_argument("--feedback", default=None, help="反馈事件 JSON 路径。")
    parser.add_argument("--history", default=None, help="推荐历史 JSON 路径。")
    parser.add_argument("--min-count", type=int, default=0, help="用探索性核心分类论文补足到该数量。")
    parser.add_argument("--exploration-count", type=int, default=0, help="额外加入 AI/ML 体系结构探索候选数。")
    args = parser.parse_args(argv)

    papers = load_papers_jsonl(args.input)
    profile = load_interest_profile(args.profile) if args.profile else None
    feedback_events = load_feedback_json(args.feedback) if args.feedback else None
    history_runs = load_history_json(args.history) if args.history else None
    payload = write_recommendations_json(
        papers,
        output_path=args.output,
        run_date=args.run_date,
        limit=args.limit,
        profile=profile,
        feedback_events=feedback_events,
        history_runs=history_runs,
        min_count=args.min_count,
        exploration_count=args.exploration_count,
    )
    print(f"已写入 {payload['count']} 条推荐到 {args.output}")
    return 0


def _first_text(record: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _authors_from_record(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(value, list):
        return []

    authors: list[str] = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                authors.append(name)
        elif item is not None:
            name = str(item).strip()
            if name:
                authors.append(name)
    return authors


def _affiliations_from_record(record: dict[str, Any]) -> list[str]:
    affiliations: list[str] = []
    for key in ("affiliations", "author_affiliations", "institutions"):
        affiliations.extend(_string_list(record.get(key, [])))

    authors = record.get("authors", [])
    if isinstance(authors, list):
        for author in authors:
            if not isinstance(author, dict):
                continue
            for key in ("affiliation", "affiliations", "institution", "institutions"):
                affiliations.extend(_string_list(author.get(key, [])))

    seen = set()
    result = []
    for affiliation in affiliations:
        normalized = affiliation.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(affiliation)
    return result


def _categories_from_record(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.replace(",", " ").split() if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _code_urls_from_record(record: dict[str, Any]) -> list[str]:
    explicit = record.get("code_urls", record.get("code_url", []))
    urls = _url_list(explicit)
    text = " ".join([str(record.get("abstract", "")), str(record.get("summary", "")), str(record.get("description", ""))])
    urls.extend(_extract_code_urls(text))
    seen = set()
    result = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _url_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = str(item.get("name", item.get("display_name", ""))).strip()
            else:
                text = str(item).strip()
            if text:
                result.append(text)
        return result
    return []


def _int_value(value: Any) -> int:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _paper_links_from_record(record: dict[str, Any]) -> list[dict[str, str]]:
    raw_links = record.get("paper_links", [])
    if not isinstance(raw_links, list):
        return []
    links: list[dict[str, str]] = []
    seen = set()
    for item in raw_links:
        if isinstance(item, dict):
            url = str(item.get("url", "")).strip()
            label = str(item.get("label", "")).strip() or "Paper"
        else:
            url = str(item).strip()
            label = "Paper"
        if not url or url in seen:
            continue
        seen.add(url)
        links.append({"label": label, "url": url})
    return links


def _extract_code_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://(?:github\.com|gitlab\.com|bitbucket\.org|huggingface\.co)/[^\s),.;]+", text)
    return [url.rstrip(".,;)") for url in urls]


def _pdf_url_from_abs_url(url: str) -> str:
    match = re.search(r"arxiv\.org/abs/([^?#]+)", url)
    if not match:
        return ""
    return f"https://arxiv.org/pdf/{match.group(1)}"


def _code_search_url(title: str, paper_id: str) -> str:
    query = title.strip() or paper_id.strip()
    if not query:
        return ""
    return f"https://github.com/search?q={quote_plus(query)}&type=repositories"


def _with_exploratory_fill(
    ranked: list[Classification],
    papers: list[Paper],
    profile: InterestProfile,
    min_count: int,
    section_weights: dict[str, float],
    keyword_weights: dict[str, float],
    author_weights: dict[str, float],
    affiliation_weights: dict[str, float],
    toolchain_weights: dict[str, float],
    shown_counts: dict[str, int],
) -> list[Classification]:
    if len(ranked) >= min_count:
        return ranked
    ranked_ids = {result.paper.paper_id for result in ranked}
    core_exploratory = []
    expansion_exploratory = []
    for paper in papers:
        if paper.paper_id in ranked_ids:
            continue
        categories = set(paper.categories)
        in_core = bool(categories & profile.core_categories)
        in_expansion = bool(categories & profile.expansion_categories)
        if not in_core and not in_expansion:
            continue
        result = classify_paper(paper, profile=profile)
        if result.accepted:
            continue
        if result.negative_matches:
            continue
        target = core_exploratory if in_core else expansion_exploratory
        target.append(
            Classification(
                paper=paper,
                accepted=True,
                score=0.1 if in_core else -0.25,
                sections=("exploratory",),
                positive_matches=(),
                negative_matches=(),
            )
        )
    exploratory = core_exploratory + expansion_exploratory
    filled = ranked + _apply_feedback_weights(
        exploratory,
        section_weights,
        keyword_weights,
        author_weights,
        affiliation_weights,
        toolchain_weights,
        shown_counts,
    )
    return filled[:max(min_count, len(ranked))]


def _exploration_candidates(
    ranked: list[Classification],
    papers: list[Paper],
    profile: InterestProfile,
    count: int,
    section_weights: dict[str, float],
    keyword_weights: dict[str, float],
    author_weights: dict[str, float],
    affiliation_weights: dict[str, float],
    toolchain_weights: dict[str, float],
    shown_counts: dict[str, int],
) -> list[Classification]:
    if count <= 0:
        return []
    ranked_ids = {result.paper.paper_id for result in ranked}
    candidates = []
    for paper in papers:
        if paper.paper_id in ranked_ids:
            continue
        if not set(paper.categories) & EXPLORATION_CATEGORIES:
            continue
        result = classify_paper(paper, profile=profile)
        if result.accepted or result.negative_matches:
            continue
        matches = _matching_exploration_keywords(paper)
        if not matches:
            continue
        candidates.append(
            Classification(
                paper=paper,
                accepted=True,
                score=min(3.0, len(matches) * 0.25),
                sections=(EXPLORATION_SECTION,),
                positive_matches=tuple(f"{EXPLORATION_SECTION}:{match}" for match in matches),
                negative_matches=(),
            )
        )
    adjusted = _apply_feedback_weights(
        candidates,
        section_weights,
        keyword_weights,
        author_weights,
        affiliation_weights,
        toolchain_weights,
        shown_counts,
    )
    return adjusted[:count]


def _apply_feedback_weights(
    results,
    section_weights: dict[str, float],
    keyword_weights: dict[str, float],
    author_weights: dict[str, float],
    affiliation_weights: dict[str, float],
    toolchain_weights: dict[str, float],
    shown_counts: dict[str, int],
):
    adjusted = []
    for result in results:
        paper = result.paper
        paper_text = " ".join(
            [
                paper.title,
                paper.abstract,
                " ".join(paper.authors),
                " ".join(paper.affiliations),
                " ".join(paper.categories),
            ]
        )
        adjustment = sum(section_weights.get(section, 0.0) for section in result.sections)
        adjustment += text_feedback_adjustment(paper_text, keyword_weights)
        adjustment += entity_feedback_adjustment(paper.authors, author_weights)
        adjustment += entity_feedback_adjustment(paper.affiliations, affiliation_weights, scale=0.5)
        adjustment += toolchain_feedback_adjustment(paper_text, toolchain_weights)
        adjustment -= min(shown_counts.get(paper.paper_id, 0), 3) * 2.0
        if adjustment == 0:
            adjusted.append(result)
            continue
        adjusted.append(
            type(result)(
                paper=result.paper,
                accepted=result.accepted,
                score=result.score + adjustment,
                sections=result.sections,
                positive_matches=result.positive_matches,
                negative_matches=result.negative_matches,
            )
        )
    return sorted(adjusted, key=lambda result: (-result.score, result.paper.paper_id))


def _matching_exploration_keywords(paper: Paper) -> tuple[str, ...]:
    text = _normalize_for_matching(
        " ".join(
            [
                paper.title,
                paper.abstract,
                " ".join(paper.authors),
                " ".join(paper.affiliations),
            ]
        )
    )
    ai_matches = tuple(keyword for keyword in EXPLORATION_AI_ML_KEYWORDS if _keyword_matches_text(text, keyword))
    systems_matches = tuple(
        keyword for keyword in EXPLORATION_SYSTEMS_KEYWORDS if _keyword_matches_text(text, keyword)
    )
    if not ai_matches or not systems_matches:
        return ()
    return ai_matches + systems_matches


def _normalize_for_matching(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _keyword_matches_text(text: str, keyword: str) -> bool:
    normalized = _normalize_for_matching(keyword)
    if not normalized:
        return False
    if re.fullmatch(r"[a-z0-9][a-z0-9.+#-]{0,4}", normalized):
        return re.search(rf"\b{re.escape(normalized)}\b", text) is not None
    return normalized in text


if __name__ == "__main__":
    raise SystemExit(main())
