import json
import tempfile
import unittest
from pathlib import Path

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
            "authors": [{"name": "A. Architect"}, {"name": "B. Researcher"}],
            "categories": "cs.AR cs.LG",
        }

        paper = paper_from_record(record)

        self.assertEqual(paper.paper_id, "2604.03312")
        self.assertEqual(paper.authors, ["A. Architect", "B. Researcher"])
        self.assertEqual(paper.categories, ["cs.AR", "cs.LG"])

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
                "categories": ["cs.AI", "cs.AR"],
            },
        ]

        payload = recommendation_payload([paper_from_record(record) for record in records], "2026-06-12")

        self.assertEqual(payload["run_date"], "2026-06-12")
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["recommendations"][0]["rank"], 1)
        self.assertEqual(payload["recommendations"][0]["paper_id"], "arch")
        self.assertIn("agentic_architecture", payload["recommendations"][0]["sections"])


if __name__ == "__main__":
    unittest.main()

