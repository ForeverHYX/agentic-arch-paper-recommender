"""Pipeline helpers for turning paper records into recommendation payloads."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any

from paper_recommender.domain import InterestProfile, Paper, load_interest_profile, rank_papers
from paper_recommender.feedback import (
    FeedbackEvent,
    load_feedback_json,
    section_feedback_weights,
    text_feedback_adjustment,
    text_feedback_weights,
)


def paper_from_record(record: dict[str, Any]) -> Paper:
    paper_id = _first_text(record, ("paper_id", "id", "arxiv_id", "entry_id", "url"))
    title = _first_text(record, ("title",))
    abstract = _first_text(record, ("abstract", "summary", "description"))
    authors = _authors_from_record(record.get("authors", []))
    categories = _categories_from_record(record.get("categories", record.get("category", [])))

    return Paper(
        paper_id=paper_id,
        title=title,
        abstract=abstract,
        authors=authors,
        categories=categories,
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
) -> dict[str, Any]:
    resolved_profile = profile or load_interest_profile()
    feedback_weights = section_feedback_weights(feedback_events or [])
    keyword_weights = text_feedback_weights(feedback_events or [])
    ranked = _apply_feedback_weights(
        rank_papers(papers, profile=resolved_profile),
        feedback_weights,
        keyword_weights,
    )
    if limit is not None:
        ranked = ranked[:limit]

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
                "categories": paper.categories,
                "score": result.score,
                "sections": list(result.sections),
                "positive_matches": list(result.positive_matches),
                "negative_matches": list(result.negative_matches),
            }
        )

    resolved_run_date = run_date or date.today().isoformat()
    return {
        "run_date": resolved_run_date,
        "profile_name": resolved_profile.name,
        "section_labels": resolved_profile.section_labels,
        "feedback_summary": {
            "section_weights": feedback_weights,
            "keyword_weights": keyword_weights,
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
) -> dict[str, Any]:
    payload = recommendation_payload(
        papers,
        run_date=run_date,
        limit=limit,
        profile=profile,
        feedback_events=feedback_events,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build recommendation JSON from paper JSONL.")
    parser.add_argument("--input", required=True, help="Input JSONL paper records.")
    parser.add_argument("--output", required=True, help="Output recommendation JSON path.")
    parser.add_argument("--run-date", default=None, help="Run date to store in output.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum recommendations to emit.")
    parser.add_argument("--profile", default=None, help="Interest profile JSON path.")
    parser.add_argument("--feedback", default=None, help="Feedback events JSON path.")
    args = parser.parse_args(argv)

    papers = load_papers_jsonl(args.input)
    profile = load_interest_profile(args.profile) if args.profile else None
    feedback_events = load_feedback_json(args.feedback) if args.feedback else None
    payload = write_recommendations_json(
        papers,
        output_path=args.output,
        run_date=args.run_date,
        limit=args.limit,
        profile=profile,
        feedback_events=feedback_events,
    )
    print(f"Wrote {payload['count']} recommendations to {args.output}")
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


def _categories_from_record(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.replace(",", " ").split() if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _apply_feedback_weights(
    results,
    section_weights: dict[str, float],
    keyword_weights: dict[str, float],
):
    adjusted = []
    for result in results:
        paper = result.paper
        paper_text = " ".join([paper.title, paper.abstract, " ".join(paper.authors), " ".join(paper.categories)])
        adjustment = sum(section_weights.get(section, 0.0) for section in result.sections)
        adjustment += text_feedback_adjustment(paper_text, keyword_weights)
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


if __name__ == "__main__":
    raise SystemExit(main())
