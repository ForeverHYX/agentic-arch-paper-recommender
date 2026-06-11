import unittest
from pathlib import Path


class FeedbackPageContractTests(unittest.TestCase):
    def test_feedback_page_posts_paper_metadata_for_learning(self):
        script = Path("site/feedback.js").read_text(encoding="utf-8")

        self.assertIn('fetch("recommendations.json"', script)
        self.assertIn("findPaperMetadata", script)
        self.assertIn("title: paperMetadata.title", script)
        self.assertIn("abstract: paperMetadata.abstract", script)
        self.assertIn("authors: paperMetadata.authors", script)
        self.assertIn("categories: paperMetadata.categories", script)


if __name__ == "__main__":
    unittest.main()
