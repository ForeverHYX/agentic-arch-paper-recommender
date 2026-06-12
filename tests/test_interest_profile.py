import json
import tempfile
import unittest
from pathlib import Path

from paper_recommender.domain import Paper, classify_paper, load_interest_profile


class InterestProfileTests(unittest.TestCase):
    def test_load_interest_profile_from_json(self):
        profile = self._write_profile(
            {
                "name": "Quantum Systems",
                "core_categories": ["quant-ph"],
                "expansion_categories": ["cs.LG"],
                "sections": [
                    {
                        "id": "quantum_control",
                        "label": "Quantum Control",
                        "weight": 5.0,
                        "keywords": ["quantum control", "pulse optimization"],
                    }
                ],
                "negative_rules": [
                    {
                        "id": "software-noise",
                        "penalty": 4.0,
                        "keywords": ["web framework"],
                    }
                ],
            }
        )

        self.assertEqual(profile.name, "Quantum Systems")
        self.assertEqual(profile.sections[0].id, "quantum_control")
        self.assertEqual(profile.sections[0].label, "Quantum Control")

    def test_load_interest_profile_seed_papers_from_json(self):
        profile = self._write_profile(
            {
                "name": "Agentic Architecture",
                "core_categories": ["cs.AR"],
                "expansion_categories": ["cs.AI"],
                "sections": [],
                "seed_papers": [
                    {
                        "title": "Computer Architecture's AlphaZero Moment",
                        "url": "https://arxiv.org/abs/2407.XXXX",
                        "notes": "Representative automated architecture discovery seed.",
                        "keywords": ["automated architecture discovery", "design space exploration"],
                    }
                ],
            }
        )

        self.assertEqual(len(profile.seed_papers), 1)
        seed = profile.seed_papers[0]
        self.assertEqual(seed.title, "Computer Architecture's AlphaZero Moment")
        self.assertEqual(seed.url, "https://arxiv.org/abs/2407.XXXX")
        self.assertEqual(seed.notes, "Representative automated architecture discovery seed.")
        self.assertEqual(seed.keywords, ("automated architecture discovery", "design space exploration"))

    def test_custom_profile_drives_classification_without_code_changes(self):
        profile = self._write_profile(
            {
                "name": "Quantum Systems",
                "core_categories": ["quant-ph"],
                "expansion_categories": ["cs.LG"],
                "sections": [
                    {
                        "id": "quantum_control",
                        "label": "Quantum Control",
                        "weight": 5.0,
                        "keywords": ["quantum control", "pulse optimization"],
                    }
                ],
                "negative_rules": [],
            }
        )
        paper = Paper(
            paper_id="quantum-1",
            title="Learning Pulse Optimization for Quantum Control",
            abstract="A reinforcement learning method for quantum control.",
            authors=["Q. Researcher"],
            categories=["cs.LG"],
        )

        result = classify_paper(paper, profile=profile)

        self.assertTrue(result.accepted)
        self.assertEqual(result.sections, ("quantum_control",))

    def _write_profile(self, payload):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "interests.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return load_interest_profile(path)


if __name__ == "__main__":
    unittest.main()
