import unittest
from pathlib import Path


class DocsContractTests(unittest.TestCase):
    def test_readme_links_supabase_setup_guide(self):
        readme = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("[docs/setup-supabase.md](docs/setup-supabase.md)", readme)

    def test_supabase_setup_guide_has_required_steps(self):
        guide = Path("docs/setup-supabase.md").read_text(encoding="utf-8")

        required = [
            "supabase/schema.sql",
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "gh variable set SUPABASE_URL",
            "gh variable set SUPABASE_ANON_KEY",
            "gh secret set SUPABASE_SERVICE_ROLE_KEY",
            "Daily Paper Recommender",
            "Run Health",
            "Supabase active",
            "local only",
            "service role",
        ]
        for text in required:
            with self.subTest(text=text):
                self.assertIn(text, guide)


if __name__ == "__main__":
    unittest.main()
