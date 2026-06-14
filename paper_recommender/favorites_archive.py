"""Export liked recommendation feedback into a filesystem paper archive."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def fetch_liked_feedback_events(
    supabase_url: str,
    service_role_key: str,
    limit: int = 1000,
    opener: Callable[[Request], Any] = urlopen,
) -> list[dict[str, Any]]:
    select = "paper_id,rating,item_type,section,title,abstract,authors,affiliations,categories,repository_url,paper_links,created_at"
    legacy_select = "paper_id,rating,section,title,abstract,authors,affiliations,categories,created_at"
    try:
        return _fetch_liked_feedback_records(
            supabase_url,
            service_role_key,
            select=select,
            limit=limit,
            opener=opener,
        )
    except HTTPError as exc:
        if exc.code != 400:
            raise
        return _fetch_liked_feedback_records(
            supabase_url,
            service_role_key,
            select=legacy_select,
            limit=limit,
            opener=opener,
        )


def _fetch_liked_feedback_records(
    supabase_url: str,
    service_role_key: str,
    select: str,
    limit: int,
    opener: Callable[[Request], Any],
) -> list[dict[str, Any]]:
    base_url = supabase_url.rstrip("/")
    query = urlencode(
        {
            "select": select,
            "rating": "eq.like",
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
    return records if isinstance(records, list) else []


def export_favorites(
    records: list[dict[str, Any]],
    output_dir: str | Path,
    opener: Callable[..., Any] = urlopen,
    timeout: int = 60,
    command_runner: Callable[[list[str], Path], None] | None = None,
) -> int:
    root = Path(output_dir)
    run_command = command_runner or _run_command
    written = 0
    for record in records:
        if str(record.get("rating", "")).lower() != "like":
            continue
        paper_id = str(record.get("paper_id", "")).strip()
        if not paper_id:
            continue

        month = _month_from_created_at(record.get("created_at"))
        section = _archive_section(record)
        folder = root / month / slugify(section)
        folder.mkdir(parents=True, exist_ok=True)

        stem = slugify(paper_id)
        metadata = _metadata(record)
        if metadata["item_type"] == "repository":
            try:
                _add_repository_submodule(root, metadata["repository_url"], command_runner=run_command)
            except Exception as exc:
                metadata["submodule_error"] = str(exc)
        else:
            pdf_url = paper_pdf_url(paper_id)
            metadata["pdf_url"] = pdf_url
            if pdf_url:
                pdf_path = folder / f"{stem}.pdf"
                try:
                    _download_pdf(pdf_url, pdf_path, opener=opener, timeout=timeout)
                except Exception as exc:  # Download should not block metadata archival.
                    metadata["download_error"] = str(exc)

        (folder / f"{stem}.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written += 1
    return written


def paper_pdf_url(paper_id: str) -> str:
    value = str(paper_id).strip()
    if value.lower().startswith("arxiv:"):
        value = value.split(":", 1)[1].strip()
    if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?", value, flags=re.IGNORECASE):
        return ""
    return f"https://arxiv.org/pdf/{value}.pdf"


def slugify(value: str) -> str:
    normalized = str(value).strip().lower()
    normalized = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    normalized = normalized.strip("-._")
    return normalized or "untitled"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导出喜欢的论文到收藏仓库。")
    parser.add_argument("--output-dir", required=True, help="收藏仓库工作区目录。")
    parser.add_argument("--limit", type=int, default=1000, help="最多读取喜欢反馈数。")
    args = parser.parse_args(argv)

    records = fetch_liked_feedback_events(
        _required_env("SUPABASE_URL"),
        _required_env("SUPABASE_SERVICE_ROLE_KEY"),
        limit=args.limit,
    )
    written = export_favorites(records, args.output_dir)
    print(f"已导出 {written} 篇喜欢论文到收藏仓库")
    return 0


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    paper_id = str(record.get("paper_id", "")).strip()
    repository_url = str(record.get("repository_url", "")).strip() or _repository_url_from_paper_id(paper_id)
    item_type = _item_type(record.get("item_type"), repository_url, paper_id)
    return {
        "paper_id": paper_id,
        "item_type": item_type,
        "title": str(record.get("title", "")).strip(),
        "abstract": str(record.get("abstract", "")).strip(),
        "authors": _string_list(record.get("authors", [])),
        "affiliations": _string_list(record.get("affiliations", [])),
        "categories": _string_list(record.get("categories", [])),
        "section": str(record.get("section", "")).strip(),
        "rating": "like",
        "created_at": str(record.get("created_at", "")).strip(),
        "arxiv_url": f"https://arxiv.org/abs/{paper_id}" if paper_pdf_url(paper_id) else "",
        "repository_url": repository_url,
        "paper_links": _paper_links(record.get("paper_links", [])),
    }


def _download_pdf(
    pdf_url: str,
    pdf_path: Path,
    opener: Callable[..., Any],
    timeout: int,
) -> None:
    request = Request(pdf_url, headers={"User-Agent": "agentic-arch-paper-recommender/1.0"})
    try:
        response_context = opener(request, timeout=timeout)
    except TypeError:
        response_context = opener(request)
    with response_context as response:
        pdf_path.write_bytes(response.read())


def _month_from_created_at(value: Any) -> str:
    text = str(value or "").strip()
    if re.match(r"^\d{4}-\d{2}", text):
        return text[:7]
    return "unknown-month"


def _archive_section(record: dict[str, Any]) -> str:
    section = str(record.get("section", "")).strip()
    if section:
        return section
    categories = _string_list(record.get("categories", []))
    return categories[0] if categories else "uncategorized"


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _paper_links(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    links: list[dict[str, str]] = []
    seen = set()
    for item in value:
        if isinstance(item, dict):
            url = str(item.get("url", "")).strip()
            label = str(item.get("label", "Paper")).strip() or "Paper"
        else:
            url = str(item).strip()
            label = "Paper"
        if not url or url in seen:
            continue
        seen.add(url)
        links.append({"label": label, "url": url})
    return links


def _item_type(value: Any, repository_url: Any = "", paper_id: str = "") -> str:
    text = str(value or "").strip().lower()
    if text == "repository" or str(repository_url or "").strip() or str(paper_id).startswith("repo:"):
        return "repository"
    return "paper"


def _repository_url_from_paper_id(paper_id: str) -> str:
    value = str(paper_id or "").strip()
    if not value.startswith("repo:"):
        return ""
    full_name = value.split(":", 1)[1].strip("/")
    if not re.fullmatch(r"[^/\s]+/[^/\s]+", full_name):
        return ""
    return f"https://github.com/{full_name}"


def _add_repository_submodule(
    root: Path,
    repository_url: str,
    command_runner: Callable[[list[str], Path], None],
) -> None:
    url = str(repository_url or "").strip()
    if not url:
        return
    path = Path("repositories") / _repository_slug(url)
    if (root / path).exists():
        return
    (root / path.parent).mkdir(parents=True, exist_ok=True)
    command_runner(["git", "submodule", "add", url, path.as_posix()], root)


def _repository_slug(repository_url: str) -> str:
    match = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", repository_url)
    if match:
        return slugify(f"{match.group(1)}-{match.group(2)}")
    return slugify(repository_url)


def _run_command(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"缺少必要环境变量：{name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
