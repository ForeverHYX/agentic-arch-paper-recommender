"""Affiliation enrichment from arXiv source archives."""

from __future__ import annotations

import argparse
import gzip
import io
import json
from pathlib import Path
import re
import tarfile
from typing import Any, Callable
from urllib.request import Request, urlopen


ARXIV_EPRINT_URL = "https://arxiv.org/e-print/{paper_id}"
AFFILIATION_MACROS = ("affil", "affiliation", "institute")


def extract_affiliations_from_latex(text: str) -> list[str]:
    without_comments = _strip_latex_comments(text)
    affiliations: list[str] = []
    for macro in AFFILIATION_MACROS:
        affiliations.extend(_extract_macro_arguments(without_comments, macro))
    return _dedupe(_clean_affiliation(value) for value in affiliations)


def extract_affiliations_from_source_archive(data: bytes) -> list[str]:
    affiliations: list[str] = []
    for text in _source_texts(data):
        affiliations.extend(extract_affiliations_from_latex(text))
    return _dedupe(affiliations)


def fetch_arxiv_source(
    paper_id: str,
    opener: Callable[..., Any] = urlopen,
    timeout: int = 30,
) -> bytes:
    clean_id = _clean_paper_id(paper_id)
    request = Request(
        ARXIV_EPRINT_URL.format(paper_id=clean_id),
        headers={"User-Agent": "agentic-arch-paper-recommender/0.1"},
    )
    try:
        response_context = opener(request, timeout=timeout)
    except TypeError:
        response_context = opener(request)
    with response_context as response:
        return response.read()


def enrich_payload_with_affiliations(
    payload: dict[str, Any],
    fetcher: Callable[[str], bytes] = fetch_arxiv_source,
    max_items: int = 15,
) -> dict[str, Any]:
    enriched = dict(payload)
    recommendations = []
    attempted = 0
    enriched_count = 0
    failed_count = 0

    for item in payload.get("recommendations", []):
        updated = dict(item)
        current = _string_list(updated.get("affiliations", []))
        if current or attempted >= max_items:
            updated["affiliations"] = current
            recommendations.append(updated)
            continue

        paper_id = str(updated.get("paper_id", "")).strip()
        if not paper_id:
            updated["affiliations"] = []
            recommendations.append(updated)
            continue

        attempted += 1
        try:
            affiliations = extract_affiliations_from_source_archive(fetcher(paper_id))
        except Exception:
            affiliations = []
            failed_count += 1
        if affiliations:
            enriched_count += 1
            updated["affiliations"] = affiliations
        else:
            updated["affiliations"] = []
        recommendations.append(updated)

    enriched["recommendations"] = recommendations
    enriched["affiliation_summary"] = {
        "source": "arxiv-eprint",
        "attempted_count": attempted,
        "enriched_count": enriched_count,
        "failed_count": failed_count,
    }
    return enriched


def main(argv: list[str] | None = None, fetcher: Callable[[str], bytes] = fetch_arxiv_source) -> int:
    parser = argparse.ArgumentParser(description="Enrich recommendation JSON with author affiliations from arXiv sources.")
    parser.add_argument("--input", required=True, help="Input recommendation JSON path.")
    parser.add_argument("--output", required=True, help="Output recommendation JSON path.")
    parser.add_argument("--max-items", type=int, default=15, help="Maximum papers to query from arXiv e-print.")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    enriched = enrich_payload_with_affiliations(payload, fetcher=fetcher, max_items=args.max_items)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = enriched["affiliation_summary"]
    print(
        "Enriched "
        f"{summary['enriched_count']} of {summary['attempted_count']} recommendations "
        "with affiliations"
    )
    return 0


def _source_texts(data: bytes) -> list[str]:
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
            texts = []
            for member in archive.getmembers():
                if not member.isfile() or not member.name.lower().endswith(".tex"):
                    continue
                handle = archive.extractfile(member)
                if handle is None:
                    continue
                texts.append(handle.read().decode("utf-8", errors="ignore"))
            if texts:
                return texts
    except tarfile.TarError:
        pass

    try:
        return [gzip.decompress(data).decode("utf-8", errors="ignore")]
    except (OSError, EOFError):
        return [data.decode("utf-8", errors="ignore")]


def _extract_macro_arguments(text: str, macro: str) -> list[str]:
    pattern = re.compile(rf"\\{re.escape(macro)}\s*(?:\[[^\]]*\]\s*)?\{{", re.IGNORECASE)
    values = []
    for match in pattern.finditer(text):
        start = match.end() - 1
        value = _balanced_brace_value(text, start)
        if value:
            values.append(value)
    return values


def _balanced_brace_value(text: str, brace_index: int) -> str:
    depth = 0
    value_start = brace_index + 1
    index = brace_index
    while index < len(text):
        char = text[index]
        previous = text[index - 1] if index > 0 else ""
        if char == "{" and previous != "\\":
            depth += 1
        elif char == "}" and previous != "\\":
            depth -= 1
            if depth == 0:
                return text[value_start:index]
        index += 1
    return ""


def _strip_latex_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        lines.append(re.sub(r"(?<!\\)%.*", "", line))
    return "\n".join(lines)


def _clean_affiliation(value: str) -> str:
    cleaned = _remove_macro_arguments(value, "email")
    cleaned = _remove_macro_arguments(cleaned, "thanks")
    cleaned = re.sub(r"\\(?:and|quad|qquad|,|;)", " ", cleaned)
    cleaned = re.sub(r"\\(?:textsuperscript|thanks|email)\s*\{[^{}]*\}", " ", cleaned)
    cleaned = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", cleaned)
    cleaned = cleaned.replace("\\", " ")
    cleaned = cleaned.replace("~", " ")
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" ,;.")


def _remove_macro_arguments(text: str, macro: str) -> str:
    pattern = re.compile(rf"\\{re.escape(macro)}\s*(?:\[[^\]]*\]\s*)?\{{", re.IGNORECASE)
    result = []
    last = 0
    for match in pattern.finditer(text):
        start = match.start()
        brace_index = match.end() - 1
        end = _balanced_brace_end(text, brace_index)
        if end is None:
            continue
        result.append(text[last:start])
        last = end + 1
    result.append(text[last:])
    return "".join(result)


def _balanced_brace_end(text: str, brace_index: int) -> int | None:
    depth = 0
    index = brace_index
    while index < len(text):
        char = text[index]
        previous = text[index - 1] if index > 0 else ""
        if char == "{" and previous != "\\":
            depth += 1
        elif char == "}" and previous != "\\":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(";") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _clean_paper_id(paper_id: str) -> str:
    clean = paper_id.rstrip("/").split("/")[-1]
    return re.sub(r"v\d+$", "", clean)


def _dedupe(values) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
