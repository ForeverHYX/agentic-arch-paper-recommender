import unittest
from pathlib import Path


class WorkflowContractTests(unittest.TestCase):
    def test_daily_workflow_fetches_real_arxiv_records_before_recommendation_build(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("python -m paper_recommender.arxiv_source", workflow)
        self.assertIn("--output output/papers.jsonl", workflow)
        self.assertIn("--input output/papers.jsonl", workflow)
        self.assertNotIn("--input examples/sample_papers.jsonl", workflow)

    def test_daily_workflow_reads_and_publishes_recommendation_history(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("echo '[]' > output/history.json", workflow)
        self.assertIn("python -m paper_recommender.history fetch", workflow)
        self.assertIn("--output output/history.json", workflow)
        self.assertIn("--history output/history.json", workflow)
        self.assertIn("python -m paper_recommender.history publish", workflow)
        self.assertIn("--recommendations site/recommendations.json", workflow)


if __name__ == "__main__":
    unittest.main()
