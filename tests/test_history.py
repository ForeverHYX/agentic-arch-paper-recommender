import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request

from paper_recommender.history import (
    RecommendationRun,
    fetch_recommendation_history,
    history_counts,
    load_history_json,
    publish_recommendation_runs,
    recommendation_runs_from_payload,
    write_history_json,
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


class HistoryTests(unittest.TestCase):
    def test_history_counts_repeated_papers(self):
        counts = history_counts(
            [
                RecommendationRun("p1", "2026-06-10", 1, 10.0, "arch"),
                RecommendationRun("p1", "2026-06-11", 3, 8.0, "arch"),
                RecommendationRun("p2", "2026-06-11", 2, 9.0, "hpc"),
            ]
        )

        self.assertEqual(counts, {"p1": 2, "p2": 1})

    def test_load_and_write_history_json_preserves_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "history.json"
            write_history_json([RecommendationRun("p1", "2026-06-11", 2, 9.5, "arch")], path)

            runs = load_history_json(path)

        self.assertEqual(runs, [RecommendationRun("p1", "2026-06-11", 2, 9.5, "arch")])

    def test_recommendation_runs_from_payload_serializes_primary_section(self):
        runs = recommendation_runs_from_payload(
            {
                "run_date": "2026-06-12",
                "recommendations": [
                    {
                        "paper_id": "p1",
                        "rank": 1,
                        "score": 12.0,
                        "sections": ["agentic_architecture", "microarchitecture_simulators"],
                    }
                ],
            },
            shown_in_email=True,
        )

        self.assertEqual(runs[0].paper_id, "p1")
        self.assertEqual(runs[0].section, "agentic_architecture")
        self.assertTrue(runs[0].shown_in_email)

    def test_fetch_recommendation_history_uses_service_role_key(self):
        seen_requests: list[Request] = []

        def opener(request):
            seen_requests.append(request)
            return FakeResponse(
                [
                    {
                        "paper_id": "p1",
                        "run_date": "2026-06-11",
                        "rank": 1,
                        "score": 12.0,
                        "section": "arch",
                        "shown_in_email": False,
                        "shown_on_page": True,
                    }
                ]
            )

        runs = fetch_recommendation_history("https://example.supabase.co", "service-key", opener=opener)

        self.assertEqual(runs[0].paper_id, "p1")
        self.assertIn("/rest/v1/recommendation_runs?", seen_requests[0].full_url)
        self.assertEqual(seen_requests[0].headers["Apikey"], "service-key")

    def test_publish_recommendation_runs_upserts_payload_rows(self):
        seen_requests: list[Request] = []

        def opener(request):
            seen_requests.append(request)
            return FakeResponse([])

        publish_recommendation_runs(
            "https://example.supabase.co",
            "service-key",
            {
                "run_date": "2026-06-12",
                "recommendations": [
                    {
                        "paper_id": "p1",
                        "rank": 1,
                        "score": 12.0,
                        "sections": ["arch"],
                        "title": "A paper",
                    }
                ],
            },
            opener=opener,
        )

        body = json.loads(seen_requests[0].data.decode("utf-8"))
        self.assertIn("on_conflict=run_date%2Cpaper_id", seen_requests[0].full_url)
        self.assertEqual(body[0]["paper_id"], "p1")
        self.assertEqual(body[0]["payload"]["title"], "A paper")
        self.assertIn("resolution=merge-duplicates", seen_requests[0].headers["Prefer"])


if __name__ == "__main__":
    unittest.main()
