import unittest

from paper_recommender.domain import InterestProfile, Paper, SectionRule
from paper_recommender.feedback import FeedbackEvent
from paper_recommender.history import RecommendationRun
from paper_recommender.pipeline import recommendation_payload


class FeedbackPipelineTests(unittest.TestCase):
    def test_feedback_section_weights_adjust_recommendation_order(self):
        profile = InterestProfile(
            name="Custom",
            core_categories=frozenset({"cs.TEST"}),
            expansion_categories=frozenset(),
            sections=(
                SectionRule("liked_section", "Liked Section", 1.0, ("shared",)),
                SectionRule("disliked_section", "Disliked Section", 1.0, ("other",)),
            ),
        )
        liked = Paper("liked", "Shared topic", "shared", [], ["cs.TEST"])
        disliked = Paper("disliked", "Other topic", "other other other", [], ["cs.TEST"])

        payload = recommendation_payload(
            [disliked, liked],
            run_date="2026-06-12",
            profile=profile,
            feedback_events=[
                FeedbackEvent("old-1", "like", "liked_section", "page"),
                FeedbackEvent("old-2", "dislike", "disliked_section", "page"),
            ],
        )

        self.assertEqual(payload["recommendations"][0]["paper_id"], "liked")
        self.assertEqual(payload["feedback_summary"]["section_weights"]["liked_section"], 1.0)

    def test_feedback_text_similarity_adjusts_recommendation_order(self):
        profile = InterestProfile(
            name="Custom",
            core_categories=frozenset({"cs.TEST"}),
            expansion_categories=frozenset(),
            sections=(SectionRule("arch", "Architecture", 1.0, ("architecture", "runtime")),),
        )
        similar_to_like = Paper(
            "gem5-cache",
            "Architecture Study for gem5 Cache Replacement",
            "Cycle accurate microarchitecture simulation of cache replacement policies.",
            [],
            ["cs.TEST"],
        )
        unrelated = Paper(
            "runtime",
            "Architecture Study for Parallel Runtime Scheduling",
            "A runtime scheduling method for distributed services.",
            [],
            ["cs.TEST"],
        )

        payload = recommendation_payload(
            [unrelated, similar_to_like],
            run_date="2026-06-12",
            profile=profile,
            feedback_events=[
                FeedbackEvent(
                    "old-liked",
                    "like",
                    "arch",
                    title="gem5 cache replacement exploration",
                    abstract="cycle accurate microarchitecture simulation",
                )
            ],
        )

        self.assertEqual(payload["recommendations"][0]["paper_id"], "gem5-cache")
        self.assertGreater(payload["feedback_summary"]["keyword_weights"]["gem5"], 0)

    def test_feedback_entity_weights_adjust_recommendation_order(self):
        profile = InterestProfile(
            name="Custom",
            core_categories=frozenset({"cs.TEST"}),
            expansion_categories=frozenset(),
            sections=(SectionRule("arch", "Architecture", 1.0, ("architecture", "runtime")),),
        )
        entity_match = Paper(
            "entity-match",
            "Architecture Study for Accelerator Simulation",
            "A simulator evaluates memory hierarchy behavior with gem5 and MLIR.",
            ["A. Architect"],
            ["cs.TEST"],
            affiliations=["University of Architecture"],
        )
        stronger_rule_score = Paper(
            "rule-strong",
            "Architecture Study for Generic Runtime",
            "architecture architecture architecture runtime scheduling.",
            ["Generic Author"],
            ["cs.TEST"],
            affiliations=["Generic Benchmark Institute"],
        )

        payload = recommendation_payload(
            [stronger_rule_score, entity_match],
            run_date="2026-06-12",
            profile=profile,
            feedback_events=[
                FeedbackEvent(
                    "old-liked",
                    "like",
                    "arch",
                    title="gem5 MLIR architecture simulation",
                    abstract="A gem5 and MLIR toolchain for architecture design.",
                    authors=["A. Architect"],
                    affiliations=["University of Architecture"],
                ),
                FeedbackEvent(
                    "old-disliked",
                    "dislike",
                    "arch",
                    title="generic runtime benchmark",
                    abstract="A generic runtime paper.",
                    authors=["Generic Author"],
                    affiliations=["Generic Benchmark Institute"],
                ),
            ],
        )

        self.assertEqual(payload["recommendations"][0]["paper_id"], "entity-match")
        self.assertGreater(payload["feedback_summary"]["author_weights"]["A. Architect"], 0)
        self.assertGreater(payload["feedback_summary"]["affiliation_weights"]["University of Architecture"], 0)
        self.assertGreater(payload["feedback_summary"]["toolchain_weights"]["gem5"], 0)
        self.assertLess(payload["feedback_summary"]["author_weights"]["Generic Author"], 0)

    def test_recommendation_history_penalizes_repeated_papers(self):
        profile = InterestProfile(
            name="Custom",
            core_categories=frozenset({"cs.TEST"}),
            expansion_categories=frozenset(),
            sections=(SectionRule("arch", "Architecture", 1.0, ("architecture",)),),
        )
        repeated = Paper(
            "repeated",
            "Architecture Study for Cache Design",
            "architecture architecture cache design",
            [],
            ["cs.TEST"],
        )
        fresh = Paper(
            "fresh",
            "Architecture Study for Cache Design",
            "architecture architecture cache design",
            [],
            ["cs.TEST"],
        )

        payload = recommendation_payload(
            [repeated, fresh],
            run_date="2026-06-12",
            profile=profile,
            history_runs=[
                RecommendationRun("repeated", "2026-06-10", 1, 5.0, "arch"),
                RecommendationRun("repeated", "2026-06-11", 2, 4.0, "arch"),
            ],
        )

        self.assertEqual(payload["recommendations"][0]["paper_id"], "fresh")
        self.assertEqual(payload["history_summary"]["shown_counts"]["repeated"], 2)


if __name__ == "__main__":
    unittest.main()
