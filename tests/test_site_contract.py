import unittest
from pathlib import Path


class SiteContractTests(unittest.TestCase):
    def test_recommendation_page_renders_tldr_and_external_links(self):
        script = Path("site/app.js").read_text(encoding="utf-8")

        self.assertIn("paper.tldr", script)
        self.assertIn("AI 总结", script)
        self.assertIn("paper.ai_judgement", script)
        self.assertIn("AI 判断", script)
        self.assertIn("paper.affiliations", script)
        self.assertIn("单位", script)
        self.assertIn("paper.url", script)
        self.assertIn("paper.pdf_url", script)
        self.assertIn("paper.code_urls", script)
        self.assertIn("paper.code_search_url", script)
        self.assertIn("Paper", script)
        self.assertIn("PDF", script)
        self.assertIn("Code", script)
        self.assertIn("Code Search", script)

    def test_recommendation_page_has_workbench_layout_hooks(self):
        html = Path("site/index.html").read_text(encoding="utf-8")
        styles = Path("site/styles.css").read_text(encoding="utf-8")
        script = Path("site/app.js").read_text(encoding="utf-8")

        self.assertIn('id="summaryStats"', html)
        self.assertIn('id="sectionNav"', html)
        self.assertIn("renderSummaryStats", script)
        self.assertIn("renderSectionNav", script)
        self.assertIn(".paper-tldr", styles)
        self.assertIn(".ai-judgement", styles)
        self.assertIn(".link-button", styles)
        self.assertIn(".section-nav", styles)


if __name__ == "__main__":
    unittest.main()
