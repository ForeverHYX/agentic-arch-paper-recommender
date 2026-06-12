import unittest

from paper_recommender.emailer import render_email_html


class EmailerTests(unittest.TestCase):
    def test_render_email_groups_recommendations_and_includes_feedback_links(self):
        payload = {
            "run_date": "2026-06-12",
            "section_labels": {"agentic_architecture": "Agentic Architecture / Auto-DSE"},
            "feedback_summary": {
                "metrics": {
                    "total_events": 3,
                    "like_count": 2,
                    "dislike_count": 1,
                    "like_rate": 2 / 3,
                    "top_liked_keywords": ["gem5", "mlir"],
                    "top_disliked_keywords": ["browser"],
                    "top_liked_toolchains": ["gem5"],
                    "top_disliked_toolchains": ["cuda"],
                }
            },
            "recommendations": [
                {
                    "rank": 1,
                    "paper_id": "arch",
                    "title": "Agentic AI-Driven Microarchitecture Exploration",
                    "authors": ["A. Architect"],
                    "affiliations": ["University of Architecture", "National HPC Lab"],
                    "score": 14.0,
                    "sections": ["agentic_architecture", "microarchitecture_simulators"],
                    "abstract": "An LLM-driven architecture DSE system.",
                    "tldr": "用 agent 自动探索微架构设计空间。",
                    "ai_judgement": {
                        "score": 9.0,
                        "reason": "高度贴合自动架构探索。",
                        "decision": "keep",
                    },
                    "url": "https://arxiv.org/abs/2604.03312",
                    "pdf_url": "https://arxiv.org/pdf/2604.03312",
                    "code_urls": ["https://github.com/example/arch-agent"],
                    "code_search_url": "https://github.com/search?q=Agentic+Architecture+Exploration&type=repositories",
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
        self.assertIn("University of Architecture", html)
        self.assertIn("National HPC Lab", html)
        self.assertIn("rating=like", html)
        self.assertIn("rating=dislike", html)
        self.assertIn("paper_id=arch", html)
        self.assertIn("用 agent 自动探索微架构设计空间。", html)
        self.assertIn("AI 判断", html)
        self.assertIn("高度贴合自动架构探索。", html)
        self.assertIn("https://arxiv.org/abs/2604.03312", html)
        self.assertIn("https://arxiv.org/pdf/2604.03312", html)
        self.assertIn("https://github.com/example/arch-agent", html)
        self.assertIn("Code Search", html)
        self.assertIn("https://github.com/search?q=Agentic+Architecture+Exploration", html)
        self.assertIn("Feedback: 3 events", html)
        self.assertIn("67% like rate", html)
        self.assertIn("liked: gem5, mlir", html)
        self.assertIn("disliked: browser", html)

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
