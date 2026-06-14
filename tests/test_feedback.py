import json
import os
import tempfile
import unittest
from pathlib import Path

from paper_recommender.feedback import (
    FeedbackEvent,
    author_feedback_weights,
    affiliation_feedback_weights,
    feedback_events_from_records,
    feedback_events_from_json_text,
    feedback_metrics,
    load_feedback_json,
    section_feedback_weights,
    text_feedback_weights,
    toolchain_feedback_weights,
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

    def test_feedback_events_from_json_text_accepts_local_export_shape(self):
        events = feedback_events_from_json_text(
            json.dumps(
                [
                    {
                        "paper_id": "local-liked",
                        "rating": "like",
                        "section": "arch",
                        "title": "Local exported feedback",
                    }
                ]
            )
        )

        self.assertEqual(events[0].paper_id, "local-liked")
        self.assertEqual(events[0].title, "Local exported feedback")

    def test_feedback_cli_can_write_events_from_environment_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "feedback.json"
            old_value = os.environ.get("LOCAL_FEEDBACK_JSON")
            os.environ["LOCAL_FEEDBACK_JSON"] = json.dumps(
                [{"paper_id": "secret-liked", "rating": "like", "section": "arch"}]
            )
            try:
                from paper_recommender.feedback import main

                exit_code = main(["--from-env", "LOCAL_FEEDBACK_JSON", "--output", str(path)])
            finally:
                if old_value is None:
                    os.environ.pop("LOCAL_FEEDBACK_JSON", None)
                else:
                    os.environ["LOCAL_FEEDBACK_JSON"] = old_value

            rows = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(rows[0]["paper_id"], "secret-liked")
        self.assertEqual(rows[0]["rating"], "like")

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
                    "affiliations": ["University of Architecture"],
                    "categories": ["cs.AR", "cs.AI"],
                }
            ]
        )

        self.assertEqual(events[0].title, "Agentic AI-Driven Microarchitecture Exploration")
        self.assertIn("hardware design agent", events[0].abstract)
        self.assertEqual(events[0].authors, ("A. Architect",))
        self.assertEqual(events[0].affiliations, ("University of Architecture",))
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
                        affiliations=["University of Architecture"],
                        categories=["cs.AR"],
                    )
                ],
                path,
            )

            rows = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(rows[0]["title"], "Agentic AI-Driven Microarchitecture Exploration")
        self.assertEqual(rows[0]["authors"], ["A. Architect"])
        self.assertEqual(rows[0]["affiliations"], ["University of Architecture"])

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

    def test_text_feedback_weights_filter_generic_words_and_numeric_ranges(self):
        weights = text_feedback_weights(
            [
                FeedbackEvent(
                    "liked",
                    "like",
                    "exploration",
                    title="A detailed framework which improves communication",
                    abstract=(
                        "The paper discusses further implementations, efficiency, efficient emerging systems, "
                        "and size 4--6 results."
                    ),
                ),
                FeedbackEvent(
                    "liked-domain",
                    "like",
                    "microarchitecture_simulators",
                    title="gem5 cache replacement exploration",
                    abstract="Cycle accurate microarchitecture simulation for GPU memory hierarchy.",
                ),
            ]
        )

        for noisy in (
            "which",
            "communication",
            "detailed",
            "framework",
            "further",
            "implementations",
            "size",
            "4--6",
            "accurate",
            "cycle",
            "efficiency",
            "efficient",
            "emerging",
        ):
            self.assertNotIn(noisy, weights)
        self.assertGreater(weights["gem5"], 0)
        self.assertGreater(weights["cache"], 0)
        self.assertGreater(weights["microarchitecture"], 0)

    def test_entity_feedback_weights_learn_authors_affiliations_and_toolchains(self):
        events = [
            FeedbackEvent(
                "liked",
                "like",
                "microarchitecture_simulators",
                title="gem5 and MLIR for accelerator simulation",
                abstract="A gem5 workflow with Accel-Sim and CIRCT.",
                authors=["A. Architect", "B. Systems"],
                affiliations=["University of Architecture", "National HPC Lab"],
            ),
            FeedbackEvent(
                "disliked",
                "dislike",
                "hpc_cross_over",
                title="CUDA kernel benchmark",
                abstract="A CUDA and OpenMP benchmark without architecture insight.",
                authors=["C. Benchmark"],
                affiliations=["Generic Benchmark Institute"],
            ),
        ]

        self.assertEqual(author_feedback_weights(events)["A. Architect"], 1.0)
        self.assertEqual(author_feedback_weights(events)["C. Benchmark"], -1.0)
        self.assertEqual(affiliation_feedback_weights(events)["University of Architecture"], 1.0)
        self.assertEqual(affiliation_feedback_weights(events)["Generic Benchmark Institute"], -1.0)
        toolchains = toolchain_feedback_weights(events)
        self.assertEqual(toolchains["gem5"], 1.0)
        self.assertEqual(toolchains["mlir"], 1.0)
        self.assertEqual(toolchains["accel-sim"], 1.0)
        self.assertEqual(toolchains["cuda"], -1.0)
        self.assertEqual(toolchains["openmp"], -1.0)

    def test_feedback_metrics_summarize_activity_and_topics(self):
        events = [
            FeedbackEvent(
                "liked-1",
                "like",
                "agentic_architecture",
                source="page",
                title="gem5 agentic architecture exploration",
                abstract="A gem5 architecture design agent with MLIR.",
                authors=["A. Architect"],
                affiliations=["University of Architecture"],
            ),
            FeedbackEvent(
                "liked-2",
                "like",
                "agentic_architecture",
                source="email",
                title="MLIR hardware software co-design",
                abstract="Full-stack co-design with gem5.",
                authors=["A. Architect"],
                affiliations=["University of Architecture"],
            ),
            FeedbackEvent(
                "disliked-1",
                "dislike",
                "hpc_cross_over",
                source="page",
                title="web agent benchmark",
                abstract="Browser automation benchmark without architecture insight.",
                authors=["Generic Author"],
                affiliations=["Generic Benchmark Institute"],
            ),
        ]

        metrics = feedback_metrics(events)

        self.assertEqual(metrics["total_events"], 3)
        self.assertEqual(metrics["like_count"], 2)
        self.assertEqual(metrics["dislike_count"], 1)
        self.assertAlmostEqual(metrics["like_rate"], 2 / 3)
        self.assertEqual(metrics["source_counts"]["page"], 2)
        self.assertEqual(metrics["section_counts"]["agentic_architecture"], 2)
        self.assertIn("gem5", metrics["top_liked_keywords"])
        self.assertIn("browser", metrics["top_disliked_keywords"])
        self.assertEqual(metrics["top_liked_authors"][0], "A. Architect")
        self.assertEqual(metrics["top_disliked_authors"][0], "Generic Author")
        self.assertIn("University of Architecture", metrics["top_liked_affiliations"])
        self.assertIn("Generic Benchmark Institute", metrics["top_disliked_affiliations"])
        self.assertIn("gem5", metrics["top_liked_toolchains"])


if __name__ == "__main__":
    unittest.main()
