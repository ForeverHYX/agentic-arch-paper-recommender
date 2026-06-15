import unittest
from contextlib import redirect_stdout
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from paper_recommender.domain import InterestProfile, NegativeRule, SectionRule
from paper_recommender.github_trending import (
    extract_paper_links,
    main,
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


def trending_article(full_name: str, description: str, language: str = "Python", stars_today: int = 40) -> str:
    stars = 1000 + stars_today
    forks = 50 + stars_today
    return f"""
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/{full_name}"><span>{full_name.split('/')[0]} /</span> {full_name.split('/')[1]}</a>
  </h2>
  <p class="col-9 color-fg-muted my-1">{description}</p>
  <span itemprop="programmingLanguage">{language}</span>
  <a href="/{full_name}/stargazers">{stars:,}</a>
  <a href="/{full_name}/forks">{forks:,}</a>
  <span>{stars_today} stars today</span>
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

    def test_repository_records_use_looser_arch_ai_infra_filter_and_cap_at_five(self):
        html = "\n".join(
            [
                trending_article("example/gpu-inference", "LLM inference serving runtime for CUDA GPUs."),
                trending_article("example/web-agent", "RAG agent for browser task automation."),
                trending_article("example/rtl-lab", "SystemVerilog RTL toolkit for RISC-V accelerators."),
                trending_article("example/mlir-runtime", "MLIR compiler runtime for AI accelerator deployment."),
                trending_article("example/gem5-tools", "gem5 workflows for memory hierarchy simulation."),
                trending_article("example/training-scheduler", "Distributed training scheduler for GPU clusters."),
                trending_article("example/tensor-kernels", "Triton tensor kernels for quantized transformer inference."),
            ]
        )
        strict_paper_profile = InterestProfile(
            name="Strict Paper Profile",
            core_categories=frozenset({"cs.AR"}),
            expansion_categories=frozenset({"cs.AI"}),
            expansion_accept_score=100.0,
            sections=(
                SectionRule(
                    "paper_only",
                    "Paper-only",
                    10.0,
                    ("unrelated paper phrase",),
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
            "example/gpu-inference": {"topics": ["llm", "inference", "cuda"], "language": "Python"},
            "example/web-agent": {"topics": ["rag", "browser-agent"], "language": "TypeScript"},
            "example/rtl-lab": {"topics": ["systemverilog", "risc-v", "accelerator"], "language": "SystemVerilog"},
            "example/mlir-runtime": {"topics": ["mlir", "compiler", "runtime"], "language": "C++"},
            "example/gem5-tools": {"topics": ["gem5", "memory-hierarchy", "simulation"], "language": "Python"},
            "example/training-scheduler": {"topics": ["distributed-training", "gpu"], "language": "Go"},
            "example/tensor-kernels": {"topics": ["triton", "quantization", "transformer"], "language": "Python"},
        }
        readmes = {
            "example/gpu-inference": "Serves LLM inference workloads on CUDA GPUs with batching and scheduling.",
            "example/web-agent": "RAG browser task automation templates.",
            "example/rtl-lab": "RTL and SystemVerilog components for RISC-V accelerator experiments.",
            "example/mlir-runtime": "Compiler runtime and MLIR lowering paths for AI accelerators.",
            "example/gem5-tools": "Tools for gem5 and DRAM memory hierarchy simulation.",
            "example/training-scheduler": "GPU cluster scheduler for distributed training workloads.",
            "example/tensor-kernels": "Triton kernels for low-bit transformer inference.",
        }

        records = repository_records_from_trending_html(
            html,
            profile=strict_paper_profile,
            metadata_fetcher=lambda full_name: metadata[full_name],
            readme_fetcher=lambda full_name: readmes[full_name],
            limit=5,
        )

        self.assertEqual(
            [record["paper_id"] for record in records],
            [
                "repo:example/gpu-inference",
                "repo:example/rtl-lab",
                "repo:example/mlir-runtime",
                "repo:example/gem5-tools",
                "repo:example/training-scheduler",
            ],
        )
        self.assertEqual(len(records), 5)

    def test_cli_does_not_use_search_fallback_when_trending_is_empty(self):
        with TemporaryDirectory() as tmpdir:
            output_path = f"{tmpdir}/repos.jsonl"
            with patch("paper_recommender.github_trending.fetch_trending_html", return_value="<html></html>"):
                with patch("paper_recommender.github_trending.urlopen") as network:
                    stdout = StringIO()
                    with redirect_stdout(stdout):
                        exit_code = main(["--output", output_path, "--limit", "5"])

            self.assertEqual(exit_code, 0)
            self.assertFalse(network.called)
            self.assertNotIn("Search", stdout.getvalue())
            with open(output_path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "")


if __name__ == "__main__":
    unittest.main()
