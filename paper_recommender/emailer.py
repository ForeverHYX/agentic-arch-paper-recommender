"""Email rendering helpers for recommendation digests."""

from __future__ import annotations

from collections import defaultdict
from html import escape
from typing import Any
from urllib.parse import urlencode


FALLBACK_SECTION = "Exploratory but Maybe Relevant"


def render_email_html(
    payload: dict[str, Any],
    site_base_url: str,
    feedback_base_url: str,
) -> str:
    run_date = escape(str(payload.get("run_date", "")))
    section_labels = payload.get("section_labels") or {}
    grouped = _group_recommendations(payload.get("recommendations", []))
    feedback_html = _render_feedback_metrics((payload.get("feedback_summary") or {}).get("metrics") or {})

    sections_html = []
    for section_key, recommendations in grouped.items():
        section_label = escape(str(section_labels.get(section_key, FALLBACK_SECTION)))
        items_html = "\n".join(
            _render_recommendation_item(item, site_base_url, feedback_base_url)
            for item in recommendations
        )
        sections_html.append(f"<h2>{section_label}</h2>\n<ol>{items_html}</ol>")

    body = "\n".join(sections_html) or "<p>No matching papers today.</p>"
    return f"""<!doctype html>
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.5;">
    <h1>Daily arXiv Recommendations - {run_date}</h1>
    {feedback_html}
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
    affiliations = escape(", ".join(str(value) for value in item.get("affiliations", []) if str(value)))
    abstract = escape(str(item.get("abstract", "")))
    tldr = escape(str(item.get("tldr", "")))
    score = escape(str(item.get("score", "")))
    ai_judgement = item.get("ai_judgement") or {}
    ai_score = escape(str(ai_judgement.get("score", item.get("ai_score", ""))))
    ai_reason = escape(str(ai_judgement.get("reason", "")))

    page_url = f"{site_base_url.rstrip('/')}/?paper_id={urlencode({'': paper_id})[1:]}"
    paper_url = str(item.get("url", "")) or f"https://arxiv.org/abs/{paper_id}"
    pdf_url = str(item.get("pdf_url", "")) or f"https://arxiv.org/pdf/{paper_id}"
    code_urls = [str(url) for url in item.get("code_urls", []) if str(url)]
    code_search_url = str(item.get("code_search_url", ""))
    primary_section = str((item.get("sections") or [""])[0])
    like_url = _feedback_url(feedback_base_url, paper_id, "like", primary_section)
    dislike_url = _feedback_url(feedback_base_url, paper_id, "dislike", primary_section)
    code_links = " ".join(f'<a href="{escape(url)}">Code</a>' for url in code_urls)
    code_search_link = f'<a href="{escape(code_search_url)}">Code Search</a>' if code_search_url else ""
    code_section = " ".join(part for part in [code_links, code_search_link] if part)

    return f"""
      <li style="margin-bottom: 20px;">
        <h3 style="margin-bottom: 4px;"><a href="{escape(page_url)}">{title}</a></h3>
        <div style="color: #555;">{authors}</div>
        {f'<div style="color: #555;"><strong>单位:</strong> {affiliations}</div>' if affiliations else ''}
        <div style="color: #777;">score: {score}</div>
        {f'<p><strong>AI 总结:</strong> {tldr}</p>' if tldr else ''}
        {f'<p><strong>AI 判断:</strong> {ai_score} - {ai_reason}</p>' if ai_reason else ''}
        <p>{abstract}</p>
        <p>
          <a href="{escape(paper_url)}">Paper</a>
          &nbsp;|&nbsp;
          <a href="{escape(pdf_url)}">PDF</a>
          {f'&nbsp;|&nbsp;{code_section}' if code_section else ''}
          &nbsp;|&nbsp;
          <a href="{escape(like_url)}">Like</a>
          &nbsp;|&nbsp;
          <a href="{escape(dislike_url)}">Dislike</a>
        </p>
      </li>
    """


def _render_feedback_metrics(metrics: dict[str, Any]) -> str:
    total = int(metrics.get("total_events") or 0)
    if total <= 0:
        return ""

    like_rate = round(float(metrics.get("like_rate") or 0) * 100)
    liked_topics = _unique_strings(
        list(metrics.get("top_liked_keywords") or []) + list(metrics.get("top_liked_toolchains") or [])
    )[:4]
    disliked_topics = _unique_strings(
        list(metrics.get("top_disliked_keywords") or []) + list(metrics.get("top_disliked_toolchains") or [])
    )[:4]
    topic_parts = []
    if liked_topics:
        topic_parts.append(f"liked: {escape(', '.join(liked_topics))}")
    if disliked_topics:
        topic_parts.append(f"disliked: {escape(', '.join(disliked_topics))}")
    topics = f"<br>{' | '.join(topic_parts)}" if topic_parts else ""
    return (
        '<p style="color: #555; border-left: 4px solid #0f766e; padding-left: 10px;">'
        f"<strong>Feedback: {total} events</strong>, {like_rate}% like rate"
        f"{topics}</p>"
    )


def _unique_strings(values: list[Any]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _feedback_url(base_url: str, paper_id: str, rating: str, section: str) -> str:
    return f"{base_url}?{urlencode({'paper_id': paper_id, 'rating': rating, 'source': 'email', 'section': section})}"
