import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

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


class FakeErrorBody:
    def __init__(self, text):
        self.text = text

    def read(self):
        return self.text.encode("utf-8")

    def close(self):
        pass


class SummarizerTests(unittest.TestCase):
    def test_fallback_tldr_is_structured_english_briefing(self):
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

        self.assertIn("Problem:", text)
        self.assertIn("Method:", text)
        self.assertIn("Finding:", text)
        self.assertIn("Why it matters:", text)
        self.assertGreaterEqual(len(text), 120)
        self.assertNotIn("...", text)
        self.assertNotIn("…", text)
        self.assertNotRegex(text, r"[\u4e00-\u9fff]")

    def test_fallback_tldr_handles_repository_items(self):
        text = fallback_tldr(
            {
                "item_type": "repository",
                "title": "example/arch-agent",
                "abstract": "Hardware design agent for gem5 microarchitecture exploration.",
                "repository_stars_today": 87,
                "paper_links": [{"label": "arXiv", "url": "https://arxiv.org/abs/2606.00001"}],
            }
        )

        self.assertIn("repository", text.lower())
        self.assertIn("stars today", text.lower())
        self.assertIn("paper link", text.lower())
        self.assertIn("Problem:", text)
        self.assertNotRegex(text, r"[\u4e00-\u9fff]")

    def test_fallback_tldr_does_not_truncate_with_ellipsis(self):
        text = fallback_tldr(
            {
                "title": "Agentic Microarchitecture Exploration",
                "abstract": "LLM agents explore cache replacement policies with simulator feedback.",
                "sections": ["agentic_architecture", "microarchitecture_simulators"],
            },
            max_chars=120,
        )

        self.assertGreater(len(text), 120)
        self.assertNotIn("...", text)
        self.assertNotIn("…", text)

    def test_request_tldr_calls_openai_compatible_chat_completion(self):
        seen = {}

        def opener(request, timeout=None):
            seen["url"] = request.full_url
            seen["body"] = json.loads(request.data.decode("utf-8"))
            seen["authorization"] = request.headers["Authorization"]
            seen["user_agent"] = request.get_header("User-agent")
            seen["timeout"] = timeout
            return FakeResponse({"choices": [{"message": {"content": "One sentence summary."}}]})

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

        self.assertEqual(tldr, "One sentence summary.")
        self.assertEqual(seen["url"], "https://example.com/v1/chat/completions")
        self.assertEqual(seen["authorization"], "Bearer secret")
        self.assertIn("agentic-arch-paper-recommender", seen["user_agent"])
        self.assertGreaterEqual(seen["timeout"], 180)
        self.assertEqual(seen["body"]["model"], "deepseek-v4-flash")
        self.assertEqual(seen["body"]["thinking"], {"type": "disabled"})
        self.assertGreaterEqual(seen["body"]["max_tokens"], 8192)
        self.assertLessEqual(seen["body"]["max_tokens"], 9000)
        system_prompt = seen["body"]["messages"][0]["content"]
        self.assertIn("English", system_prompt)
        self.assertIn("final answer only", system_prompt.lower())
        self.assertIn("do not explain", system_prompt.lower())
        self.assertIn("Problem", system_prompt)
        self.assertIn("Method", system_prompt)
        self.assertIn("Finding", system_prompt)
        self.assertIn("Why it matters", system_prompt)

    def test_request_tldr_includes_repository_context_for_repo_items(self):
        seen = {}

        def opener(request, timeout=None):
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"choices": [{"message": {"content": "Problem: This repository is relevant to hardware design automation. Method: It packages the implementation and metadata needed to inspect the system. Finding: Its trend and links make it worth checking. Why it matters: It may connect software tooling with architecture research."}}]})

        request_tldr(
            {
                "item_type": "repository",
                "title": "example/arch-agent",
                "abstract": "Hardware design agent for gem5 microarchitecture exploration.",
                "repository_stars_today": 87,
                "repository_stars": 1300,
                "repository_language": "Python",
                "repository_topics": ["gem5", "microarchitecture"],
                "paper_links": [{"label": "arXiv", "url": "https://arxiv.org/abs/2606.00001"}],
            },
            api_key="secret",
            opener=opener,
        )

        system_prompt = seen["body"]["messages"][0]["content"]
        user_prompt = seen["body"]["messages"][1]["content"]
        self.assertIn("repository", system_prompt.lower())
        self.assertIn("what it implements", system_prompt)
        self.assertIn("Stars today: 87", user_prompt)
        self.assertIn("Topics: gem5, microarchitecture", user_prompt)
        self.assertIn("Original paper links: arXiv https://arxiv.org/abs/2606.00001", user_prompt)

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
        self.assertIn("Problem:", enriched["recommendations"][0]["tldr"])

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

        self.assertIn("Problem:", enriched["recommendations"][0]["tldr"])
        self.assertIn("Method:", enriched["recommendations"][0]["tldr"])

    def test_enrich_payload_with_tldrs_retries_short_model_response(self):
        payload = {
            "recommendations": [
                {
                    "paper_id": "p1",
                    "title": "Agentic Microarchitecture Exploration",
                    "abstract": "LLM agents explore cache replacement policies.",
                }
            ]
        }
        long_tldr = (
            "Problem: The paper studies how an LLM agent can search microarchitecture design space with simulator feedback. "
            "Method: It links candidate generation, gem5 evaluation, and feedback-guided refinement into a closed loop. "
            "Finding: The abstract suggests the loop can improve cache and prefetcher choices, although the full experiment still needs checking. "
            "Why it matters: It directly matches agentic architecture exploration and simulator-guided optimization."
        )
        calls = []

        def opener(request, timeout=None):
            calls.append(json.loads(request.data.decode("utf-8")))
            if len(calls) == 1:
                return FakeResponse({"choices": [{"message": {"content": "Short summary."}}]})
            return FakeResponse({"choices": [{"message": {"content": long_tldr}}]})

        enriched = enrich_payload_with_tldrs(payload, api_key="secret", opener=opener, require_api=True)

        self.assertEqual(enriched["recommendations"][0]["tldr"], long_tldr)
        self.assertEqual(len(calls), 2)
        self.assertIn("previous output was too short", calls[1]["messages"][0]["content"])

    def test_enrich_payload_with_tldrs_requires_api_without_leaking_key(self):
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
            raise HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                hdrs=None,
                fp=FakeErrorBody('{"error":"invalid api key unit-test-secret"}'),
            )

        with self.assertRaises(RuntimeError) as context:
            enrich_payload_with_tldrs(
                payload,
                api_key="unit-test-secret",
                base_url="https://opencode.ai/zen/go/v1",
                model="deepseek-v4-flash",
                opener=opener,
                require_api=True,
            )

        message = str(context.exception)
        self.assertIn("HTTP 401", message)
        self.assertIn("opencode.ai/zen/go/v1", message)
        self.assertIn("deepseek-v4-flash", message)
        self.assertIn("invalid api key", message)
        self.assertNotIn("unit-test-secret", message)

    def test_enrich_payload_with_tldrs_requires_api_rejects_short_model_response(self):
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
            return FakeResponse({"choices": [{"message": {"content": "Short summary."}}]})

        with self.assertRaises(RuntimeError) as context:
            enrich_payload_with_tldrs(payload, api_key="secret", opener=opener, require_api=True)

        self.assertIn("TLDR is too short", str(context.exception))

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
