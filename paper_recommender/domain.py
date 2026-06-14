"""Configurable domain filtering and rule-based scoring for paper candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re


DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[1] / "config" / "interests.json"


@dataclass(frozen=True)
class Paper:
    paper_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    affiliations: list[str] = field(default_factory=list)
    url: str = ""
    pdf_url: str = ""
    code_urls: list[str] = field(default_factory=list)
    code_search_url: str = ""
    item_type: str = "paper"
    source: str = "arxiv"
    repository_url: str = ""
    repository_full_name: str = ""
    repository_stars: int = 0
    repository_forks: int = 0
    repository_stars_today: int = 0
    repository_language: str = ""
    repository_topics: list[str] = field(default_factory=list)
    repository_pushed_at: str = ""
    repository_homepage: str = ""
    paper_links: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class Classification:
    paper: Paper
    accepted: bool
    score: float
    sections: tuple[str, ...] = field(default_factory=tuple)
    positive_matches: tuple[str, ...] = field(default_factory=tuple)
    negative_matches: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SectionRule:
    id: str
    label: str
    weight: float
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class NegativeRule:
    id: str
    penalty: float
    keywords: tuple[str, ...]
    recovery_keywords: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SeedPaper:
    title: str
    url: str = ""
    notes: str = ""
    keywords: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "url": self.url,
            "notes": self.notes,
            "keywords": list(self.keywords),
        }


@dataclass(frozen=True)
class InterestProfile:
    name: str
    core_categories: frozenset[str]
    expansion_categories: frozenset[str]
    sections: tuple[SectionRule, ...]
    negative_rules: tuple[NegativeRule, ...] = field(default_factory=tuple)
    expansion_accept_score: float = 4.0
    seed_papers: tuple[SeedPaper, ...] = field(default_factory=tuple)

    @property
    def section_labels(self) -> dict[str, str]:
        return {section.id: section.label for section in self.sections}


def load_interest_profile(path: str | Path = DEFAULT_PROFILE_PATH) -> InterestProfile:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sections = tuple(
        SectionRule(
            id=str(item["id"]),
            label=str(item.get("label", item["id"])),
            weight=float(item.get("weight", 1.0)),
            keywords=tuple(str(keyword) for keyword in item.get("keywords", [])),
        )
        for item in payload.get("sections", [])
    )
    negative_rules = tuple(
        NegativeRule(
            id=str(item["id"]),
            penalty=float(item.get("penalty", 1.0)),
            keywords=tuple(str(keyword) for keyword in item.get("keywords", [])),
            recovery_keywords=tuple(str(keyword) for keyword in item.get("recovery_keywords", [])),
        )
        for item in payload.get("negative_rules", [])
    )
    seed_papers = tuple(
        SeedPaper(
            title=str(item.get("title", "")).strip(),
            url=str(item.get("url", "")).strip(),
            notes=str(item.get("notes", "")).strip(),
            keywords=tuple(str(keyword) for keyword in item.get("keywords", [])),
        )
        for item in payload.get("seed_papers", [])
        if str(item.get("title", "")).strip()
    )
    return InterestProfile(
        name=str(payload.get("name", "每日 arXiv 推荐")),
        core_categories=frozenset(str(item) for item in payload.get("core_categories", [])),
        expansion_categories=frozenset(str(item) for item in payload.get("expansion_categories", [])),
        sections=sections,
        negative_rules=negative_rules,
        expansion_accept_score=float(payload.get("expansion_accept_score", 4.0)),
        seed_papers=seed_papers,
    )


def classify_paper(paper: Paper, profile: InterestProfile | None = None) -> Classification:
    resolved_profile = profile or load_interest_profile()
    text = _paper_text(paper)
    positive_matches: list[str] = []
    negative_matches: list[str] = []
    section_scores: dict[str, float] = {}

    for rule in resolved_profile.sections:
        matches = _matching_keywords(text, rule.keywords)
        if not matches:
            continue
        section_scores[rule.id] = len(matches) * rule.weight
        positive_matches.extend(f"{rule.id}:{match}" for match in matches)

    score = sum(section_scores.values())

    for rule in resolved_profile.negative_rules:
        if _negative_rule_matches(text, rule):
            negative_matches.append(rule.id)
            score -= rule.penalty

    content_score = score
    if paper.item_type == "repository" and content_score > 0:
        trend_bonus = _repository_trend_bonus(paper.repository_stars_today)
        if trend_bonus:
            score += trend_bonus
            positive_matches.append(f"github_trending:{paper.repository_stars_today}-stars-today")

    categories = set(paper.categories)
    in_core_category = bool(categories & resolved_profile.core_categories)
    in_expansion_category = bool(categories & resolved_profile.expansion_categories)
    sections = tuple(
        name for name, value in sorted(section_scores.items(), key=lambda item: (-item[1], item[0]))
    )

    accepted = False
    if paper.item_type == "repository":
        accepted = content_score >= resolved_profile.expansion_accept_score and content_score > 0
    elif score > 0 and in_core_category:
        accepted = True
    elif score >= resolved_profile.expansion_accept_score and in_expansion_category and score > 0:
        accepted = True

    return Classification(
        paper=paper,
        accepted=accepted,
        score=score,
        sections=sections,
        positive_matches=tuple(positive_matches),
        negative_matches=tuple(negative_matches),
    )


def rank_papers(papers: list[Paper], profile: InterestProfile | None = None) -> list[Classification]:
    resolved_profile = profile or load_interest_profile()
    accepted = [
        result for result in (classify_paper(paper, profile=resolved_profile) for paper in papers) if result.accepted
    ]
    return sorted(accepted, key=lambda result: (-result.score, result.paper.paper_id))


def _paper_text(paper: Paper) -> str:
    return _normalize(
        " ".join(
            [
                paper.title,
                paper.abstract,
                " ".join(paper.authors),
                " ".join(paper.affiliations),
                " ".join(paper.categories),
                paper.repository_full_name,
                paper.repository_language,
                " ".join(paper.repository_topics),
                " ".join(str(link.get("url", "")) for link in paper.paper_links),
            ]
        )
    )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _matching_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [keyword for keyword in keywords if _keyword_matches(text, keyword)]


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(_keyword_matches(text, keyword) for keyword in keywords)


def _negative_rule_matches(text: str, rule: NegativeRule) -> bool:
    if not _contains_any(text, rule.keywords):
        return False
    return not _contains_any(text, rule.recovery_keywords)


def _keyword_matches(text: str, keyword: str) -> bool:
    normalized_keyword = _normalize(keyword)
    if not normalized_keyword:
        return False
    if _needs_word_boundary(normalized_keyword):
        return re.search(rf"\b{re.escape(normalized_keyword)}\b", text) is not None
    return normalized_keyword in text


def _needs_word_boundary(keyword: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9.+#-]{0,4}", keyword))


def _repository_trend_bonus(stars_today: int) -> float:
    if stars_today <= 0:
        return 0.0
    return min(3.0, stars_today / 50.0)
