import unittest

from paper_recommender.emailer import render_email_html


class EmailerTests(unittest.TestCase):
    def test_render_email_groups_recommendations_and_includes_feedback_links(self):
        payload = {
            "run_date": "2026-06-12",
            "section_labels": {"agentic_architecture": "Agentic Architecture / 自动设计空间探索"},
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
        self.assertIn("Agentic Architecture / 自动设计空间探索", html)
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
        self.assertIn("搜代码", html)
        self.assertIn("https://github.com/search?q=Agentic+Architecture+Exploration", html)
        self.assertIn("反馈：3 条", html)
        self.assertIn("喜欢率 67%", html)
        self.assertIn("偏好：gem5, mlir", html)
        self.assertIn("降权：browser", html)
        self.assertIn(">喜欢</a>", html)
        self.assertIn(">不喜欢</a>", html)

    def test_render_email_uses_payload_section_labels(self):
        payload = {
            "run_date": "2026-06-12",
            "section_labels": {"quantum_control": "量子控制"},
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

        self.assertIn("<h2>量子控制</h2>", html)

    def test_render_email_includes_repository_trend_and_original_paper_links(self):
        payload = {
            "run_date": "2026-06-14",
            "section_labels": {"agentic_architecture": "Agentic Architecture"},
            "recommendations": [
                {
                    "rank": 1,
                    "paper_id": "repo:example/arch-agent",
                    "item_type": "repository",
                    "source": "github_trending",
                    "title": "example/arch-agent",
                    "authors": ["example"],
                    "score": 12.0,
                    "sections": ["agentic_architecture"],
                    "abstract": "Hardware design agent for gem5.",
                    "tldr": "这个仓库实现了面向微架构探索的硬件设计 agent。",
                    "url": "https://github.com/example/arch-agent",
                    "code_urls": ["https://github.com/example/arch-agent"],
                    "repository_url": "https://github.com/example/arch-agent",
                    "repository_stars": 1300,
                    "repository_forks": 60,
                    "repository_stars_today": 87,
                    "repository_language": "Python",
                    "repository_topics": ["gem5", "microarchitecture"],
                    "paper_links": [{"label": "arXiv", "url": "https://arxiv.org/abs/2606.00001"}],
                }
            ],
        }

        html = render_email_html(
            payload,
            site_base_url="https://foreverhyx.github.io/agentic-arch-paper-recommender",
            feedback_base_url="https://foreverhyx.github.io/agentic-arch-paper-recommender/feedback.html",
        )

        self.assertIn("GitHub 仓库", html)
        self.assertIn("今日新增 star：87", html)
        self.assertIn("总 star：1300", html)
        self.assertIn("Python", html)
        self.assertIn("gem5, microarchitecture", html)
        self.assertIn("原始论文", html)
        self.assertIn("https://arxiv.org/abs/2606.00001", html)
        self.assertIn("https://github.com/example/arch-agent", html)
        self.assertIn("paper_id=repo%3Aexample%2Farch-agent", html)


if __name__ == "__main__":
    unittest.main()
