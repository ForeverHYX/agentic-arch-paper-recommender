import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from paper_recommender.judge import (
    enrich_payload_with_judgements,
    fallback_judgement,
    main,
    parse_judgement_response,
    request_judgement,
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


class JudgeTests(unittest.TestCase):
    def test_parse_judgement_response_accepts_markdown_json(self):
        judgement = parse_judgement_response(
            '```json\n{"score": 8.5, "reason": "贴合自动架构探索。", "decision": "keep"}\n```'
        )

        self.assertEqual(judgement["score"], 8.5)
        self.assertEqual(judgement["reason"], "贴合自动架构探索。")
        self.assertEqual(judgement["decision"], "keep")

    def test_parse_judgement_response_accepts_plain_text_model_judgement(self):
        judgement = parse_judgement_response(
            "Score: 8.5\nDecision: keep\nReason: It directly studies simulator-guided architecture exploration."
        )

        self.assertEqual(judgement["score"], 8.5)
        self.assertEqual(judgement["decision"], "keep")
        self.assertIn("simulator-guided", judgement["reason"])

    def test_parse_judgement_response_reports_preview_when_score_is_missing(self):
        with self.assertRaises(ValueError) as context:
            parse_judgement_response("This is relevant because it discusses architecture exploration.")

        self.assertIn("LLM 响应中没有 JSON 对象", str(context.exception))
        self.assertIn("This is relevant", str(context.exception))

    def test_parse_judgement_response_recovers_truncated_json_with_score_and_reason(self):
        judgement = parse_judgement_response(
            '{"score": 8.5, "reason": "高度贴合自动架构探索，但需要结合论文实验继续确认'
        )

        self.assertEqual(judgement["score"], 8.5)
        self.assertEqual(judgement["decision"], "keep")
        self.assertIn("高度贴合自动架构探索", judgement["reason"])

    def test_fallback_judgement_uses_rule_score_when_model_is_unavailable(self):
        judgement = fallback_judgement({"score": 7.0, "sections": ["agentic_architecture"]})

        self.assertGreater(judgement["score"], 0)
        self.assertEqual(judgement["decision"], "keep")
        self.assertIn("规则得分", judgement["reason"])

    def test_request_judgement_calls_openai_compatible_chat_completion(self):
        seen = {}

        def opener(request):
            seen["url"] = request.full_url
            seen["body"] = json.loads(request.data.decode("utf-8"))
            seen["authorization"] = request.headers["Authorization"]
            seen["user_agent"] = request.get_header("User-agent")
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"score": 9, "reason": "强相关。", "decision": "keep"}'
                            }
                        }
                    ]
                }
            )

        judgement = request_judgement(
            {
                "title": "Agentic Microarchitecture Exploration",
                "abstract": "LLM agents explore cache replacement policies with gem5.",
                "affiliations": ["University of Architecture", "National HPC Lab"],
                "score": 3.0,
            },
            api_key="secret",
            profile_name="Agentic Architecture",
            section_labels={"agentic_architecture": "Agentic Architecture / Auto-DSE"},
            base_url="https://example.com/v1",
            model="deepseek-v4-flash",
            opener=opener,
        )

        self.assertEqual(judgement["score"], 9.0)
        self.assertEqual(judgement["decision"], "keep")
        self.assertEqual(seen["url"], "https://example.com/v1/chat/completions")
        self.assertEqual(seen["authorization"], "Bearer secret")
        self.assertIn("agentic-arch-paper-recommender", seen["user_agent"])
        self.assertEqual(seen["body"]["model"], "deepseek-v4-flash")
        self.assertLessEqual(seen["body"]["max_tokens"], 256)
        self.assertNotIn("response_format", seen["body"])
        self.assertIn("reason 使用简体中文", seen["body"]["messages"][0]["content"])
        self.assertIn("80 个汉字以内", seen["body"]["messages"][0]["content"])
        self.assertIn("Agentic Microarchitecture Exploration", seen["body"]["messages"][1]["content"])
        self.assertIn("University of Architecture", seen["body"]["messages"][1]["content"])
        self.assertIn("Affiliations", seen["body"]["messages"][1]["content"])

    def test_request_judgement_reports_empty_content_metadata(self):
        def opener(request):
            return FakeResponse(
                {
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "reasoning_content": "",
                            },
                        }
                    ],
                    "usage": {"completion_tokens": 220},
                }
            )

        with self.assertRaises(ValueError) as context:
            request_judgement(
                {
                    "title": "Agentic Microarchitecture Exploration",
                    "abstract": "LLM agents explore cache replacement policies with gem5.",
                },
                api_key="secret",
                opener=opener,
            )

        message = str(context.exception)
        self.assertIn("LLM 返回空 judgement 内容", message)
        self.assertIn("finish_reason=length", message)
        self.assertIn("reasoning_content", message)

    def test_request_judgement_includes_learned_feedback_profile(self):
        seen = {}

        def opener(request):
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"score": 8, "reason": "符合反馈画像。", "decision": "keep"}'
                            }
                        }
                    ]
                }
            )

        request_judgement(
            {
                "title": "GPU Simulator for HPC Kernels",
                "abstract": "A simulator evaluates GPU memory hierarchy behavior.",
                "score": 4.0,
            },
            api_key="secret",
            feedback_summary={
                "section_weights": {"microarchitecture_simulators": 2.0, "hpc_cross_over": -1.0},
                "keyword_weights": {"gem5": 2.0, "browser": -2.0, "cache": 1.0},
                "author_weights": {"A. Architect": 1.0, "Generic Author": -1.0},
                "affiliation_weights": {"University of Architecture": 1.0, "Generic Benchmark Institute": -1.0},
                "toolchain_weights": {"gem5": 2.0, "cuda": -1.0},
            },
            opener=opener,
        )

        prompt = seen["body"]["messages"][1]["content"]
        self.assertIn("Learned feedback profile", prompt)
        self.assertIn("Prefer sections: microarchitecture_simulators", prompt)
        self.assertIn("Avoid sections: hpc_cross_over", prompt)
        self.assertIn("Prefer keywords: gem5, cache", prompt)
        self.assertIn("Avoid keywords: browser", prompt)
        self.assertIn("Prefer authors: A. Architect", prompt)
        self.assertIn("Avoid authors: Generic Author", prompt)
        self.assertIn("Prefer affiliations: University of Architecture", prompt)
        self.assertIn("Avoid affiliations: Generic Benchmark Institute", prompt)
        self.assertIn("Prefer toolchains: gem5", prompt)
        self.assertIn("Avoid toolchains: cuda", prompt)

    def test_request_judgement_includes_seed_papers_as_interest_anchors(self):
        seen = {}

        def opener(request):
            seen["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"score": 9, "reason": "贴近种子论文画像。", "decision": "keep"}'
                            }
                        }
                    ]
                }
            )

        request_judgement(
            {
                "title": "Agentic Architecture Design Space Exploration",
                "abstract": "A hardware design agent explores microarchitecture choices.",
                "score": 5.0,
            },
            api_key="secret",
            seed_papers=[
                {
                    "title": "Computer Architecture's AlphaZero Moment",
                    "notes": "Positive seed for automated architecture discovery.",
                    "keywords": ["automated architecture discovery", "design space exploration"],
                }
            ],
            opener=opener,
        )

        prompt = seen["body"]["messages"][1]["content"]
        self.assertIn("Representative seed papers", prompt)
        self.assertIn("Computer Architecture's AlphaZero Moment", prompt)
        self.assertIn("Positive seed for automated architecture discovery", prompt)
        self.assertIn("automated architecture discovery", prompt)

    def test_enrich_payload_with_judgements_reranks_and_limits_by_ai_score(self):
        payload = {
            "profile_name": "Agentic Architecture",
            "section_labels": {"agentic_architecture": "Agentic Architecture / Auto-DSE"},
            "recommendations": [
                {
                    "rank": 1,
                    "paper_id": "rule-high",
                    "title": "Generic Agent Benchmark",
                    "abstract": "A browser agent benchmark.",
                    "score": 20.0,
                    "sections": ["agentic_architecture"],
                },
                {
                    "rank": 2,
                    "paper_id": "ai-high",
                    "title": "AlphaZero Moment for Computer Architecture",
                    "abstract": "Automated discovery for architecture design space exploration.",
                    "score": 3.0,
                    "sections": ["agentic_architecture"],
                },
                {
                    "rank": 3,
                    "paper_id": "ai-mid",
                    "title": "GPU Simulator for HPC Kernels",
                    "abstract": "A simulator evaluates GPU memory hierarchy behavior for HPC.",
                    "score": 4.0,
                    "sections": ["microarchitecture_simulators"],
                },
            ],
        }

        def opener(request):
            body = json.loads(request.data.decode("utf-8"))
            prompt = body["messages"][1]["content"]
            if "Generic Agent Benchmark" in prompt:
                content = '{"score": 2, "reason": "泛 agent benchmark。", "decision": "drop"}'
            elif "AlphaZero Moment" in prompt:
                content = '{"score": 9, "reason": "高度贴合自动架构探索。", "decision": "keep"}'
            else:
                content = '{"score": 6, "reason": "贴合 GPU/HPC 模拟。", "decision": "keep"}'
            return FakeResponse({"choices": [{"message": {"content": content}}]})

        enriched = enrich_payload_with_judgements(payload, api_key="secret", limit=2, opener=opener)

        self.assertEqual(enriched["count"], 2)
        self.assertEqual([item["paper_id"] for item in enriched["recommendations"]], ["ai-high", "ai-mid"])
        self.assertEqual([item["rank"] for item in enriched["recommendations"]], [1, 2])
        self.assertEqual(enriched["recommendations"][0]["ai_score"], 9.0)
        self.assertEqual(enriched["recommendations"][0]["ai_judgement"]["decision"], "keep")
        self.assertIn("高度贴合", enriched["recommendations"][0]["ai_judgement"]["reason"])

    def test_enrich_payload_with_judgements_passes_profile_seed_papers_to_model(self):
        payload = {
            "profile_name": "Agentic Architecture",
            "profile_context": {
                "seed_papers": [
                    {
                        "title": "ASSASSYN-style Full-stack Co-design",
                        "notes": "Positive seed for full-stack hardware/software co-design.",
                        "keywords": ["full-stack co-design"],
                    }
                ]
            },
            "recommendations": [
                {
                    "rank": 1,
                    "paper_id": "codesign",
                    "title": "Full-stack Accelerator Co-design",
                    "abstract": "Compiler and hardware are optimized together.",
                    "score": 5.0,
                }
            ],
        }
        seen = {}

        def opener(request):
            seen["prompt"] = json.loads(request.data.decode("utf-8"))["messages"][1]["content"]
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"score": 8, "reason": "符合 seed。", "decision": "keep"}'
                            }
                        }
                    ]
                }
            )

        enrich_payload_with_judgements(payload, api_key="secret", opener=opener)

        self.assertIn("ASSASSYN-style Full-stack Co-design", seen["prompt"])

    def test_enrich_payload_with_judgements_excludes_dropped_papers_even_when_under_limit(self):
        payload = {
            "recommendations": [
                {"rank": 1, "paper_id": "keep", "title": "GPU Simulator for HPC", "abstract": "", "score": 4.0},
                {"rank": 2, "paper_id": "drop", "title": "Generic Web Agent", "abstract": "", "score": 9.0},
            ],
        }

        def opener(request):
            body = json.loads(request.data.decode("utf-8"))
            prompt = body["messages"][1]["content"]
            if "Generic Web Agent" in prompt:
                content = '{"score": 1, "reason": "泛 Web agent。", "decision": "drop"}'
            else:
                content = '{"score": 7, "reason": "相关。", "decision": "keep"}'
            return FakeResponse({"choices": [{"message": {"content": content}}]})

        enriched = enrich_payload_with_judgements(payload, api_key="secret", limit=15, opener=opener)

        self.assertEqual(enriched["count"], 1)
        self.assertEqual([item["paper_id"] for item in enriched["recommendations"]], ["keep"])
        self.assertEqual(enriched["judge_summary"]["dropped_count"], 1)

    def test_enrich_payload_with_judgements_requires_api_without_leaking_key(self):
        payload = {
            "recommendations": [
                {
                    "rank": 1,
                    "paper_id": "p1",
                    "title": "Agentic Microarchitecture Exploration",
                    "abstract": "LLM agents explore cache replacement policies.",
                    "score": 5.0,
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
            enrich_payload_with_judgements(
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

    def test_cli_updates_recommendation_json_with_fallback_judgement(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "recommendations.json"
            path.write_text(
                json.dumps(
                    {
                        "recommendations": [
                            {
                                "rank": 1,
                                "paper_id": "p1",
                                "title": "Agentic Microarchitecture Exploration",
                                "abstract": "LLM agents explore cache replacement policies.",
                                "score": 5.0,
                            },
                            {
                                "rank": 2,
                                "paper_id": "p2",
                                "title": "Weak Candidate",
                                "abstract": "Some unrelated content.",
                                "score": 1.0,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(["--input", str(path), "--output", str(path), "--limit", "1"])

            self.assertEqual(exit_code, 0)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["count"], 1)
            self.assertIn("ai_judgement", payload["recommendations"][0])


if __name__ == "__main__":
    unittest.main()
