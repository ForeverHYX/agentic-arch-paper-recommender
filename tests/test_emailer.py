import unittest

from paper_recommender.emailer import render_email_html


class EmailerTests(unittest.TestCase):
    def test_render_email_groups_recommendations_and_includes_feedback_links(self):
        payload = {
            "run_date": "2026-06-12",
            "section_labels": {"agentic_architecture": "Agentic Architecture / Auto-DSE"},
            "recommendations": [
                {
                    "rank": 1,
                    "paper_id": "arch",
                    "title": "Agentic AI-Driven Microarchitecture Exploration",
                    "authors": ["A. Architect"],
                    "score": 14.0,
                    "sections": ["agentic_architecture", "microarchitecture_simulators"],
                    "abstract": "An LLM-driven architecture DSE system.",
                }
            ],
        }

        html = render_email_html(
            payload,
            site_base_url="https://foreverhyx.github.io/agentic-arch-paper-recommender",
            feedback_base_url="https://foreverhyx.github.io/agentic-arch-paper-recommender/feedback.html",
        )

        self.assertIn("2026-06-12", html)
        self.assertIn("Agentic Architecture / Auto-DSE", html)
        self.assertIn("Agentic AI-Driven Microarchitecture Exploration", html)
        self.assertIn("rating=like", html)
        self.assertIn("rating=dislike", html)
        self.assertIn("paper_id=arch", html)

    def test_render_email_uses_payload_section_labels(self):
        payload = {
            "run_date": "2026-06-12",
            "section_labels": {"quantum_control": "Quantum Control"},
            "recommendations": [
                {
                    "rank": 1,
                    "paper_id": "quantum",
                    "title": "Learning for Quantum Control",
                    "authors": ["Q. Researcher"],
                    "score": 5.0,
                    "sections": ["quantum_control"],
                    "abstract": "Pulse optimization for quantum systems.",
                }
            ],
        }

        html = render_email_html(
            payload,
            site_base_url="https://foreverhyx.github.io/agentic-arch-paper-recommender",
            feedback_base_url="https://foreverhyx.github.io/agentic-arch-paper-recommender/feedback.html",
        )

        self.assertIn("<h2>Quantum Control</h2>", html)


if __name__ == "__main__":
    unittest.main()
