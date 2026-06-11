import json
import tempfile
import unittest
from pathlib import Path

from paper_recommender.feedback import (
    FeedbackEvent,
    feedback_events_from_records,
    load_feedback_json,
    section_feedback_weights,
    text_feedback_weights,
    write_feedback_json,
)


class FeedbackTests(unittest.TestCase):
    def test_feedback_events_from_records_normalizes_valid_rows(self):
        events = feedback_events_from_records(
            [
                {
                    "paper_id": "p1",
                    "rating": "like",
                    "section": "agentic_architecture",
                    "source": "email",
                },
                {"paper_id": "p2", "rating": "skip", "section": "noise"},
            ]
        )

        self.assertEqual(
            events,
            [
                FeedbackEvent(
                    paper_id="p1",
                    rating="like",
                    section="agentic_architecture",
                    source="email",
                )
            ],
        )

    def test_section_feedback_weights_counts_likes_and_dislikes(self):
        weights = section_feedback_weights(
            [
                FeedbackEvent("p1", "like", "agentic_architecture", "page"),
                FeedbackEvent("p2", "like", "agentic_architecture", "email"),
                FeedbackEvent("p3", "dislike", "hpc_cross_over", "page"),
            ]
        )

        self.assertEqual(weights["agentic_architecture"], 2.0)
        self.assertEqual(weights["hpc_cross_over"], -1.0)

    def test_load_feedback_json_reads_supabase_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback.json"
            path.write_text(
                json.dumps([{"paper_id": "p1", "rating": "dislike", "section": "hpc_cross_over"}]),
                encoding="utf-8",
            )

            events = load_feedback_json(path)

        self.assertEqual(events[0].paper_id, "p1")
        self.assertEqual(events[0].rating, "dislike")

    def test_feedback_events_preserve_paper_metadata_for_learning(self):
        events = feedback_events_from_records(
            [
                {
                    "paper_id": "arch",
                    "rating": "like",
                    "section": "agentic_architecture",
                    "source": "page",
                    "title": "Agentic AI-Driven Microarchitecture Exploration",
                    "abstract": "A hardware design agent uses gem5 for cache replacement policy search.",
                    "authors": ["A. Architect"],
                    "categories": ["cs.AR", "cs.AI"],
                }
            ]
        )

        self.assertEqual(events[0].title, "Agentic AI-Driven Microarchitecture Exploration")
        self.assertIn("hardware design agent", events[0].abstract)
        self.assertEqual(events[0].authors, ("A. Architect",))
        self.assertEqual(events[0].categories, ("cs.AR", "cs.AI"))

    def test_write_feedback_json_preserves_learning_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback.json"
            write_feedback_json(
                [
                    FeedbackEvent(
                        paper_id="arch",
                        rating="like",
                        section="agentic_architecture",
                        source="email",
                        title="Agentic AI-Driven Microarchitecture Exploration",
                        abstract="gem5 based microarchitecture design space exploration.",
                        authors=["A. Architect"],
                        categories=["cs.AR"],
                    )
                ],
                path,
            )

            rows = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(rows[0]["title"], "Agentic AI-Driven Microarchitecture Exploration")
        self.assertEqual(rows[0]["authors"], ["A. Architect"])

    def test_text_feedback_weights_learn_from_likes_and_dislikes(self):
        weights = text_feedback_weights(
            [
                FeedbackEvent(
                    "liked",
                    "like",
                    "microarchitecture_simulators",
                    title="gem5 cache replacement exploration",
                    abstract="cycle accurate microarchitecture simulation search.",
                    authors=["Sample Architect"],
                    categories=["cs.AR"],
                ),
                FeedbackEvent(
                    "disliked",
                    "dislike",
                    "hpc_cross_over",
                    title="web agent benchmark",
                    abstract="browser task automation with retrieval augmented generation",
                ),
            ]
        )

        self.assertGreater(weights["gem5"], 0)
        self.assertGreater(weights["cache"], 0)
        self.assertLess(weights["browser"], 0)
        self.assertGreater(weights["search"], 0)
        self.assertNotIn("search.", weights)
        self.assertNotIn("sample", weights)
        self.assertNotIn("cs.ar", weights)
        self.assertNotIn("with", weights)


if __name__ == "__main__":
    unittest.main()
