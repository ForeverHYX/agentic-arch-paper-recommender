import json
import tempfile
import unittest
from pathlib import Path

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

    def test_slugify_and_pdf_url_are_stable(self):
        self.assertEqual(slugify("HPC x 架构 / 编译器 / 运行时"), "hpc-x-架构-编译器-运行时")
        self.assertEqual(paper_pdf_url("2606.00001"), "https://arxiv.org/pdf/2606.00001.pdf")
        self.assertEqual(paper_pdf_url("not-arxiv"), "")


if __name__ == "__main__":
    unittest.main()
