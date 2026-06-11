import unittest
from pathlib import Path


class WorkflowContractTests(unittest.TestCase):
    def test_daily_workflow_fetches_real_arxiv_records_before_recommendation_build(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("python -m paper_recommender.arxiv_source", workflow)
        self.assertIn("--output output/papers.jsonl", workflow)
        self.assertIn("--input output/papers.jsonl", workflow)
        self.assertNotIn("--input examples/sample_papers.jsonl", workflow)


if __name__ == "__main__":
    unittest.main()
