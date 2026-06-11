import json
import tempfile
import unittest
from pathlib import Path

from paper_recommender.domain import InterestProfile, SectionRule
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


if __name__ == "__main__":
    unittest.main()
