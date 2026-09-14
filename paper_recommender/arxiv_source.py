"""Fetch and normalize arXiv Atom records into pipeline-compatible JSONL."""

from __future__ import annotations

import argparse
import json
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import re
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from paper_recommender.domain import InterestProfile, load_interest_profile


ARXIV_API_BASE_URL = "https://export.arxiv.org/api/query"
# rss.arxiv.org is a separate host from export.arxiv.org with its own rate
# limits, so it stays reachable when the API throttles CI egress IP ranges.
ARXIV_RSS_BASE_URL = "https://rss.arxiv.org/rss/{category}"
USER_AGENT = "agentic-arch-paper-recommender/0.1"
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


def fetch_atom_feed(
    url: str,
    timeout: int = 90,
    max_attempts: int = 6,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> str:
    """Fetch an arXiv API feed, retrying failures that are likely to be transient."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    return _fetch_text_with_retries(
        request,
        timeout=timeout,
        max_attempts=max_attempts,
        opener=opener,
        sleeper=sleeper,
        label="arXiv API",
    )


def fetch_rss_feed(
    url: str,
    timeout: int = 60,
    max_attempts: int = 3,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> str:
    """Fetch an rss.arxiv.org category feed with the same transient retry policy."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    request = Request(url, headers={"User-Agent": USER_AGENT})
    return _fetch_text_with_retries(
        request,
        timeout=timeout,
        max_attempts=max_attempts,
        opener=opener,
        sleeper=sleeper,
        label="arXiv RSS",
    )


def fetch_papers_via_rss(
    profile: InterestProfile,
    timeout: int = 60,
    max_attempts: int = 3,
    opener: Callable[..., Any] = urlopen,
    sleeper: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Collect recent arXiv records from per-category RSS feeds, deduped by paper id."""
    categories = sorted(profile.core_categories | profile.expansion_categories)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    feeds_ok = 0
    for category in categories:
        url = ARXIV_RSS_BASE_URL.format(category=category)
        try:
            feed_text = fetch_rss_feed(
                url,
                timeout=timeout,
                max_attempts=max_attempts,
                opener=opener,
                sleeper=sleeper,
            )
        except Exception as error:
            print(f"arXiv RSS feed {category} failed: {error}")
            continue
        feeds_ok += 1
        for record in parse_rss_feed(feed_text):
            paper_id = str(record.get("paper_id", ""))
            if not paper_id or paper_id in seen:
                continue
            seen.add(paper_id)
            records.append(record)
    if feeds_ok == 0:
        raise RuntimeError("all arXiv RSS feeds failed")
    records.sort(key=lambda record: str(record.get("published", "")), reverse=True)
    return records


def _fetch_text_with_retries(
    request: Request,
    timeout: int,
    max_attempts: int,
    opener: Callable[..., Any],
    sleeper: Callable[[float], None],
    label: str,
) -> str:
    for attempt in range(1, max_attempts + 1):
        try:
            with opener(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == max_attempts:
                raise
            retry_after = error.headers.get("Retry-After") if error.headers else None
            delay = _retry_delay(attempt, retry_after)
            print(
                f"{label} returned HTTP {error.code}; retrying in {delay:g}s "
                f"({attempt}/{max_attempts})"
            )
            sleeper(delay)
        except (TimeoutError, URLError, ConnectionError, OSError) as error:
            if attempt == max_attempts:
                raise
            delay = _retry_delay(attempt)
            print(
                f"{label} request failed ({error}); retrying in {delay:g}s "
                f"({attempt}/{max_attempts})"
            )
            sleeper(delay)
    raise RuntimeError("unreachable")


def _retry_delay(attempt: int, retry_after: str | None = None) -> float:
    if retry_after:
        try:
            return max(5.0, min(float(retry_after), 120.0))
        except ValueError:
            pass
    # arXiv rate limits shared CI egress IPs aggressively; back off long enough
    # (up to ~2.5 minutes total) for the throttle window to clear.
    return min(5.0 * (2 ** (attempt - 1)), 90.0)


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


def parse_rss_feed(feed_text: str) -> list[dict[str, Any]]:
    """Parse an rss.arxiv.org category feed into pipeline-compatible records."""
    root = ET.fromstring(feed_text)
    records: list[dict[str, Any]] = []
    for item in root.iter("item"):
        fields: dict[str, list[str]] = {}
        for child in item:
            name = child.tag.rsplit("}", 1)[-1]
            text = _normalize_text(child.text or "")
            if text:
                fields.setdefault(name, []).append(text)
        title = fields.get("title", [""])[0]
        link = fields.get("link", [""])[0]
        guid = fields.get("guid", [""])[0]
        description = fields.get("description", [""])[0]
        categories = fields.get("category", [])
        authors = _authors_from_creator(fields.get("creator", [""])[0])
        published = _iso_from_rfc822(fields.get("pubDate", [""])[0])
        paper_id = _paper_id_from_rss_item(guid=guid, link=link)
        abstract = _abstract_from_rss_description(description)
        records.append(
            {
                "paper_id": paper_id,
                "title": title,
                "abstract": abstract,
                "summary": abstract,
                "authors": authors,
                "affiliations": [],
                "categories": categories,
                "url": link or (f"https://arxiv.org/abs/{paper_id}" if paper_id else ""),
                "published": published,
                "updated": published,
            }
        )
    return [record for record in records if record["paper_id"]]


def fetch_atom_and_rss_records(
    profile: InterestProfile,
    max_results: int,
    start: int,
    api_timeout: int = 240,
    rss_timeout: int = 60,
) -> list[dict[str, Any]]:
    """Fetch from the export API, falling back to the RSS mirror when throttled."""
    try:
        feed_text = fetch_atom_feed(
            build_query_url(profile, max_results=max_results, start=start),
            timeout=api_timeout,
        )
        return parse_atom_feed(feed_text)
    except Exception as error:
        print(f"arXiv API fetch failed ({error}); falling back to the rss.arxiv.org mirror")
        return fetch_papers_via_rss(profile, timeout=rss_timeout)


def _authors_from_creator(creator: str) -> list[str]:
    return [author.strip() for author in creator.split(",") if author.strip()]


def _paper_id_from_rss_item(guid: str, link: str) -> str:
    raw_id = ""
    if guid:
        raw_id = guid.rstrip("/").rsplit(":", 1)[-1]
    elif link:
        raw_id = link.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"v\d+$", "", raw_id)


def _abstract_from_rss_description(description: str) -> str:
    marker = "Abstract:"
    position = description.find(marker)
    if position >= 0:
        return description[position + len(marker) :].strip()
    return re.sub(r"^arXiv:\S+\s*", "", description).strip()


def _iso_from_rfc822(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return ""
    if parsed is None:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_jsonl(records: list[dict[str, Any]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取 arXiv Atom 记录并写入论文 JSONL。")
    parser.add_argument("--profile", required=True, help="兴趣画像 JSON 路径。")
    parser.add_argument("--output", required=True, help="输出论文 JSONL 路径。")
    parser.add_argument("--max-results", type=int, default=200, help="最多抓取 arXiv 记录数。")
    parser.add_argument("--start", type=int, default=0, help="arXiv API 分页起点。")
    parser.add_argument("--source-file", default=None, help="从本地 Atom XML 文件读取，而不是访问 arXiv。")
    parser.add_argument(
        "--via",
        choices=("auto", "api", "rss"),
        default="auto",
        help="auto 先用 export API，失败时回退到 rss.arxiv.org 镜像。",
    )
    args = parser.parse_args(argv)

    profile = load_interest_profile(args.profile)
    if args.source_file:
        records = parse_atom_feed(Path(args.source_file).read_text(encoding="utf-8"))
    elif args.via == "api":
        # A 500-record Atom response is large and slow to read while arXiv is
        # throttling, so allow a long read window before treating it as a timeout.
        feed_text = fetch_atom_feed(
            build_query_url(profile, max_results=args.max_results, start=args.start),
            timeout=240,
        )
        records = parse_atom_feed(feed_text)
    elif args.via == "rss":
        records = fetch_papers_via_rss(profile)
    else:
        records = fetch_atom_and_rss_records(
            profile,
            max_results=args.max_results,
            start=args.start,
        )

    write_jsonl(records, args.output)
    print(f"已写入 {len(records)} 条 arXiv 记录到 {args.output}")
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
