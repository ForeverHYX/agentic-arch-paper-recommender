"""GitHub Trending repository source for daily recommendations."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import date, timedelta
from html import unescape
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from paper_recommender.domain import InterestProfile, classify_paper, load_interest_profile
from paper_recommender.pipeline import paper_from_record
from paper_recommender.summarizer import DEFAULT_USER_AGENT


TRENDING_URL = "https://github.com/trending"
GITHUB_API_URL = "https://api.github.com"
SEARCH_FALLBACK_QUERIES = (
    "llm inference serving",
    "cuda gpu inference",
    "ai infrastructure runtime",
    "mlir compiler accelerator",
    "triton quantization inference",
    "distributed training gpu",
    "gem5 microarchitecture",
    "risc-v accelerator",
    "systemverilog rtl",
    "memory hierarchy simulator",
)


@dataclass(frozen=True)
class TrendingRepository:
    full_name: str
    url: str
    description: str = ""
    language: str = ""
    stars: int = 0
    forks: int = 0
    stars_today: int = 0


def parse_trending_repositories(html: str, limit: int | None = None) -> list[TrendingRepository]:
    repositories: list[TrendingRepository] = []
    for block in _article_blocks(html):
        repo_match = re.search(
            r'<h2\b[^>]*>.*?<a\b[^>]*href="/([^"/?#]+/[^"/?#]+)"',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not repo_match:
            continue
        full_name = unescape(repo_match.group(1)).strip("/")
        if "/" not in full_name:
            continue
        repositories.append(
            TrendingRepository(
                full_name=full_name,
                url=f"https://github.com/{full_name}",
                description=_description_from_block(block),
                language=_language_from_block(block),
                stars=_count_for_repo_link(block, full_name, ("stargazers",)),
                forks=_count_for_repo_link(block, full_name, ("forks", "network/members")),
                stars_today=_stars_today_from_block(block),
            )
        )
        if limit is not None and len(repositories) >= limit:
            break
    return repositories


def extract_paper_links(text: str) -> list[dict[str, str]]:
    patterns = (
        ("arXiv", r"https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/[^\s<>\]\[{}()\"']+"),
        ("OpenReview", r"https?://(?:www\.)?openreview\.net/[^\s<>\]\[{}()\"']+"),
        ("DOI", r"https?://(?:dx\.)?doi\.org/10\.[^\s<>\]\[{}()\"']+"),
    )
    links: list[dict[str, str]] = []
    seen = set()
    for label, pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            url = match.group(0).rstrip(".,;:)]}")
            if not url or url in seen:
                continue
            seen.add(url)
            links.append({"label": label, "url": url})
    return links


def repository_records_from_trending_html(
    html: str,
    profile: InterestProfile | None = None,
    metadata_fetcher: Callable[[str], dict[str, Any]] | None = None,
    readme_fetcher: Callable[[str], str] | None = None,
    limit: int = 25,
    readme_chars: int = 6000,
) -> list[dict[str, Any]]:
    return repository_records_from_repositories(
        parse_trending_repositories(html),
        profile=profile,
        metadata_fetcher=metadata_fetcher,
        readme_fetcher=readme_fetcher,
        limit=limit,
        readme_chars=readme_chars,
    )


def repository_records_from_search_results(
    results: list[dict[str, Any]],
    profile: InterestProfile | None = None,
    readme_fetcher: Callable[[str], str] | None = None,
    limit: int = 25,
    readme_chars: int = 6000,
) -> list[dict[str, Any]]:
    repositories = []
    metadata_by_name: dict[str, dict[str, Any]] = {}
    for item in results:
        repo = _repository_from_search_result(item)
        if not repo:
            continue
        repositories.append(repo)
        metadata_by_name[repo.full_name] = item
    return repository_records_from_repositories(
        repositories,
        profile=profile,
        metadata_fetcher=lambda full_name: metadata_by_name.get(full_name, {}),
        readme_fetcher=readme_fetcher,
        limit=limit,
        readme_chars=readme_chars,
    )


def repository_records_from_repositories(
    repositories: list[TrendingRepository],
    profile: InterestProfile | None = None,
    metadata_fetcher: Callable[[str], dict[str, Any]] | None = None,
    readme_fetcher: Callable[[str], str] | None = None,
    limit: int = 25,
    readme_chars: int = 6000,
) -> list[dict[str, Any]]:
    resolved_profile = profile or load_interest_profile()
    fetch_metadata = metadata_fetcher or (lambda full_name: {})
    fetch_readme = readme_fetcher or (lambda full_name: "")
    records: list[dict[str, Any]] = []
    for repo in repositories:
        metadata = _safe_fetch_metadata(repo.full_name, fetch_metadata)
        readme = _safe_fetch_readme(repo.full_name, fetch_readme)
        record = repository_record(repo, metadata=metadata, readme_text=readme, readme_chars=readme_chars)
        classification = classify_paper(paper_from_record(record), profile=resolved_profile)
        if not classification.accepted:
            continue
        records.append(record)
        if len(records) >= limit:
            break
    return records


def repository_record(
    repo: TrendingRepository,
    metadata: dict[str, Any] | None = None,
    readme_text: str = "",
    readme_chars: int = 6000,
) -> dict[str, Any]:
    resolved_metadata = metadata or {}
    full_name = str(resolved_metadata.get("full_name") or repo.full_name)
    owner = full_name.split("/", 1)[0]
    description = _clean_text(str(resolved_metadata.get("description") or repo.description or "").strip())
    language = str(resolved_metadata.get("language") or repo.language or "").strip()
    topics = _string_list(resolved_metadata.get("topics", []))
    homepage = str(resolved_metadata.get("homepage") or "").strip()
    pushed_at = str(resolved_metadata.get("pushed_at") or "").strip()
    stars = _int_value(resolved_metadata.get("stargazers_count"), repo.stars)
    forks = _int_value(resolved_metadata.get("forks_count"), repo.forks)
    readme_excerpt = _clean_text(readme_text)[:readme_chars]
    abstract = "\n\n".join(part for part in [description, readme_excerpt] if part)
    paper_links = extract_paper_links(" ".join([description, readme_text, homepage]))
    url = str(resolved_metadata.get("html_url") or repo.url)
    categories = ["github"]
    if language:
        categories.append(language)
    categories.extend(topics)
    return {
        "paper_id": f"repo:{full_name}",
        "item_type": "repository",
        "source": "github_trending",
        "title": full_name,
        "abstract": abstract,
        "authors": [owner],
        "categories": categories,
        "url": url,
        "code_urls": [url],
        "repository_url": url,
        "repository_full_name": full_name,
        "repository_stars": stars,
        "repository_forks": forks,
        "repository_stars_today": repo.stars_today,
        "repository_language": language,
        "repository_topics": topics,
        "repository_pushed_at": pushed_at,
        "repository_homepage": homepage,
        "paper_links": paper_links,
    }


def fetch_trending_html(since: str = "daily", opener: Callable[..., Any] = urlopen, timeout: int = 60) -> str:
    request = Request(
        f"{TRENDING_URL}?since={since}",
        headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "text/html"},
    )
    try:
        response_context = opener(request, timeout=timeout)
    except TypeError:
        response_context = opener(request)
    with response_context as response:
        return response.read().decode("utf-8", "replace")


def fetch_repository_metadata(
    full_name: str,
    token: str = "",
    opener: Callable[..., Any] = urlopen,
    timeout: int = 60,
) -> dict[str, Any]:
    payload = _fetch_github_json(f"{GITHUB_API_URL}/repos/{full_name}", token=token, opener=opener, timeout=timeout)
    return payload if isinstance(payload, dict) else {}


def fetch_repository_readme(
    full_name: str,
    token: str = "",
    opener: Callable[..., Any] = urlopen,
    timeout: int = 60,
) -> str:
    payload = _fetch_github_json(f"{GITHUB_API_URL}/repos/{full_name}/readme", token=token, opener=opener, timeout=timeout)
    if not isinstance(payload, dict):
        return ""
    if payload.get("encoding") != "base64" or not payload.get("content"):
        return ""
    return base64.b64decode(str(payload["content"])).decode("utf-8", "replace")


def fetch_repository_search_results(
    token: str = "",
    limit: int = 40,
    days: int = 7,
    opener: Callable[..., Any] = urlopen,
    timeout: int = 60,
) -> list[dict[str, Any]]:
    pushed_since = (date.today() - timedelta(days=days)).isoformat()
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_page = min(10, max(5, limit))
    for query in SEARCH_FALLBACK_QUERIES:
        search_query = quote_plus(f"{query} pushed:>={pushed_since}")
        payload = _fetch_github_json(
            f"{GITHUB_API_URL}/search/repositories?q={search_query}&sort=stars&order=desc&per_page={per_page}",
            token=token,
            opener=opener,
            timeout=timeout,
        )
        if not isinstance(payload, dict):
            continue
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            full_name = str(item.get("full_name", "")).strip()
            if not full_name or full_name in seen:
                continue
            seen.add(full_name)
            results.append(item)
            if len(results) >= limit:
                return results
    return results


def write_records_jsonl(records: list[dict[str, Any]], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取 GitHub Trending 仓库并输出推荐候选 JSONL。")
    parser.add_argument("--output", required=True, help="输出 JSONL 路径。")
    parser.add_argument("--profile", default=None, help="兴趣画像 JSON 路径。")
    parser.add_argument("--limit", type=int, default=25, help="最多输出相关仓库数。")
    parser.add_argument("--since", default="daily", choices=("daily", "weekly", "monthly"), help="Trending 时间窗口。")
    parser.add_argument("--source-file", default=None, help="本地 GitHub Trending HTML，用于测试或离线运行。")
    parser.add_argument("--readme-chars", type=int, default=6000, help="用于分类和摘要的 README 最大字符数。")
    args = parser.parse_args(argv)

    profile = load_interest_profile(args.profile) if args.profile else None
    token = os.environ.get("GITHUB_TOKEN", "")
    records: list[dict[str, Any]] = []
    try:
        html = Path(args.source_file).read_text(encoding="utf-8") if args.source_file else fetch_trending_html(args.since)
        repositories = parse_trending_repositories(html)
        if repositories:
            records = repository_records_from_repositories(
                repositories,
                profile=profile,
                metadata_fetcher=lambda full_name: fetch_repository_metadata(full_name, token=token),
                readme_fetcher=lambda full_name: fetch_repository_readme(full_name, token=token),
                limit=args.limit,
                readme_chars=args.readme_chars,
            )
        else:
            print("GitHub Trending 页面未返回仓库列表，尝试 GitHub Search fallback。")
    except Exception as exc:
        print(f"GitHub Trending 抓取失败，尝试 GitHub Search fallback：{exc}")
    if not records:
        try:
            search_results = fetch_repository_search_results(token=token, limit=max(args.limit * 6, args.limit))
            records = repository_records_from_search_results(
                search_results,
                profile=profile,
                readme_fetcher=lambda full_name: fetch_repository_readme(full_name, token=token),
                limit=args.limit,
                readme_chars=args.readme_chars,
            )
        except Exception as exc:
            print(f"GitHub Search fallback 抓取失败，写入空仓库候选：{exc}")
            records = []
    write_records_jsonl(records, args.output)
    print(f"已写入 {len(records)} 个 GitHub Trending 仓库候选到 {args.output}")
    return 0


def _article_blocks(html: str) -> list[str]:
    return re.findall(
        r'<article\b[^>]*class="[^"]*\bBox-row\b[^"]*"[^>]*>.*?</article>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _description_from_block(block: str) -> str:
    match = re.search(r"<p\b[^>]*>(.*?)</p>", block, flags=re.IGNORECASE | re.DOTALL)
    return _clean_html(match.group(1)) if match else ""


def _language_from_block(block: str) -> str:
    match = re.search(r'itemprop="programmingLanguage"[^>]*>(.*?)</span>', block, flags=re.IGNORECASE | re.DOTALL)
    return _clean_html(match.group(1)) if match else ""


def _count_for_repo_link(block: str, full_name: str, suffixes: tuple[str, ...]) -> int:
    for suffix in suffixes:
        pattern = rf'href="/{re.escape(full_name)}/{re.escape(suffix)}"[^>]*>.*?([0-9][0-9,]*)\s*</a>'
        match = re.search(pattern, block, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _int_value(match.group(1), 0)
    return 0


def _stars_today_from_block(block: str) -> int:
    match = re.search(r"([0-9][0-9,]*)\s+stars?\s+today", block, flags=re.IGNORECASE)
    return _int_value(match.group(1), 0) if match else 0


def _clean_html(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(unescape(without_tags).split())


def _clean_text(value: str) -> str:
    text = unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    return " ".join(text.split())


def _safe_fetch_metadata(full_name: str, fetcher: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    try:
        metadata = fetcher(full_name)
    except Exception:
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _safe_fetch_readme(full_name: str, fetcher: Callable[[str], str]) -> str:
    try:
        return str(fetcher(full_name) or "")
    except Exception:
        return ""


def _repository_from_search_result(item: dict[str, Any]) -> TrendingRepository | None:
    full_name = str(item.get("full_name", "")).strip()
    if "/" not in full_name:
        return None
    return TrendingRepository(
        full_name=full_name,
        url=str(item.get("html_url") or f"https://github.com/{full_name}"),
        description=_clean_text(str(item.get("description") or "")),
        language=str(item.get("language") or "").strip(),
        stars=_int_value(item.get("stargazers_count"), 0),
        forks=_int_value(item.get("forks_count"), 0),
        stars_today=0,
    )


def _fetch_github_json(
    url: str,
    token: str,
    opener: Callable[..., Any],
    timeout: int,
) -> Any:
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        response_context = opener(request, timeout=timeout)
    except TypeError:
        response_context = opener(request)
    with response_context as response:
        return json.loads(response.read().decode("utf-8"))


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _int_value(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return int(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    raise SystemExit(main())
