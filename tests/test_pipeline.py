import json
import tempfile
import unittest
from pathlib import Path

from paper_recommender.domain import InterestProfile, SectionRule, SeedPaper
from paper_recommender.pipeline import (
    load_papers_jsonl,
    paper_from_record,
    recommendation_payload,
)


class PipelineTests(unittest.TestCase):
    def test_paper_from_record_accepts_arxiv_style_fields(self):
        record = {
            "id": "2604.03312",
            "title": "Computer Architecture's AlphaZero Moment",
            "summary": "Automated architecture discovery for computer architecture design.",
            "authors": [
                {"name": "A. Architect", "affiliation": "University of Architecture"},
                {"name": "B. Researcher", "affiliations": ["National HPC Lab"]},
            ],
            "categories": "cs.AR cs.LG",
        }

        paper = paper_from_record(record)

        self.assertEqual(paper.paper_id, "2604.03312")
        self.assertEqual(paper.authors, ["A. Architect", "B. Researcher"])
        self.assertEqual(paper.affiliations, ["University of Architecture", "National HPC Lab"])
        self.assertEqual(paper.categories, ["cs.AR", "cs.LG"])

    def test_paper_from_record_preserves_paper_and_code_links(self):
        record = {
            "paper_id": "2604.03312",
            "title": "Agentic Architecture Exploration",
            "abstract": "Code is available at https://github.com/example/arch-agent.",
            "authors": ["A. Architect"],
            "categories": ["cs.AR"],
            "url": "https://arxiv.org/abs/2604.03312",
        }

        paper = paper_from_record(record)

        self.assertEqual(paper.url, "https://arxiv.org/abs/2604.03312")
        self.assertEqual(paper.pdf_url, "https://arxiv.org/pdf/2604.03312")
        self.assertEqual(paper.code_urls, ["https://github.com/example/arch-agent"])
        self.assertIn("https://github.com/search?", paper.code_search_url)
        self.assertIn("Agentic+Architecture+Exploration", paper.code_search_url)
        self.assertIn("type=repositories", paper.code_search_url)

    def test_paper_from_record_preserves_repository_metadata(self):
        record = {
            "item_type": "repository",
            "source": "github_trending",
            "paper_id": "repo:example/arch-agent",
            "title": "example/arch-agent",
            "abstract": "Hardware design agent for gem5 microarchitecture exploration.",
            "authors": ["example"],
            "categories": ["github", "Python", "gem5"],
            "url": "https://github.com/example/arch-agent",
            "code_urls": ["https://github.com/example/arch-agent"],
            "repository_url": "https://github.com/example/arch-agent",
            "repository_full_name": "example/arch-agent",
            "repository_stars": 1300,
            "repository_forks": 60,
            "repository_stars_today": 87,
            "repository_language": "Python",
            "repository_topics": ["gem5", "microarchitecture"],
            "repository_pushed_at": "2026-06-14T00:00:00Z",
            "repository_homepage": "https://example.com/arch-agent",
            "paper_links": [{"label": "arXiv", "url": "https://arxiv.org/abs/2606.00001"}],
        }

        paper = paper_from_record(record)

        self.assertEqual(paper.item_type, "repository")
        self.assertEqual(paper.source, "github_trending")
        self.assertEqual(paper.repository_url, "https://github.com/example/arch-agent")
        self.assertEqual(paper.repository_full_name, "example/arch-agent")
        self.assertEqual(paper.repository_stars_today, 87)
        self.assertEqual(paper.repository_topics, ["gem5", "microarchitecture"])
        self.assertEqual(paper.paper_links, [{"label": "arXiv", "url": "https://arxiv.org/abs/2606.00001"}])

    def test_load_papers_jsonl_skips_empty_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "papers.jsonl"
            path.write_text(
                "\n".join(
                    [
                        "",
                        json.dumps(
                            {
                                "paper_id": "agentic",
                                "title": "LLM-Driven Architecture Design Space Exploration",
                                "abstract": "A hardware design agent explores microarchitecture optimization.",
                                "authors": ["C. Agent"],
                                "categories": ["cs.AI", "cs.AR"],
                            }
                        ),
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            papers = load_papers_jsonl(path)

        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].paper_id, "agentic")

    def test_recommendation_payload_ranks_and_serializes_accepted_papers(self):
        records = [
            {
                "paper_id": "noise",
                "title": "A Web Agent Benchmark",
                "abstract": "A RAG agent for browser task automation.",
                "authors": ["D. Noise"],
                "categories": ["cs.AI"],
            },
            {
                "paper_id": "arch",
                "title": "Agentic AI-Driven Microarchitecture Exploration",
                "abstract": (
                    "An LLM-driven architecture design space exploration system "
                    "uses gem5 and cache replacement policy search."
                ),
                "authors": ["E. Arch"],
                "affiliations": ["University of Architecture"],
                "categories": ["cs.AI", "cs.AR"],
            },
        ]

        payload = recommendation_payload([paper_from_record(record) for record in records], "2026-06-12")

        self.assertEqual(payload["run_date"], "2026-06-12")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["recommendations"][0]["rank"], 1)
        self.assertEqual(payload["recommendations"][0]["paper_id"], "arch")
        self.assertIn("agentic_architecture", payload["recommendations"][0]["sections"])
        self.assertEqual(payload["recommendations"][0]["affiliations"], ["University of Architecture"])
        self.assertIn("code_search_url", payload["recommendations"][0])
        self.assertIn("github.com/search", payload["recommendations"][0]["code_search_url"])

    def test_recommendation_payload_accepts_relevant_repository_items(self):
        profile = InterestProfile(
            name="Repo Profile",
            core_categories=frozenset({"cs.AR"}),
            expansion_categories=frozenset({"cs.AI"}),
            sections=(
                SectionRule(
                    "agentic_architecture",
                    "Agentic Architecture",
                    4.0,
                    ("hardware design agent", "gem5", "microarchitecture exploration"),
                ),
            ),
        )
        paper = paper_from_record(
            {
                "item_type": "repository",
                "source": "github_trending",
                "paper_id": "repo:example/arch-agent",
                "title": "example/arch-agent",
                "abstract": "A hardware design agent uses gem5 for microarchitecture exploration.",
                "authors": ["example"],
                "categories": ["github", "Python", "gem5"],
                "url": "https://github.com/example/arch-agent",
                "code_urls": ["https://github.com/example/arch-agent"],
                "repository_url": "https://github.com/example/arch-agent",
                "repository_full_name": "example/arch-agent",
                "repository_stars": 1300,
                "repository_forks": 60,
                "repository_stars_today": 87,
                "repository_language": "Python",
                "repository_topics": ["gem5", "microarchitecture"],
                "paper_links": [{"label": "arXiv", "url": "https://arxiv.org/abs/2606.00001"}],
            }
        )

        payload = recommendation_payload([paper], "2026-06-14", profile=profile)

        self.assertEqual(payload["count"], 1)
        item = payload["recommendations"][0]
        self.assertEqual(item["item_type"], "repository")
        self.assertEqual(item["source"], "github_trending")
        self.assertEqual(item["repository_url"], "https://github.com/example/arch-agent")
        self.assertEqual(item["repository_stars_today"], 87)
        self.assertEqual(item["paper_links"], [{"label": "arXiv", "url": "https://arxiv.org/abs/2606.00001"}])

    def test_recommendation_payload_accepts_ai_infra_repository_with_looser_threshold(self):
        profile = InterestProfile(
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
        )
        repository = paper_from_record(
            {
                "item_type": "repository",
                "source": "github_trending",
                "paper_id": "repo:example/gpu-inference",
                "title": "example/gpu-inference",
                "abstract": "LLM inference serving runtime with batching and CUDA GPU scheduling.",
                "authors": ["example"],
                "categories": ["github", "Python", "llm", "inference", "cuda"],
                "url": "https://github.com/example/gpu-inference",
                "code_urls": ["https://github.com/example/gpu-inference"],
                "repository_url": "https://github.com/example/gpu-inference",
                "repository_full_name": "example/gpu-inference",
                "repository_stars": 1800,
                "repository_forks": 90,
                "repository_stars_today": 55,
                "repository_language": "Python",
                "repository_topics": ["llm", "inference", "cuda"],
            }
        )

        payload = recommendation_payload([repository], "2026-06-15", profile=profile)

        self.assertEqual(payload["count"], 1)
        item = payload["recommendations"][0]
        self.assertEqual(item["item_type"], "repository")
        self.assertEqual(item["paper_id"], "repo:example/gpu-inference")
        self.assertIn("github_arch_ai_infra", item["sections"])
        self.assertIn("repository:inference", item["positive_matches"])

    def test_recommendation_payload_includes_profile_metadata(self):
        profile = InterestProfile(
            name="Quantum Systems",
            core_categories=frozenset({"quant-ph"}),
            expansion_categories=frozenset({"cs.LG"}),
            sections=(
                SectionRule(
                    id="quantum_control",
                    label="Quantum Control",
                    weight=5.0,
                    keywords=("quantum control",),
                ),
            ),
        )
        paper = paper_from_record(
            {
                "paper_id": "quantum",
                "title": "Learning for Quantum Control",
                "abstract": "Quantum control with pulse optimization.",
                "authors": ["Q. Researcher"],
                "categories": ["cs.LG"],
            }
        )

        payload = recommendation_payload([paper], "2026-06-12", profile=profile)

        self.assertEqual(payload["profile_name"], "Quantum Systems")
        self.assertEqual(payload["section_labels"]["quantum_control"], "Quantum Control")

    def test_recommendation_payload_includes_seed_papers_in_profile_context(self):
        profile = InterestProfile(
            name="Agentic Architecture",
            core_categories=frozenset({"cs.AR"}),
            expansion_categories=frozenset({"cs.AI"}),
            sections=(
                SectionRule(
                    id="agentic_architecture",
                    label="Agentic Architecture",
                    weight=5.0,
                    keywords=("architecture design space exploration",),
                ),
            ),
            seed_papers=(
                SeedPaper(
                    title="Computer Architecture's AlphaZero Moment",
                    url="https://arxiv.org/abs/2407.XXXX",
                    notes="Use as a positive example for automated architecture discovery.",
                    keywords=("automated architecture discovery", "design space exploration"),
                ),
            ),
        )
        paper = paper_from_record(
            {
                "paper_id": "agentic",
                "title": "Agentic Architecture Design Space Exploration",
                "abstract": "A system explores architecture design space.",
                "authors": ["A. Architect"],
                "categories": ["cs.AR"],
            }
        )

        payload = recommendation_payload([paper], "2026-06-12", profile=profile)

        self.assertEqual(
            payload["profile_context"]["seed_papers"],
            [
                {
                    "title": "Computer Architecture's AlphaZero Moment",
                    "url": "https://arxiv.org/abs/2407.XXXX",
                    "notes": "Use as a positive example for automated architecture discovery.",
                    "keywords": ["automated architecture discovery", "design space exploration"],
                }
            ],
        )

    def test_recommendation_payload_can_fill_minimum_count_with_exploratory_core_papers(self):
        profile = InterestProfile(
            name="Custom",
            core_categories=frozenset({"cs.TEST"}),
            expansion_categories=frozenset(),
            sections=(
                SectionRule("arch", "Architecture", 3.0, ("cache replacement",)),
            ),
        )
        matched = paper_from_record(
            {
                "paper_id": "matched",
                "title": "Cache Replacement for Architecture",
                "abstract": "cache replacement",
                "authors": [],
                "categories": ["cs.TEST"],
            }
        )
        exploratory = paper_from_record(
            {
                "paper_id": "explore",
                "title": "Performance Study for Processors",
                "abstract": "A core category paper without current keyword matches.",
                "authors": [],
                "categories": ["cs.TEST"],
            }
        )

        payload = recommendation_payload(
            [matched, exploratory],
            "2026-06-12",
            limit=10,
            min_count=2,
            profile=profile,
        )

        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["recommendations"][1]["paper_id"], "explore")
        self.assertEqual(payload["recommendations"][1]["sections"], ["exploratory"])

    def test_recommendation_payload_uses_clean_expansion_papers_when_core_fill_is_insufficient(self):
        profile = InterestProfile(
            name="Custom",
            core_categories=frozenset({"cs.AR"}),
            expansion_categories=frozenset({"cs.AI"}),
            sections=(SectionRule("arch", "Architecture", 3.0, ("cache replacement",)),),
        )
        core = paper_from_record(
            {
                "paper_id": "core",
                "title": "Cache Replacement for Architecture",
                "abstract": "cache replacement",
                "authors": [],
                "categories": ["cs.AR"],
            }
        )
        expansion = paper_from_record(
            {
                "paper_id": "clean-ai",
                "title": "Learning Systems for Design Search",
                "abstract": "A clean expansion-category candidate without generic web agent noise.",
                "authors": [],
                "categories": ["cs.AI"],
            }
        )
        noisy = paper_from_record(
            {
                "paper_id": "noise",
                "title": "A Web Agent Benchmark",
                "abstract": "A RAG agent for browser task automation.",
                "authors": [],
                "categories": ["cs.AI"],
            }
        )

        payload = recommendation_payload(
            [core, expansion, noisy],
            "2026-06-12",
            limit=10,
            min_count=2,
            profile=profile,
        )

        self.assertEqual([item["paper_id"] for item in payload["recommendations"]], ["core", "clean-ai"])
        self.assertEqual(payload["recommendations"][1]["sections"], ["exploratory"])

    def test_recommendation_payload_adds_extra_exploration_papers(self):
        profile = InterestProfile(
            name="Custom",
            core_categories=frozenset({"cs.AR"}),
            expansion_categories=frozenset({"cs.AI", "cs.LG"}),
            sections=(SectionRule("arch", "Architecture", 3.0, ("cache replacement",)),),
        )
        core_records = [
            {
                "paper_id": "core-1",
                "title": "Cache Replacement for Architecture",
                "abstract": "cache replacement for microarchitecture",
                "authors": [],
                "categories": ["cs.AR"],
            },
            {
                "paper_id": "core-2",
                "title": "Another Cache Replacement Study",
                "abstract": "cache replacement for memory hierarchy",
                "authors": [],
                "categories": ["cs.AR"],
            },
        ]
        exploration_records = [
            {
                "paper_id": f"explore-{index}",
                "title": f"AI Systems Exploration {index}",
                "abstract": "GPU accelerator runtime for machine learning systems.",
                "authors": [],
                "categories": ["cs.AI"],
            }
            for index in range(6)
        ]
        papers = [paper_from_record(record) for record in core_records + exploration_records]

        payload = recommendation_payload(
            papers,
            "2026-06-14",
            limit=2,
            min_count=2,
            exploration_count=5,
            profile=profile,
        )

        self.assertEqual(payload["count"], 7)
        self.assertEqual(
            sum("exploration" in item["sections"] for item in payload["recommendations"]),
            5,
        )
        self.assertEqual(payload["section_labels"]["exploration"], "Exploration / AI+体系结构探索")

    def test_exploration_requires_ai_ml_and_systems_signals(self):
        profile = InterestProfile(
            name="Custom",
            core_categories=frozenset({"cs.AR"}),
            expansion_categories=frozenset({"cs.AI", "cs.LG"}),
            sections=(SectionRule("arch", "Architecture", 3.0, ("cache replacement",)),),
        )
        good = paper_from_record(
            {
                "paper_id": "gpu-llm-serving",
                "title": "Characterizing Software Aging in GPU-Based LLM Serving Systems",
                "abstract": "We study GPU memory behavior and inference serving performance for LLM systems.",
                "authors": [],
                "categories": ["cs.AI"],
            }
        )
        runtime_only = paper_from_record(
            {
                "paper_id": "runtime-only",
                "title": "Runtime Enforcement of Hybrid System Properties",
                "abstract": "A runtime monitor checks hybrid system specifications.",
                "authors": [],
                "categories": ["cs.AI"],
            }
        )
        ml_only = paper_from_record(
            {
                "paper_id": "ml-only",
                "title": "Sparse Attention for Language Models",
                "abstract": "A machine learning method improves attention quality.",
                "authors": [],
                "categories": ["cs.LG"],
            }
        )

        payload = recommendation_payload(
            [good, runtime_only, ml_only],
            "2026-06-14",
            exploration_count=5,
            profile=profile,
        )

        self.assertEqual([item["paper_id"] for item in payload["recommendations"]], ["gpu-llm-serving"])
        self.assertEqual(payload["recommendations"][0]["sections"], ["exploration"])


if __name__ == "__main__":
    unittest.main()
