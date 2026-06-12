import json
import os
import tempfile
import unittest
from pathlib import Path


class StatusTests(unittest.TestCase):
    def test_status_cli_writes_boolean_subsystem_status_without_secret_values(self):
        env_updates = {
            "HAS_LLM": "true",
            "HAS_SMTP": "false",
            "HAS_SUPABASE": "false",
            "HAS_LOCAL_FEEDBACK": "true",
            "HAS_PROFILE_OVERRIDE": "true",
            "OPENAI_BASE_URL": "https://opencode.ai/zen/go/v1",
            "OPENAI_MODEL": "deepseek-v4-flash",
            "OPENAI_API_KEY": "secret-value-that-must-not-appear",
        }
        old_values = {key: os.environ.get(key) for key in env_updates}
        os.environ.update(env_updates)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "status.json"
                from paper_recommender.status import main

                exit_code = main(["--output", str(output)])
                payload = json.loads(output.read_text(encoding="utf-8"))
        finally:
            for key, old_value in old_values.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["llm"]["configured"])
        self.assertEqual(payload["llm"]["base_url"], "https://opencode.ai/zen/go/v1")
        self.assertEqual(payload["llm"]["model"], "deepseek-v4-flash")
        self.assertFalse(payload["smtp"]["configured"])
        self.assertFalse(payload["supabase"]["configured"])
        self.assertTrue(payload["local_feedback"]["configured"])
        self.assertTrue(payload["profile_override"]["configured"])
        self.assertNotIn("secret-value-that-must-not-appear", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
