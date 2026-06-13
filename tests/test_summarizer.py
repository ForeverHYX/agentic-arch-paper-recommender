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
        self.assertNotIn("This paper studies", text)
        self.assertNotIn("LLM agents can search", text)

    def test_request_tldr_calls_openai_compatible_chat_completion(self):
        seen = {}

        def opener(request, timeout=None):
            seen["url"] = request.full_url
            seen["body"] = json.loads(request.data.decode("utf-8"))
            seen["authorization"] = request.headers["Authorization"]
            seen["user_agent"] = request.get_header("User-agent")
            seen["timeout"] = timeout
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
        self.assertIn("agentic-arch-paper-recommender", seen["user_agent"])
        self.assertGreaterEqual(seen["timeout"], 180)
        self.assertEqual(seen["body"]["model"], "deepseek-v4-flash")
        self.assertEqual(seen["body"]["thinking"], {"type": "disabled"})
        self.assertGreaterEqual(seen["body"]["max_tokens"], 8192)
        self.assertLessEqual(seen["body"]["max_tokens"], 9000)
        system_prompt = seen["body"]["messages"][0]["content"]
        self.assertIn("简体中文", system_prompt)
        self.assertIn("只输出最终答案", system_prompt)
        self.assertIn("不要解释", system_prompt)
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
            "研究问题：这篇论文关注如何让 LLM agent 结合体系结构模拟器搜索微架构设计空间，"
            "目标是在缓存和分支预测等部件上减少人工试错成本。核心方法：系统把候选设计生成、"
            "仿真评估和反馈修正串成闭环，用性能计数器和规则约束指导下一轮候选。关键结论："
            "摘要显示该流程能在典型 benchmark 上改善 IPC 和 miss-rate，但仍需核对实验规模。"
            "推荐理由：它同时命中 agentic 架构探索和模拟器驱动优化，适合优先略读方法与实验。"
        )
        calls = []

        def opener(request, timeout=None):
            calls.append(json.loads(request.data.decode("utf-8")))
            if len(calls) == 1:
                return FakeResponse({"choices": [{"message": {"content": "一句话总结。"}}]})
            return FakeResponse({"choices": [{"message": {"content": long_tldr}}]})

        enriched = enrich_payload_with_tldrs(payload, api_key="secret", opener=opener, require_api=True)

        self.assertEqual(enriched["recommendations"][0]["tldr"], long_tldr)
        self.assertEqual(len(calls), 2)
        self.assertIn("上一次输出过短", calls[1]["messages"][0]["content"])

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
            return FakeResponse({"choices": [{"message": {"content": "一句话总结。"}}]})

        with self.assertRaises(RuntimeError) as context:
            enrich_payload_with_tldrs(payload, api_key="secret", opener=opener, require_api=True)

        self.assertIn("TLDR 过短", str(context.exception))

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
