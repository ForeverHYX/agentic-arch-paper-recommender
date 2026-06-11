"""Recommendation history helpers for repeat-aware daily ranking."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class RecommendationRun:
    paper_id: str
    run_date: str
    rank: int
    score: float
    section: str
    shown_in_email: bool = False
    shown_on_page: bool = True
    payload: dict[str, Any] | None = None


def history_counts(runs: list[RecommendationRun]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in runs:
        counts[run.paper_id] = counts.get(run.paper_id, 0) + 1
    return counts


def load_history_json(path: str | Path) -> list[RecommendationRun]:
    return recommendation_runs_from_records(json.loads(Path(path).read_text(encoding="utf-8")))


def write_history_json(runs: list[RecommendationRun], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([_run_record(run) for run in runs], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def recommendation_runs_from_records(records: list[dict[str, Any]]) -> list[RecommendationRun]:
    runs: list[RecommendationRun] = []
    for record in records:
        paper_id = str(record.get("paper_id", "")).strip()
        if not paper_id:
            continue
        runs.append(
            RecommendationRun(
                paper_id=paper_id,
                run_date=str(record.get("run_date", "")).strip(),
                rank=int(record.get("rank", 0) or 0),
                score=float(record.get("score", 0.0) or 0.0),
                section=str(record.get("section", "") or ""),
                shown_in_email=bool(record.get("shown_in_email", False)),
                shown_on_page=bool(record.get("shown_on_page", True)),
                payload=record.get("payload") if isinstance(record.get("payload"), dict) and record.get("payload") else None,
            )
        )
    return runs


def recommendation_runs_from_payload(
    payload: dict[str, Any],
    shown_in_email: bool = False,
    shown_on_page: bool = True,
) -> list[RecommendationRun]:
    run_date = str(payload.get("run_date", "")).strip()
    runs: list[RecommendationRun] = []
    for item in payload.get("recommendations", []):
        paper_id = str(item.get("paper_id", "")).strip()
        if not paper_id:
            continue
        sections = item.get("sections") or []
        runs.append(
            RecommendationRun(
                paper_id=paper_id,
                run_date=run_date,
                rank=int(item.get("rank", 0) or 0),
                score=float(item.get("score", 0.0) or 0.0),
                section=str(sections[0] if sections else ""),
                shown_in_email=shown_in_email,
                shown_on_page=shown_on_page,
                payload=item,
            )
        )
    return runs


def fetch_recommendation_history(
    supabase_url: str,
    service_role_key: str,
    limit: int = 1000,
    opener: Callable[[Request], Any] = urlopen,
) -> list[RecommendationRun]:
    base_url = supabase_url.rstrip("/")
    query = urlencode(
        {
            "select": "paper_id,run_date,rank,score,section,shown_in_email,shown_on_page,payload",
            "order": "created_at.desc",
            "limit": str(limit),
        }
    )
    request = Request(
        f"{base_url}/rest/v1/recommendation_runs?{query}",
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Accept": "application/json",
        },
    )
    with opener(request) as response:
        records = json.loads(response.read().decode("utf-8"))
    return recommendation_runs_from_records(records)


def publish_recommendation_runs(
    supabase_url: str,
    service_role_key: str,
    payload: dict[str, Any],
    shown_in_email: bool = False,
    shown_on_page: bool = True,
    opener: Callable[[Request], Any] = urlopen,
) -> None:
    runs = recommendation_runs_from_payload(payload, shown_in_email=shown_in_email, shown_on_page=shown_on_page)
    if not runs:
        return
    base_url = supabase_url.rstrip("/")
    query = urlencode({"on_conflict": "run_date,paper_id"})
    request = Request(
        f"{base_url}/rest/v1/recommendation_runs?{query}",
        data=json.dumps([_run_record(run) for run in runs], ensure_ascii=False).encode("utf-8"),
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        method="POST",
    )
    with opener(request):
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch or publish Supabase recommendation history.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch recommendation history into JSON.")
    fetch_parser.add_argument("--output", required=True, help="Output JSON path.")
    fetch_parser.add_argument("--limit", type=int, default=1000, help="Maximum rows to fetch.")

    publish_parser = subparsers.add_parser("publish", help="Publish recommendation JSON to history.")
    publish_parser.add_argument("--recommendations", required=True, help="Recommendation JSON path.")
    publish_parser.add_argument("--shown-in-email", action="store_true", help="Mark rows as shown in email.")
    publish_parser.add_argument("--no-shown-on-page", action="store_true", help="Mark rows as not shown on page.")

    args = parser.parse_args(argv)
    supabase_url = _required_env("SUPABASE_URL")
    service_role_key = _required_env("SUPABASE_SERVICE_ROLE_KEY")

    if args.command == "fetch":
        runs = fetch_recommendation_history(supabase_url, service_role_key, limit=args.limit)
        write_history_json(runs, args.output)
        print(f"Wrote {len(runs)} recommendation history rows to {args.output}")
        return 0

    payload = json.loads(Path(args.recommendations).read_text(encoding="utf-8"))
    publish_recommendation_runs(
        supabase_url,
        service_role_key,
        payload,
        shown_in_email=args.shown_in_email,
        shown_on_page=not args.no_shown_on_page,
    )
    print(f"Published {len(payload.get('recommendations', []))} recommendation history rows")
    return 0


def _run_record(run: RecommendationRun) -> dict[str, Any]:
    return {
        "paper_id": run.paper_id,
        "run_date": run.run_date,
        "rank": run.rank,
        "score": run.score,
        "section": run.section,
        "shown_in_email": run.shown_in_email,
        "shown_on_page": run.shown_on_page,
        "payload": run.payload or {},
    }


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
