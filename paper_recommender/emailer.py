"""Email rendering helpers for recommendation digests."""

from __future__ import annotations

from collections import defaultdict
from html import escape
from typing import Any
from urllib.parse import urlencode


SECTION_LABELS = {
    "agentic_architecture": "Agentic Architecture / Auto-DSE",
    "full_stack_codesign": "Full-stack HW/SW Co-design",
    "microarchitecture_simulators": "CPU/GPU Microarchitecture and Simulators",
    "hpc_cross_over": "HPC x Architecture / Compiler / Runtime",
}
FALLBACK_SECTION = "Exploratory but Maybe Relevant"


def render_email_html(
    payload: dict[str, Any],
    site_base_url: str,
    feedback_base_url: str,
) -> str:
    run_date = escape(str(payload.get("run_date", "")))
    grouped = _group_recommendations(payload.get("recommendations", []))

    sections_html = []
    for section_key, recommendations in grouped.items():
        section_label = escape(SECTION_LABELS.get(section_key, FALLBACK_SECTION))
        items_html = "\n".join(
            _render_recommendation_item(item, site_base_url, feedback_base_url)
            for item in recommendations
        )
        sections_html.append(f"<h2>{section_label}</h2>\n<ol>{items_html}</ol>")

    body = "\n".join(sections_html) or "<p>No matching papers today.</p>"
    return f"""<!doctype html>
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5;">
    <h1>Daily Architecture Paper Recommendations - {run_date}</h1>
    {body}
  </body>
</html>
"""


def _group_recommendations(recommendations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in recommendations:
        sections = item.get("sections") or []
        primary = sections[0] if sections else "exploratory"
        grouped[str(primary)].append(item)
    return dict(grouped)


def _render_recommendation_item(
    item: dict[str, Any],
    site_base_url: str,
    feedback_base_url: str,
) -> str:
    paper_id = str(item.get("paper_id", ""))
    title = escape(str(item.get("title", "Untitled")))
    authors = escape(", ".join(str(author) for author in item.get("authors", [])))
    abstract = escape(str(item.get("abstract", "")))
    score = escape(str(item.get("score", "")))

    page_url = f"{site_base_url.rstrip('/')}/?paper_id={urlencode({'': paper_id})[1:]}"
    like_url = _feedback_url(feedback_base_url, paper_id, "like")
    dislike_url = _feedback_url(feedback_base_url, paper_id, "dislike")

    return f"""
      <li style="margin-bottom: 20px;">
        <h3 style="margin-bottom: 4px;"><a href="{escape(page_url)}">{title}</a></h3>
        <div style="color: #555;">{authors}</div>
        <div style="color: #777;">score: {score}</div>
        <p>{abstract}</p>
        <p>
          <a href="{escape(like_url)}">Like</a>
          &nbsp;|&nbsp;
          <a href="{escape(dislike_url)}">Dislike</a>
        </p>
      </li>
    """


def _feedback_url(base_url: str, paper_id: str, rating: str) -> str:
    return f"{base_url}?{urlencode({'paper_id': paper_id, 'rating': rating, 'source': 'email'})}"

