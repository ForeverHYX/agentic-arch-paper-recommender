"""Fetch and normalize arXiv Atom records into pipeline-compatible JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from paper_recommender.domain import InterestProfile, load_interest_profile


ARXIV_API_BASE_URL = "http://export.arxiv.org/api/query"
ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def build_query_url(
    profile: InterestProfile,
    max_results: int = 200,
    start: int = 0,
    base_url: str = ARXIV_API_BASE_URL,
) -> str:
    categories = sorted(profile.core_categories | profile.expansion_categories)
    search_query = " OR ".join(f"cat:{category}" for category in categories)
    query = urlencode(
        {
            "search_query": search_query,
            "start": start,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    return f"{base_url}?{query}"


def fetch_atom_feed(url: str, timeout: int = 30) -> str:
    request = Request(url, headers={"User-Agent": "agentic-arch-paper-recommender/0.1"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def parse_atom_feed(feed_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(feed_text)
    records: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        entry_id = _entry_text(entry, "id")
        title = _entry_text(entry, "title")
        summary = _entry_text(entry, "summary")
        authors = []
        affiliations = []
        for author in entry.findall("atom:author", ATOM_NS):
            name = author.find("atom:name", ATOM_NS)
            normalized_name = _normalize_text(name.text or "") if name is not None else ""
            if normalized_name:
                authors.append(normalized_name)
            for affiliation in author.findall("arxiv:affiliation", ATOM_NS):
                normalized_affiliation = _normalize_text(affiliation.text or "")
                if normalized_affiliation:
                    affiliations.append(normalized_affiliation)
        categories = [
            str(category.attrib.get("term", "")).strip()
            for category in entry.findall("atom:category", ATOM_NS)
            if str(category.attrib.get("term", "")).strip()
        ]
        records.append(
            {
                "paper_id": _paper_id_from_entry_id(entry_id),
                "title": title,
                "abstract": summary,
                "summary": summary,
                "authors": authors,
                "affiliations": _dedupe(affiliations),
                "categories": categories,
                "url": _entry_url(entry, entry_id),
                "published": _entry_text(entry, "published"),
                "updated": _entry_text(entry, "updated"),
            }
        )
    return records


def write_jsonl(records: list[dict[str, Any]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch arXiv Atom records and write paper JSONL.")
    parser.add_argument("--profile", required=True, help="Interest profile JSON path.")
    parser.add_argument("--output", required=True, help="Output paper JSONL path.")
    parser.add_argument("--max-results", type=int, default=200, help="Maximum arXiv records to fetch.")
    parser.add_argument("--start", type=int, default=0, help="Start offset for arXiv API pagination.")
    parser.add_argument("--source-file", default=None, help="Read Atom XML from a local file instead of arXiv.")
    args = parser.parse_args(argv)

    profile = load_interest_profile(args.profile)
    if args.source_file:
        feed_text = Path(args.source_file).read_text(encoding="utf-8")
    else:
        feed_text = fetch_atom_feed(build_query_url(profile, max_results=args.max_results, start=args.start))

    records = parse_atom_feed(feed_text)
    write_jsonl(records, args.output)
    print(f"Wrote {len(records)} arXiv records to {args.output}")
    return 0


def _entry_text(entry: ET.Element, tag_name: str) -> str:
    element = entry.find(f"atom:{tag_name}", ATOM_NS)
    if element is None or element.text is None:
        return ""
    return _normalize_text(element.text)


def _entry_url(entry: ET.Element, fallback: str) -> str:
    for link in entry.findall("atom:link", ATOM_NS):
        if link.attrib.get("rel") == "alternate" and link.attrib.get("href"):
            return str(link.attrib["href"])
    for link in entry.findall("atom:link", ATOM_NS):
        if link.attrib.get("href"):
            return str(link.attrib["href"])
    return fallback


def _paper_id_from_entry_id(entry_id: str) -> str:
    raw_id = entry_id.rstrip("/").split("/")[-1]
    return re.sub(r"v\d+$", "", raw_id)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
