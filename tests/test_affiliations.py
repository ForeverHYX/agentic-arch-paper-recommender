import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from paper_recommender.affiliations import (
    enrich_payload_with_affiliations,
    extract_affiliations_from_latex,
    extract_affiliations_from_source_archive,
    main,
)


class AffiliationsTests(unittest.TestCase):
    def test_extract_affiliations_from_latex_affil_macros(self):
        text = r"""
        \author[1]{N. Koldunov}
        \affil[1]{Alfred Wegener Institute, Helmholtz Centre for Polar and
                  Marine Research, Bremerhaven, Germany}
        \affil[2]{Department of Physics and Electrical Engineering, University of Bremen}
        """

        affiliations = extract_affiliations_from_latex(text)

        self.assertEqual(
            affiliations,
            [
                "Alfred Wegener Institute, Helmholtz Centre for Polar and Marine Research, Bremerhaven, Germany",
                "Department of Physics and Electrical Engineering, University of Bremen",
            ],
        )

    def test_extract_affiliations_from_latex_removes_email_macros(self):
        text = r"""
        \institute{Institute of Parallel and Distributed Systems, University of Stuttgart,\\ 70569 Stuttgart, Germany\\
        \email{\{alexander.strack, alexander.van-craen\}@ipvs.uni-stuttgart.de}}
        """

        affiliations = extract_affiliations_from_latex(text)

        self.assertEqual(
            affiliations,
            ["Institute of Parallel and Distributed Systems, University of Stuttgart, 70569 Stuttgart, Germany"],
        )

    def test_extract_affiliations_from_source_archive_reads_tex_files(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as archive:
            content = br"\affiliation{Department of Computer Science, Example University}"
            info = tarfile.TarInfo("main.tex")
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))

        affiliations = extract_affiliations_from_source_archive(data.getvalue())

        self.assertEqual(affiliations, ["Department of Computer Science, Example University"])

    def test_enrich_payload_with_affiliations_fetches_missing_affiliations(self):
        payload = {
            "recommendations": [
                {
                    "paper_id": "2606.11356",
                    "title": "An Ocean Model Ported by a Large Language Model",
                    "affiliations": [],
                }
            ]
        }

        def fetcher(paper_id):
            self.assertEqual(paper_id, "2606.11356")
            return br"\affil[1]{Alfred Wegener Institute}"

        enriched = enrich_payload_with_affiliations(payload, fetcher=fetcher)

        self.assertEqual(enriched["recommendations"][0]["affiliations"], ["Alfred Wegener Institute"])
        self.assertEqual(enriched["affiliation_summary"]["enriched_count"], 1)

    def test_cli_updates_recommendation_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "recommendations.json"
            path.write_text(
                json.dumps(
                    {
                        "recommendations": [
                            {
                                "paper_id": "p1",
                                "title": "Paper",
                                "affiliations": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            exit_code = main(
                ["--input", str(path), "--output", str(path)],
                fetcher=lambda paper_id: br"\institute{Example Architecture Lab}",
            )

            self.assertEqual(exit_code, 0)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["recommendations"][0]["affiliations"], ["Example Architecture Lab"])


if __name__ == "__main__":
    unittest.main()
