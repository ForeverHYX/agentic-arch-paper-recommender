import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from paper_recommender.favorites_archive import (
    export_favorites,
    fetch_liked_feedback_events,
    paper_pdf_url,
    slugify,
)


class FakeResponse:
    def __init__(self, payload=None, body=None):
        self.payload = payload
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        if self.body is not None:
            return self.body
        return json.dumps(self.payload).encode("utf-8")


class FakeErrorBody:
    def read(self):
        return b'{"message":"column feedback_events.repository_url does not exist"}'

    def close(self):
        pass


class FavoritesArchiveTests(unittest.TestCase):
    def test_fetch_liked_feedback_events_filters_likes_with_service_role_key(self):
        seen = {}

        def opener(request):
            seen["url"] = request.full_url
            seen["apikey"] = request.headers["Apikey"]
            seen["authorization"] = request.headers["Authorization"]
            return FakeResponse(
                [
                    {
                        "paper_id": "2606.00001",
                        "rating": "like",
                        "section": "Agentic Arch",
                        "title": "Agentic Architecture Exploration",
                        "created_at": "2026-06-14T02:00:00Z",
                    }
                ]
            )

        records = fetch_liked_feedback_events("https://example.supabase.co", "service-key", opener=opener)

        self.assertEqual(records[0]["paper_id"], "2606.00001")
        self.assertIn("rating=eq.like", seen["url"])
        self.assertEqual(seen["apikey"], "service-key")
        self.assertEqual(seen["authorization"], "Bearer service-key")

    def test_fetch_liked_feedback_events_falls_back_when_repository_columns_are_missing(self):
        seen_urls = []

        def opener(request):
            seen_urls.append(request.full_url)
            if len(seen_urls) == 1:
                raise HTTPError(request.full_url, 400, "Bad Request", hdrs=None, fp=FakeErrorBody())
            return FakeResponse(
                [
                    {
                        "paper_id": "2606.00001",
                        "rating": "like",
                        "section": "Agentic Arch",
                    }
                ]
            )

        records = fetch_liked_feedback_events("https://example.supabase.co", "service-key", opener=opener)

        self.assertEqual(records[0]["paper_id"], "2606.00001")
        self.assertIn("repository_url", seen_urls[0])
        self.assertNotIn("repository_url", seen_urls[1])

    def test_export_favorites_groups_by_month_and_section_and_downloads_pdf(self):
        records = [
            {
                "paper_id": "2606.00001",
                "rating": "like",
                "section": "Agentic Arch",
                "title": "Agentic Architecture Exploration",
                "abstract": "Architecture design space exploration.",
                "authors": ["A. Architect"],
                "affiliations": ["University of Architecture"],
                "categories": ["cs.AR"],
                "created_at": "2026-06-14T02:00:00Z",
            }
        ]
        seen_urls = []

        def opener(request, timeout=None):
            seen_urls.append(request.full_url)
            return FakeResponse(body=b"%PDF fake")

        with tempfile.TemporaryDirectory() as tmpdir:
            written = export_favorites(records, tmpdir, opener=opener)

            pdf_path = Path(tmpdir) / "2026-06" / "agentic-arch" / "2606.00001.pdf"
            json_path = Path(tmpdir) / "2026-06" / "agentic-arch" / "2606.00001.json"
            self.assertEqual(written, 1)
            self.assertEqual(pdf_path.read_bytes(), b"%PDF fake")
            metadata = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["paper_id"], "2606.00001")
            self.assertEqual(metadata["title"], "Agentic Architecture Exploration")
            self.assertEqual(metadata["pdf_url"], "https://arxiv.org/pdf/2606.00001.pdf")
            self.assertNotIn("download_error", metadata)
            self.assertEqual(seen_urls, ["https://arxiv.org/pdf/2606.00001.pdf"])

    def test_export_favorites_skips_dislikes_and_records_download_error(self):
        records = [
            {
                "paper_id": "skip-me",
                "rating": "dislike",
                "section": "Noise",
                "created_at": "2026-06-14T02:00:00Z",
            },
            {
                "paper_id": "2606.00002",
                "rating": "like",
                "section": "HPC x Architecture",
                "title": "HPC Runtime",
                "created_at": "2026-06-14T02:00:00Z",
            },
        ]

        def opener(request, timeout=None):
            raise TimeoutError("unit test timeout")

        with tempfile.TemporaryDirectory() as tmpdir:
            written = export_favorites(records, tmpdir, opener=opener)

            self.assertEqual(written, 1)
            self.assertFalse((Path(tmpdir) / "2026-06" / "noise").exists())
            metadata_path = Path(tmpdir) / "2026-06" / "hpc-x-architecture" / "2606.00002.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertIn("unit test timeout", metadata["download_error"])
            self.assertFalse((metadata_path.parent / "2606.00002.pdf").exists())

    def test_export_favorites_adds_liked_repository_as_git_submodule(self):
        records = [
            {
                "paper_id": "repo:example/arch-agent",
                "rating": "like",
                "item_type": "repository",
                "section": "Agentic Arch",
                "title": "example/arch-agent",
                "abstract": "Hardware design agent for gem5.",
                "repository_url": "https://github.com/example/arch-agent",
                "paper_links": [{"label": "arXiv", "url": "https://arxiv.org/abs/2606.00001"}],
                "created_at": "2026-06-14T02:00:00Z",
            }
        ]
        commands = []

        def runner(command, cwd):
            commands.append((command, cwd))

        with tempfile.TemporaryDirectory() as tmpdir:
            written = export_favorites(records, tmpdir, command_runner=runner)

            metadata_path = Path(tmpdir) / "2026-06" / "agentic-arch" / "repo-example-arch-agent.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(written, 1)
        self.assertEqual(metadata["item_type"], "repository")
        self.assertEqual(metadata["repository_url"], "https://github.com/example/arch-agent")
        self.assertEqual(metadata["paper_links"], [{"label": "arXiv", "url": "https://arxiv.org/abs/2606.00001"}])
        self.assertEqual(
            commands,
            [
                (
                    ["git", "submodule", "add", "https://github.com/example/arch-agent", "repositories/example-arch-agent"],
                    Path(tmpdir),
                )
            ],
        )

    def test_export_favorites_preserves_dotted_repository_names_in_submodule_path(self):
        records = [
            {
                "paper_id": "repo:ggml-org/llama.cpp",
                "rating": "like",
                "item_type": "repository",
                "section": "HPC",
                "title": "ggml-org/llama.cpp",
                "repository_url": "https://github.com/ggml-org/llama.cpp",
                "created_at": "2026-06-14T02:00:00Z",
            }
        ]
        commands = []

        with tempfile.TemporaryDirectory() as tmpdir:
            export_favorites(records, tmpdir, command_runner=lambda command, cwd: commands.append((command, cwd)))

        self.assertEqual(
            commands[0][0],
            ["git", "submodule", "add", "https://github.com/ggml-org/llama.cpp", "repositories/ggml-org-llama.cpp"],
        )

    def test_export_favorites_derives_repository_url_from_legacy_repo_paper_id(self):
        records = [
            {
                "paper_id": "repo:example/arch-agent",
                "rating": "like",
                "section": "Agentic Arch",
                "title": "example/arch-agent",
                "created_at": "2026-06-14T02:00:00Z",
            }
        ]
        commands = []

        with tempfile.TemporaryDirectory() as tmpdir:
            export_favorites(records, tmpdir, command_runner=lambda command, cwd: commands.append((command, cwd)))

            metadata_path = Path(tmpdir) / "2026-06" / "agentic-arch" / "repo-example-arch-agent.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        self.assertEqual(metadata["item_type"], "repository")
        self.assertEqual(metadata["repository_url"], "https://github.com/example/arch-agent")
        self.assertEqual(
            commands[0][0],
            ["git", "submodule", "add", "https://github.com/example/arch-agent", "repositories/example-arch-agent"],
        )

    def test_slugify_and_pdf_url_are_stable(self):
        self.assertEqual(slugify("HPC x 架构 / 编译器 / 运行时"), "hpc-x-架构-编译器-运行时")
        self.assertEqual(paper_pdf_url("2606.00001"), "https://arxiv.org/pdf/2606.00001.pdf")
        self.assertEqual(paper_pdf_url("not-arxiv"), "")


if __name__ == "__main__":
    unittest.main()
