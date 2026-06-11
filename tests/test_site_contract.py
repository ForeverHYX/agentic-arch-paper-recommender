import unittest
from pathlib import Path


class SiteContractTests(unittest.TestCase):
    def test_recommendation_page_renders_tldr_and_external_links(self):
        script = Path("site/app.js").read_text(encoding="utf-8")

        self.assertIn("paper.tldr", script)
        self.assertIn("paper.url", script)
        self.assertIn("paper.pdf_url", script)
        self.assertIn("paper.code_urls", script)
        self.assertIn("Paper", script)
        self.assertIn("PDF", script)
        self.assertIn("Code", script)

    def test_recommendation_page_has_workbench_layout_hooks(self):
        html = Path("site/index.html").read_text(encoding="utf-8")
        styles = Path("site/styles.css").read_text(encoding="utf-8")
        script = Path("site/app.js").read_text(encoding="utf-8")

        self.assertIn('id="summaryStats"', html)
        self.assertIn('id="sectionNav"', html)
        self.assertIn("renderSummaryStats", script)
        self.assertIn("renderSectionNav", script)
        self.assertIn(".paper-tldr", styles)
        self.assertIn(".link-button", styles)
        self.assertIn(".section-nav", styles)


if __name__ == "__main__":
    unittest.main()
