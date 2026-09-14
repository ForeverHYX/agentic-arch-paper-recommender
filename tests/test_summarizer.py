import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from paper_recommender.summarizer import (
    enrich_payload_with_tldrs,
    fallback_tldr,
    main,
    request_tldr,
    extract_paper_structure,
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


BRIEF_JSON = json.dumps(
    {
        "headline": "An agent-driven loop searches cache replacement designs with gem5 feedback.",
        "key_points": [
            {"label": "Problem", "text": "Design-space search for cache policies is slow and manual."},
            {"label": "Method", "text": "An LLM agent proposes candidates and evaluates them in gem5."},
            {"label": "Evidence", "text": "Simulated results improve miss rate and IPC over baselines."},
        ],
        "headline_zh": "用 gem5 反馈驱动的 agent 闭环搜索缓存替换策略设计。",
        "key_points_zh": [
            {"label": "问题", "text": "缓存策略的设计空间搜索又慢又依赖人工。"},
            {"label": "方法", "text": "LLM agent 提出候选并在 gem5 中评估。"},
            {"label": "证据", "text": "仿真结果显示 miss rate 与 IPC 均优于基线。"},
        ],
        "key_figure": {
            "label": "Figure 2",
            "caption": "IPC across policies",
            "explanation": "Higher bars mean faster execution.",
            "explanation_zh": "柱越高代表执行越快。",
        },
        "sections": [{"title": "Method", "summary": "The method is evaluated."}],
        "figures": [{"label": "Figure 1", "caption": "Speedup", "explanation": "Higher is better."}],
    }
)


class SummarizerTests(unittest.TestCase):
    def test_extract_paper_structure_reads_sections_and_figures(self):
        class HtmlResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self, size=None):
                return b"<h2>Method</h2><h3>Evaluation <span>Results</span></h3><figure><figcaption>Figure 2: Throughput by workload</figcaption></figure>"

        def opener(request, timeout=None):
            return HtmlResponse()

        structure = extract_paper_structure({"paper_id": "2601.12345"}, opener=opener)
        self.assertEqual(structure["sections"], ["Method", "Evaluation Results"])
        self.assertEqual(structure["figures"][0]["caption"], "Figure 2: Throughput by workload")

    def test_extract_paper_structure_ignores_arxiv_abs_page_redirect(self):
        class HtmlResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self, size=None):
                return (
                    b"<html><head><title>[2609.12923] Dissecting GPU Utilization</title></head><body>"
                    b"<h2>Submission history</h2><h3>BibTeX formatted citation</h3>"
                    b"<h2>Access Paper:</h2><h3>Bookmark</h3>"
                    b"</body></html>"
                )

        def opener(request, timeout=None):
            return HtmlResponse()

        structure = extract_paper_structure({"paper_id": "2609.12923"}, opener=opener)
        self.assertEqual(structure, {"sections": [], "figures": []})

    def test_extract_paper_structure_filters_abs_page_furniture_headings(self):
        class HtmlResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self, size=None):
                return b"<h2>Method</h2><h2>Submission history</h2>"

        def opener(request, timeout=None):
            return HtmlResponse()

        structure = extract_paper_structure({"paper_id": "2609.12923"}, opener=opener)
        self.assertEqual(structure["sections"], ["Method"])

    def test_parse_paper_summary_drops_empty_content_section_entries(self):
        from paper_recommender.summarizer import _parse_paper_summary

        summary = _parse_paper_summary(
            json.dumps(
                {
                    "headline": "A real contribution sentence that is long enough.",
                    "key_points": [
                        {"label": "Problem", "text": "Real problem."},
                        {"label": "Method", "text": "Real method."},
                        {"label": "Evidence", "text": "Real evidence."},
                    ],
                    "sections": [
                        {"title": "Method", "summary": "Real summary."},
                        {"title": "Submission history", "summary": "No content extracted from the public HTML copy."},
                    ],
                }
            )
        )

        self.assertEqual([entry["title"] for entry in summary["section_summaries"]], ["Method"])

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
        self.assertEqual(seen["body"]["max_tokens"], 1900)
        system_prompt = seen["body"]["messages"][0]["content"]
        self.assertIn("English", system_prompt)
        self.assertIn("valid json", system_prompt.lower())
        self.assertIn("headline", system_prompt)
        self.assertIn("key_points", system_prompt)
        self.assertIn("headline_zh", system_prompt)
        self.assertIn("key_points_zh", system_prompt)
        self.assertIn("Simplified Chinese", system_prompt)
        self.assertIn("Problem", system_prompt)
        self.assertIn("Method", system_prompt)
        self.assertIn("Evidence", system_prompt)
        self.assertIn("Impact", system_prompt)

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
        self.assertIn("what the repository implements", system_prompt)
        self.assertIn("Stars today: 87", user_prompt)
        self.assertIn("Topics: gem5, microarchitecture", user_prompt)
        self.assertIn("Original paper links: arXiv https://arxiv.org/abs/2606.00001", user_prompt)

    def test_enrich_payload_persists_structured_section_and_figure_summaries(self):
        def opener(request, timeout=None):
            if "ar5iv" in request.full_url:
                return FakeResponse({"html": "<h2>Method</h2><figcaption>Figure 1: Speedup</figcaption>"})
            return FakeResponse({"choices": [{"message": {"content": BRIEF_JSON}}]})

        enriched = enrich_payload_with_tldrs({"recommendations": [{"paper_id": "2601.12345", "title": "A", "abstract": "B"}]}, api_key="secret", opener=opener)
        item = enriched["recommendations"][0]
        self.assertIn("agent-driven loop", item["headline"])
        self.assertIn("agent-driven loop", item["tldr"])
        self.assertEqual(item["key_points"][0]["label"], "Problem")
        self.assertIn("缓存替换策略", item["headline_zh"])
        self.assertEqual(item["key_points_zh"][0]["label"], "问题")
        self.assertEqual(item["key_figure"]["explanation_zh"], "柱越高代表执行越快。")
        self.assertEqual(item["section_summaries"][0]["title"], "Method")
        self.assertEqual(item["figure_explanations"][0]["explanation"], "Higher is better.")

    def test_parse_paper_summary_accepts_plain_text_without_brief_fields(self):
        from paper_recommender.summarizer import request_paper_summary

        def opener(request, timeout=None):
            return FakeResponse({"choices": [{"message": {"content": "Just a plain legacy tldr sentence."}}]})

        summary = request_paper_summary({"title": "A", "abstract": "B"}, api_key="secret", opener=opener)
        self.assertEqual(summary["tldr"], "Just a plain legacy tldr sentence.")
        self.assertEqual(summary["headline"], "")
        self.assertEqual(summary["key_points"], [])

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
        calls = []

        def opener(request, timeout=None):
            if "ar5iv" in request.full_url:
                return FakeResponse({"html": ""})
            calls.append(json.loads(request.data.decode("utf-8")))
            if len(calls) == 1:
                return FakeResponse({"choices": [{"message": {"content": "Short summary."}}]})
            return FakeResponse({"choices": [{"message": {"content": BRIEF_JSON}}]})

        enriched = enrich_payload_with_tldrs(payload, api_key="secret", opener=opener, require_api=True)

        self.assertIn("agent-driven loop", enriched["recommendations"][0]["headline"])
        self.assertEqual(len(calls), 2)
        self.assertIn("previous output was too thin", calls[1]["messages"][0]["content"])

    def test_enrich_payload_with_tldrs_retries_transient_network_errors(self):
        payload = {
            "recommendations": [
                {
                    "paper_id": "p1",
                    "title": "Agentic Microarchitecture Exploration",
                    "abstract": "LLM agents explore cache replacement policies.",
                }
            ]
        }
        calls = []

        def opener(request, timeout=None):
            if "ar5iv" in request.full_url:
                return FakeResponse({"html": ""})
            calls.append(request.full_url)
            if len(calls) == 1:
                raise ConnectionResetError(104, "Connection reset by peer")
            return FakeResponse({"choices": [{"message": {"content": BRIEF_JSON}}]})

        with patch("paper_recommender.llm_retry.time.sleep") as sleeper:
            enriched = enrich_payload_with_tldrs(payload, api_key="secret", opener=opener)

        self.assertIn("agent-driven loop", enriched["recommendations"][0]["headline"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(sleeper.call_count, 1)

    def test_enrich_payload_with_tldrs_retries_missing_chinese_fields_then_keeps_english_brief(self):
        payload = {
            "recommendations": [
                {
                    "paper_id": "p1",
                    "title": "Agentic Microarchitecture Exploration",
                    "abstract": "LLM agents explore cache replacement policies.",
                }
            ]
        }
        english_only = json.dumps(
            {
                "headline": "An agent-driven loop searches cache replacement designs with gem5 feedback.",
                "key_points": [
                    {"label": "Problem", "text": "Design-space search for cache policies is slow and manual."},
                    {"label": "Method", "text": "An LLM agent proposes candidates and evaluates them in gem5."},
                    {"label": "Evidence", "text": "Simulated results improve miss rate and IPC over baselines."},
                ],
            }
        )
        calls = []

        def opener(request, timeout=None):
            if "ar5iv" in request.full_url:
                return FakeResponse({"html": ""})
            calls.append(request.data.decode("utf-8"))
            return FakeResponse({"choices": [{"message": {"content": english_only}}]})

        enriched = enrich_payload_with_tldrs(payload, api_key="secret", opener=opener, require_api=True)

        item = enriched["recommendations"][0]
        self.assertEqual(len(calls), 2)
        self.assertIn("Chinese fields", calls[1])
        self.assertIn("agent-driven loop", item["headline"])
        self.assertEqual(item["headline_zh"], "")
        self.assertEqual(item["key_points_zh"], [])

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

        calls = []

        def opener(request):
            calls.append(request.full_url)
            raise HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                hdrs=None,
                fp=FakeErrorBody('{"error":"invalid api key unit-test-secret"}'),
            )

        with patch("paper_recommender.llm_retry.time.sleep") as sleeper:
            with self.assertRaises(RuntimeError) as context:
                enrich_payload_with_tldrs(
                    payload,
                    api_key="unit-test-secret",
                    base_url="https://opencode.ai/zen/go/v1",
                    model="deepseek-v4-flash",
                    opener=opener,
                    require_api=True,
                )

        llm_calls = [url for url in calls if "ar5iv" not in url]
        self.assertEqual(len(llm_calls), 1)
        self.assertEqual(sleeper.call_count, 0)
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

        self.assertIn("summary brief is too thin", str(context.exception))

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
