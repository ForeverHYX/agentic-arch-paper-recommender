import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from paper_recommender.profile_review import (
    enrich_payload_with_profile_review,
    main,
    parse_profile_review_response,
    request_profile_review,
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


class ProfileReviewTests(unittest.TestCase):
    def test_parse_profile_review_response_forces_non_runtime_overlay(self):
        review = parse_profile_review_response(
            json.dumps(
                {
                    "summary_zh": "反馈显示更偏好 GPU 系统。",
                    "positive_adjustments": ["增强 GPU/ML systems"],
                    "negative_adjustments": ["降低泛 Web agent"],
                    "exploration_notes": ["探索反馈仍少"],
                    "risk_notes": ["样本不足"],
                    "apply_to_runtime": True,
                },
                ensure_ascii=False,
            )
        )

        self.assertFalse(review["apply_to_runtime"])
        self.assertIn("GPU", review["summary_zh"])
        self.assertEqual(review["positive_adjustments"], ["增强 GPU/ML systems"])
        self.assertEqual(review["negative_adjustments"], ["降低泛 Web agent"])
        self.assertEqual(review["exploration_notes"], ["探索反馈仍少"])
        self.assertEqual(review["risk_notes"], ["样本不足"])

    def test_request_profile_review_calls_openai_compatible_chat_completion(self):
        seen = {}

        def opener(request):
            seen["url"] = request.full_url
            seen["body"] = json.loads(request.data.decode("utf-8"))
            seen["authorization"] = request.headers["Authorization"]
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "summary_zh": "反馈显示更偏好 GPU 系统和 ML 编译器。",
                                        "positive_adjustments": ["增强 GPU 系统"],
                                        "negative_adjustments": ["降低泛 Web agent"],
                                        "exploration_notes": ["继续观察 AI+体系结构探索"],
                                        "risk_notes": ["反馈样本仍少"],
                                        "apply_to_runtime": False,
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                }
            )

        review = request_profile_review(
            {"name": "Agentic Architecture", "core_categories": ["cs.AR"]},
            {
                "feedback_summary": {"metrics": {"total_events": 3}},
                "recommendations": [
                    {
                        "title": "GPU Runtime for ML Systems",
                        "sections": ["exploration"],
                        "ai_judgement": {"score": 7, "reason": "探索相关。"},
                    }
                ],
            },
            api_key="secret",
            base_url="https://example.com/v1",
            model="deepseek-v4-flash",
            opener=opener,
        )

        self.assertEqual(seen["url"], "https://example.com/v1/chat/completions")
        self.assertEqual(seen["authorization"], "Bearer secret")
        self.assertEqual(seen["body"]["model"], "deepseek-v4-flash")
        self.assertEqual(seen["body"]["thinking"], {"type": "disabled"})
        prompt = seen["body"]["messages"][1]["content"]
        self.assertIn("Agentic Architecture", prompt)
        self.assertIn("GPU Runtime for ML Systems", prompt)
        self.assertIn("exploration", prompt)
        self.assertFalse(review["apply_to_runtime"])
        self.assertIn("GPU", review["summary_zh"])

    def test_enrich_payload_with_profile_review_requires_api_without_leaking_key(self):
        payload = {"recommendations": [{"title": "GPU Runtime", "sections": ["exploration"]}]}
        profile = {"name": "Agentic Architecture"}

        def opener(request):
            raise HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                hdrs=None,
                fp=FakeErrorBody('{"error":"invalid api key unit-test-secret"}'),
            )

        with self.assertRaises(RuntimeError) as context:
            enrich_payload_with_profile_review(
                payload,
                profile,
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

    def test_cli_writes_review_and_updates_recommendation_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            profile_path = tmp / "interests.json"
            recommendations_path = tmp / "recommendations.json"
            review_path = tmp / "profile_review.json"
            profile_path.write_text(json.dumps({"name": "Agentic Architecture"}), encoding="utf-8")
            recommendations_path.write_text(
                json.dumps({"recommendations": [{"title": "GPU Runtime", "sections": ["exploration"]}]}),
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "--profile",
                    str(profile_path),
                    "--recommendations",
                    str(recommendations_path),
                    "--output",
                    str(review_path),
                ]
            )

            self.assertEqual(exit_code, 0)
            review = json.loads(review_path.read_text(encoding="utf-8"))
            payload = json.loads(recommendations_path.read_text(encoding="utf-8"))
            self.assertFalse(review["apply_to_runtime"])
            self.assertEqual(payload["profile_review"], review)


if __name__ == "__main__":
    unittest.main()
