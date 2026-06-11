import json
import tempfile
import unittest
from pathlib import Path

from paper_recommender.summarizer import (
    enrich_payload_with_tldrs,
    fallback_tldr,
    main,
    request_tldr,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class SummarizerTests(unittest.TestCase):
    def test_fallback_tldr_uses_title_and_abstract(self):
        text = fallback_tldr(
            {
                "title": "Agentic Microarchitecture Exploration",
                "abstract": "This paper uses LLM agents to search cache replacement policies. More detail.",
            }
        )

        self.assertIn("Agentic Microarchitecture Exploration", text)
        self.assertLessEqual(len(text), 180)

    def test_request_tldr_calls_openai_compatible_chat_completion(self):
        seen = {}

        def opener(request):
            seen["url"] = request.full_url
            seen["body"] = json.loads(request.data.decode("utf-8"))
            seen["authorization"] = request.headers["Authorization"]
            return FakeResponse({"choices": [{"message": {"content": "一句话总结。"}}]})

        tldr = request_tldr(
            {
                "title": "Agentic Microarchitecture Exploration",
                "abstract": "LLM agents explore cache replacement policies.",
            },
            api_key="secret",
            base_url="https://example.com/v1",
            model="deepseek-v4-flash",
            opener=opener,
        )

        self.assertEqual(tldr, "一句话总结。")
        self.assertEqual(seen["url"], "https://example.com/v1/chat/completions")
        self.assertEqual(seen["authorization"], "Bearer secret")
        self.assertEqual(seen["body"]["model"], "deepseek-v4-flash")

    def test_enrich_payload_with_tldrs_uses_fallback_when_api_key_missing(self):
        payload = {
            "recommendations": [
                {
                    "paper_id": "p1",
                    "title": "Agentic Microarchitecture Exploration",
                    "abstract": "LLM agents explore cache replacement policies.",
                }
            ]
        }

        enriched = enrich_payload_with_tldrs(payload, api_key="")

        self.assertIn("tldr", enriched["recommendations"][0])
        self.assertIn("Agentic Microarchitecture Exploration", enriched["recommendations"][0]["tldr"])

    def test_cli_updates_recommendation_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "recommendations.json"
            path.write_text(
                json.dumps(
                    {
                        "recommendations": [
                            {
                                "paper_id": "p1",
                                "title": "Agentic Microarchitecture Exploration",
                                "abstract": "LLM agents explore cache replacement policies.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(["--input", str(path), "--output", str(path)])

            self.assertEqual(exit_code, 0)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("tldr", payload["recommendations"][0])


if __name__ == "__main__":
    unittest.main()
