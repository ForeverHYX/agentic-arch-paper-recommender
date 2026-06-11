"""Feedback ingestion and lightweight profile adjustment helpers."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


STOPWORDS = frozenset(
    {
        "about",
        "across",
        "after",
        "also",
        "from",
        "into",
        "that",
        "their",
        "this",
        "through",
        "using",
        "uses",
        "with",
        "without",
        "and",
        "for",
        "the",
        "are",
        "can",
        "our",
        "via",
    }
)


@dataclass(frozen=True)
class FeedbackEvent:
    paper_id: str
    rating: str
    section: str
    source: str = "page"
    title: str = ""
    abstract: str = ""
    authors: tuple[str, ...] = ()
    affiliations: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "authors", tuple(self.authors))
        object.__setattr__(self, "affiliations", tuple(self.affiliations))
        object.__setattr__(self, "categories", tuple(self.categories))


def feedback_events_from_records(records: list[dict[str, Any]]) -> list[FeedbackEvent]:
    events: list[FeedbackEvent] = []
    for record in records:
        rating = str(record.get("rating", "")).strip().lower()
        paper_id = str(record.get("paper_id", "")).strip()
        section = str(record.get("section", "")).strip()
        source = str(record.get("source", "page")).strip() or "page"
        if rating not in {"like", "dislike"} or not paper_id:
            continue
        events.append(
            FeedbackEvent(
                paper_id=paper_id,
                rating=rating,
                section=section,
                source=source,
                title=str(record.get("title", "")).strip(),
                abstract=str(record.get("abstract", "")).strip(),
                authors=tuple(_string_list(record.get("authors", []))),
                affiliations=tuple(_string_list(record.get("affiliations", []))),
                categories=tuple(_string_list(record.get("categories", []))),
            )
        )
    return events


def load_feedback_json(path: str | Path) -> list[FeedbackEvent]:
    return feedback_events_from_records(json.loads(Path(path).read_text(encoding="utf-8")))


def section_feedback_weights(events: list[FeedbackEvent]) -> dict[str, float]:
    weights: dict[str, float] = defaultdict(float)
    for event in events:
        if not event.section:
            continue
        weights[event.section] += 1.0 if event.rating == "like" else -1.0
    return dict(weights)


def text_feedback_weights(events: list[FeedbackEvent]) -> dict[str, float]:
    weights: dict[str, float] = defaultdict(float)
    for event in events:
        text = " ".join([event.title, event.abstract])
        tokens = set(_tokens(text))
        if not tokens:
            continue
        direction = 1.0 if event.rating == "like" else -1.0
        for token in tokens:
            weights[token] += direction
    return {token: weight for token, weight in weights.items() if weight != 0}


def text_feedback_adjustment(text: str, weights: dict[str, float], scale: float = 0.25) -> float:
    if not weights:
        return 0.0
    return sum(weights.get(token, 0.0) for token in set(_tokens(text))) * scale


def fetch_feedback_events(
    supabase_url: str,
    service_role_key: str,
    limit: int = 500,
    opener: Callable[[Request], Any] = urlopen,
) -> list[FeedbackEvent]:
    base_url = supabase_url.rstrip("/")
    query = urlencode(
        {
            "select": "paper_id,rating,section,source,title,abstract,authors,affiliations,categories",
            "order": "created_at.desc",
            "limit": str(limit),
        }
    )
    request = Request(
        f"{base_url}/rest/v1/feedback_events?{query}",
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Accept": "application/json",
        },
    )
    with opener(request) as response:
        records = json.loads(response.read().decode("utf-8"))
    return feedback_events_from_records(records)


def write_feedback_json(events: list[FeedbackEvent], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        {
            "paper_id": event.paper_id,
            "rating": event.rating,
            "section": event.section,
            "source": event.source,
            "title": event.title,
            "abstract": event.abstract,
            "authors": list(event.authors),
            "affiliations": list(event.affiliations),
            "categories": list(event.categories),
        }
        for event in events
    ]
    output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Supabase feedback events into a JSON file.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--limit", type=int, default=500, help="Maximum feedback events to fetch.")
    args = parser.parse_args(argv)

    supabase_url = _required_env("SUPABASE_URL")
    service_role_key = _required_env("SUPABASE_SERVICE_ROLE_KEY")
    events = fetch_feedback_events(supabase_url, service_role_key, limit=args.limit)
    write_feedback_json(events, args.output)
    print(f"Wrote {len(events)} feedback events to {args.output}")
    return 0


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _tokens(text: str) -> list[str]:
    normalized = text.lower()
    raw_tokens = re.findall(r"[a-z0-9][a-z0-9.+#-]*", normalized)
    tokens = [token.strip(".,;:!?()[]{}\"'") for token in raw_tokens]
    return [token for token in tokens if len(token) >= 3 and token not in STOPWORDS and not token.isdigit()]


if __name__ == "__main__":
    raise SystemExit(main())
