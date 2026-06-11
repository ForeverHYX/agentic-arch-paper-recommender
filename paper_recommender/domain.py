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
    url: str = ""
    pdf_url: str = ""
    code_urls: list[str] = field(default_factory=list)


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
class InterestProfile:
    name: str
    core_categories: frozenset[str]
    expansion_categories: frozenset[str]
    sections: tuple[SectionRule, ...]
    negative_rules: tuple[NegativeRule, ...] = field(default_factory=tuple)
    expansion_accept_score: float = 4.0

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
    return InterestProfile(
        name=str(payload.get("name", "Daily arXiv Recommender")),
        core_categories=frozenset(str(item) for item in payload.get("core_categories", [])),
        expansion_categories=frozenset(str(item) for item in payload.get("expansion_categories", [])),
        sections=sections,
        negative_rules=negative_rules,
        expansion_accept_score=float(payload.get("expansion_accept_score", 4.0)),
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

    categories = set(paper.categories)
    in_core_category = bool(categories & resolved_profile.core_categories)
    in_expansion_category = bool(categories & resolved_profile.expansion_categories)
    sections = tuple(
        name for name, value in sorted(section_scores.items(), key=lambda item: (-item[1], item[0]))
    )

    accepted = False
    if score > 0 and in_core_category:
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
    return _normalize(" ".join([paper.title, paper.abstract, " ".join(paper.authors), " ".join(paper.categories)]))


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
