from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from paper_recommender.arxiv_source import build_query_url, fetch_atom_feed, main, parse_atom_feed
from paper_recommender.domain import InterestProfile, SectionRule


ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2604.03312v2</id>
    <updated>2026-04-09T00:00:00Z</updated>
    <published>2026-04-01T00:00:00Z</published>
    <title>Agentic AI-Driven Microarchitecture Exploration</title>
    <summary>
      An LLM-driven hardware design agent explores cache replacement policy
      candidates with gem5.
    </summary>
    <author>
      <name>A. Architect</name>
      <arxiv:affiliation>University of Architecture</arxiv:affiliation>
    </author>
    <author>
      <name>B. Researcher</name>
      <arxiv:affiliation>National HPC Lab</arxiv:affiliation>
    </author>
    <category term="cs.AR" />
    <category term="cs.AI" />
    <link href="http://arxiv.org/abs/2604.03312v2" rel="alternate" type="text/html" />
  </entry>
</feed>
"""


class ArxivSourceTests(unittest.TestCase):
    def test_build_query_url_includes_core_and_expansion_categories(self):
        profile = InterestProfile(
            name="Custom",
            core_categories=frozenset({"cs.AR", "cs.PF"}),
            expansion_categories=frozenset({"cs.AI"}),
            sections=(SectionRule("arch", "Architecture", 1.0, ("microarchitecture",)),),
        )

        url = build_query_url(profile, max_results=125)

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "export.arxiv.org")
        self.assertEqual(query["max_results"], ["125"])
        self.assertEqual(query["sortBy"], ["submittedDate"])
        self.assertEqual(query["sortOrder"], ["descending"])
        self.assertEqual(
            query["search_query"],
            ["cat:cs.AI OR cat:cs.AR OR cat:cs.PF"],
        )

    def test_parse_atom_feed_emits_pipeline_compatible_records(self):
        records = parse_atom_feed(ATOM_FEED)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["paper_id"], "2604.03312")
        self.assertEqual(records[0]["title"], "Agentic AI-Driven Microarchitecture Exploration")
        self.assertIn("hardware design agent explores", records[0]["abstract"])
        self.assertEqual(records[0]["authors"], ["A. Architect", "B. Researcher"])
        self.assertEqual(records[0]["affiliations"], ["University of Architecture", "National HPC Lab"])
        self.assertEqual(records[0]["categories"], ["cs.AR", "cs.AI"])
        self.assertEqual(records[0]["url"], "http://arxiv.org/abs/2604.03312v2")
        self.assertEqual(records[0]["published"], "2026-04-01T00:00:00Z")
        self.assertEqual(records[0]["updated"], "2026-04-09T00:00:00Z")

    def test_cli_writes_jsonl_from_source_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            profile_path = tmp / "interests.json"
            feed_path = tmp / "feed.xml"
            output_path = tmp / "papers.jsonl"
            profile_path.write_text(
                json.dumps(
                    {
                        "name": "Custom",
                        "core_categories": ["cs.AR"],
                        "expansion_categories": ["cs.AI"],
                        "sections": [
                            {
                                "id": "arch",
                                "label": "Architecture",
                                "weight": 1.0,
                                "keywords": ["microarchitecture"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            feed_path.write_text(ATOM_FEED, encoding="utf-8")

            exit_code = main(
                [
                    "--profile",
                    str(profile_path),
                    "--output",
                    str(output_path),
                    "--source-file",
                    str(feed_path),
                ]
            )

            self.assertEqual(exit_code, 0)
            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["paper_id"] for row in rows], ["2604.03312"])

    def test_fetch_retries_timeout_then_succeeds(self):
        attempts = []
        delays = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self):
                return ATOM_FEED.encode("utf-8")

        def opener(request, timeout=None):
            attempts.append((request.full_url, timeout))
            if len(attempts) < 3:
                raise TimeoutError("temporary timeout")
            return Response()

        result = fetch_atom_feed(
            "https://export.arxiv.org/api/query?test=1",
            timeout=42,
            max_attempts=4,
            opener=opener,
            sleeper=delays.append,
        )

        self.assertEqual(result, ATOM_FEED)
        self.assertEqual(len(attempts), 3)
        self.assertEqual([timeout for _, timeout in attempts], [42, 42, 42])
        self.assertEqual(delays, [3.0, 6.0])

    def test_fetch_retries_rate_limit_using_retry_after(self):
        attempts = []
        delays = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self):
                return b"ok"

        def opener(request, timeout=None):
            attempts.append(request.full_url)
            if len(attempts) == 1:
                raise HTTPError(
                    request.full_url,
                    429,
                    "Too Many Requests",
                    {"Retry-After": "12"},
                    BytesIO(),
                )
            return Response()

        result = fetch_atom_feed(
            "https://export.arxiv.org/api/query?test=1",
            opener=opener,
            sleeper=delays.append,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(len(attempts), 2)
        self.assertEqual(delays, [12.0])

    def test_fetch_does_not_retry_non_transient_http_error(self):
        attempts = []

        def opener(request, timeout=None):
            attempts.append(request.full_url)
            raise HTTPError(request.full_url, 400, "Bad Request", {}, BytesIO())

        with self.assertRaises(HTTPError):
            fetch_atom_feed(
                "https://export.arxiv.org/api/query?test=1",
                opener=opener,
                sleeper=lambda _: self.fail("unexpected sleep"),
            )

        self.assertEqual(len(attempts), 1)


if __name__ == "__main__":
    unittest.main()
