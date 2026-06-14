import unittest

from paper_recommender.domain import InterestProfile, NegativeRule, SectionRule
from paper_recommender.github_trending import (
    extract_paper_links,
    parse_trending_repositories,
    repository_records_from_trending_html,
)


TRENDING_HTML = """
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/example/arch-agent"><span>example /</span> arch-agent</a>
  </h2>
  <p class="col-9 color-fg-muted my-1">Hardware design agent for microarchitecture exploration.</p>
  <span itemprop="programmingLanguage">Python</span>
  <a href="/example/arch-agent/stargazers">1,234</a>
  <a href="/example/arch-agent/forks">56</a>
  <span>87 stars today</span>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/example/web-agent"><span>example /</span> web-agent</a>
  </h2>
  <p class="col-9 color-fg-muted my-1">Browser task automation with RAG agents.</p>
  <span itemprop="programmingLanguage">TypeScript</span>
  <a href="/example/web-agent/stargazers">2,000</a>
  <a href="/example/web-agent/forks">200</a>
  <span>120 stars today</span>
</article>
"""


class GitHubTrendingTests(unittest.TestCase):
    def test_parse_trending_repositories_extracts_repo_and_star_trend(self):
        repos = parse_trending_repositories(TRENDING_HTML)

        self.assertEqual(len(repos), 2)
        self.assertEqual(repos[0].full_name, "example/arch-agent")
        self.assertEqual(repos[0].url, "https://github.com/example/arch-agent")
        self.assertEqual(repos[0].description, "Hardware design agent for microarchitecture exploration.")
        self.assertEqual(repos[0].language, "Python")
        self.assertEqual(repos[0].stars, 1234)
        self.assertEqual(repos[0].forks, 56)
        self.assertEqual(repos[0].stars_today, 87)

    def test_extract_paper_links_finds_original_paper_urls(self):
        links = extract_paper_links(
            "Paper: https://arxiv.org/abs/2606.00001, "
            "OpenReview https://openreview.net/forum?id=abc123, "
            "DOI https://doi.org/10.1145/1234567. "
            "Duplicate https://arxiv.org/abs/2606.00001"
        )

        self.assertEqual(
            links,
            [
                {"label": "arXiv", "url": "https://arxiv.org/abs/2606.00001"},
                {"label": "OpenReview", "url": "https://openreview.net/forum?id=abc123"},
                {"label": "DOI", "url": "https://doi.org/10.1145/1234567"},
            ],
        )

    def test_repository_records_filter_by_interest_profile_and_include_metadata(self):
        profile = InterestProfile(
            name="Repo Profile",
            core_categories=frozenset({"cs.AR"}),
            expansion_categories=frozenset({"cs.AI"}),
            expansion_accept_score=4.0,
            sections=(
                SectionRule(
                    "agentic_architecture",
                    "Agentic Architecture",
                    4.0,
                    ("hardware design agent", "microarchitecture exploration", "gem5"),
                ),
            ),
            negative_rules=(
                NegativeRule(
                    "generic-agent-noise",
                    6.0,
                    ("browser task", "rag agent"),
                ),
            ),
        )
        metadata = {
            "example/arch-agent": {
                "description": "Agentic architecture exploration with simulator feedback.",
                "stargazers_count": 1300,
                "forks_count": 60,
                "language": "Python",
                "topics": ["gem5", "microarchitecture"],
                "pushed_at": "2026-06-14T00:00:00Z",
                "homepage": "https://example.com/arch-agent",
            },
            "example/web-agent": {
                "description": "Browser task automation with RAG agents.",
                "stargazers_count": 2200,
                "forks_count": 220,
                "language": "TypeScript",
                "topics": ["agent"],
            },
        }
        readmes = {
            "example/arch-agent": (
                "Implements a hardware design agent that drives gem5 for microarchitecture exploration. "
                "Original paper: https://arxiv.org/abs/2606.00001"
            ),
            "example/web-agent": "RAG agent for browser task automation.",
        }

        records = repository_records_from_trending_html(
            TRENDING_HTML,
            profile=profile,
            metadata_fetcher=lambda full_name: metadata[full_name],
            readme_fetcher=lambda full_name: readmes[full_name],
            limit=10,
        )

        self.assertEqual([record["paper_id"] for record in records], ["repo:example/arch-agent"])
        record = records[0]
        self.assertEqual(record["item_type"], "repository")
        self.assertEqual(record["source"], "github_trending")
        self.assertEqual(record["title"], "example/arch-agent")
        self.assertIn("hardware design agent", record["abstract"].lower())
        self.assertEqual(record["repository_url"], "https://github.com/example/arch-agent")
        self.assertEqual(record["repository_full_name"], "example/arch-agent")
        self.assertEqual(record["repository_stars"], 1300)
        self.assertEqual(record["repository_forks"], 60)
        self.assertEqual(record["repository_stars_today"], 87)
        self.assertEqual(record["repository_topics"], ["gem5", "microarchitecture"])
        self.assertEqual(record["paper_links"], [{"label": "arXiv", "url": "https://arxiv.org/abs/2606.00001"}])


if __name__ == "__main__":
    unittest.main()
