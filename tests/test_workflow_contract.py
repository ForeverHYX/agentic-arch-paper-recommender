import unittest
from pathlib import Path


class WorkflowContractTests(unittest.TestCase):
    def test_daily_workflow_fetches_real_arxiv_records_before_recommendation_build(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("python -m paper_recommender.arxiv_source", workflow)
        self.assertIn("--output output/papers.jsonl", workflow)
        self.assertIn("--max-results 500", workflow)
        self.assertIn("--input output/papers.jsonl", workflow)
        self.assertIn("--profile output/interests.json", workflow)
        self.assertIn("--limit 45", workflow)
        self.assertIn("--min-count 45", workflow)
        self.assertNotIn("--input examples/sample_papers.jsonl", workflow)

    def test_daily_workflow_allows_profile_override_secret(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("HAS_PROFILE_OVERRIDE: ${{ secrets.PROFILE_OVERRIDE_JSON != '' }}", workflow)
        self.assertIn("cp config/interests.json output/interests.json", workflow)
        self.assertIn("Load profile override secret", workflow)
        self.assertIn("PROFILE_OVERRIDE_JSON: ${{ secrets.PROFILE_OVERRIDE_JSON }}", workflow)
        self.assertIn("python -m paper_recommender.profile_config --from-env PROFILE_OVERRIDE_JSON --output output/interests.json", workflow)
        self.assertIn("cp output/interests.json site/interests.json", workflow)
        self.assertLess(
            workflow.index("Load profile override secret"),
            workflow.index("python -m paper_recommender.arxiv_source"),
        )

    def test_daily_workflow_judges_candidates_with_llm_before_tldr_enrichment(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("python -m paper_recommender.judge", workflow)
        self.assertIn("--limit 15", workflow)
        self.assertIn("OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}", workflow)
        self.assertLess(
            workflow.index("python -m paper_recommender.judge"),
            workflow.index("python -m paper_recommender.summarizer"),
        )

    def test_daily_workflow_enriches_affiliations_before_tldr_enrichment(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("python -m paper_recommender.affiliations", workflow)
        self.assertLess(
            workflow.index("python -m paper_recommender.judge"),
            workflow.index("python -m paper_recommender.affiliations"),
        )
        self.assertLess(
            workflow.index("python -m paper_recommender.affiliations"),
            workflow.index("python -m paper_recommender.summarizer"),
        )

    def test_daily_workflow_enriches_tldrs_before_email_and_pages(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("python -m paper_recommender.summarizer", workflow)
        self.assertIn("OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}", workflow)
        self.assertLess(
            workflow.index("python -m paper_recommender.summarizer"),
            workflow.index("python -m paper_recommender.email_delivery"),
        )

    def test_daily_workflow_allows_openai_compatible_base_url_and_model_overrides(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("OPENAI_BASE_URL: ${{ vars.OPENAI_BASE_URL || 'https://opencode.ai/zen/go/v1' }}", workflow)
        self.assertIn("OPENAI_MODEL: ${{ vars.OPENAI_MODEL || 'deepseek-v4-flash' }}", workflow)

    def test_daily_workflow_reads_and_publishes_recommendation_history(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("echo '[]' > output/history.json", workflow)
        self.assertIn("python -m paper_recommender.history fetch", workflow)
        self.assertIn("--output output/history.json", workflow)
        self.assertIn("--history output/history.json", workflow)
        self.assertIn("python -m paper_recommender.history publish", workflow)
        self.assertIn("--recommendations site/recommendations.json", workflow)

    def test_daily_workflow_can_load_local_feedback_secret_without_supabase(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("HAS_LOCAL_FEEDBACK: ${{ secrets.LOCAL_FEEDBACK_JSON != '' }}", workflow)
        self.assertIn("Load local feedback secret", workflow)
        self.assertIn("if: env.HAS_SUPABASE != 'true' && env.HAS_LOCAL_FEEDBACK == 'true'", workflow)
        self.assertIn("LOCAL_FEEDBACK_JSON: ${{ secrets.LOCAL_FEEDBACK_JSON }}", workflow)
        self.assertIn("python -m paper_recommender.feedback --from-env LOCAL_FEEDBACK_JSON --output output/feedback.json", workflow)
        self.assertLess(
            workflow.index("Load local feedback secret"),
            workflow.index("python -m paper_recommender.pipeline"),
        )

    def test_daily_workflow_retries_email_delivery(self):
        workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

        self.assertIn("python -m paper_recommender.email_delivery", workflow)
        self.assertIn("--max-attempts 3", workflow)


if __name__ == "__main__":
    unittest.main()
