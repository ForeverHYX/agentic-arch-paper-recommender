import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from paper_recommender.arxiv_source import build_query_url, main, parse_atom_feed
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
    <author><name>A. Architect</name></author>
    <author><name>B. Researcher</name></author>
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


if __name__ == "__main__":
    unittest.main()
