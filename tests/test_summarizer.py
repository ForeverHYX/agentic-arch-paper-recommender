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
    def test_fallback_tldr_is_structured_chinese_briefing(self):
        text = fallback_tldr(
            {
                "title": "Agentic Microarchitecture Exploration",
                "abstract": (
                    "This paper studies how LLM agents can search cache replacement policies. "
                    "It builds a simulator-guided loop that proposes candidates, evaluates them, "
                    "and refines the next design. The evaluation reports better miss-rate and IPC."
                ),
            }
        )

        self.assertIn("研究问题：", text)
        self.assertIn("核心方法：", text)
        self.assertIn("关键结论：", text)
        self.assertIn("推荐理由：", text)
        self.assertGreaterEqual(len(text), 120)
        self.assertLessEqual(len(text), 520)

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
        self.assertGreaterEqual(seen["body"]["max_tokens"], 360)
        system_prompt = seen["body"]["messages"][0]["content"]
        self.assertIn("简体中文", system_prompt)
        self.assertIn("研究问题", system_prompt)
        self.assertIn("核心方法", system_prompt)
        self.assertIn("关键结论", system_prompt)
        self.assertIn("推荐理由", system_prompt)

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
        self.assertIn("研究问题：", enriched["recommendations"][0]["tldr"])

    def test_enrich_payload_with_tldrs_falls_back_on_empty_model_response(self):
        payload = {
            "recommendations": [
                {
                    "paper_id": "p1",
                    "title": "Agentic Microarchitecture Exploration",
                    "abstract": "LLM agents explore cache replacement policies.",
                }
            ]
        }

        def opener(request):
            return FakeResponse({"choices": [{"message": {"content": ""}}]})

        enriched = enrich_payload_with_tldrs(payload, api_key="secret", opener=opener)

        self.assertIn("研究问题：", enriched["recommendations"][0]["tldr"])
        self.assertIn("核心方法：", enriched["recommendations"][0]["tldr"])

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
