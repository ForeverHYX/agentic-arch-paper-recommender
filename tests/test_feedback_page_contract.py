import unittest
import subprocess
from pathlib import Path


class FeedbackPageContractTests(unittest.TestCase):
    def run_feedback_script(self, body):
        harness = r"""
const fs = require("fs");
const vm = require("vm");
const script = fs.readFileSync("site/feedback.js", "utf8");
const elements = {};
const storage = {};

function element(id) {
  if (!elements[id]) {
    elements[id] = { textContent: "" };
  }
  return elements[id];
}

const context = {
  window: {
    location: { search: "?paper_id=p1&rating=like&source=page&section=arch" },
    RECOMMENDER_CONFIG: {},
  },
  document: { getElementById: element },
  URLSearchParams,
  fetch: async () => {
    throw new Error("fetch should not be called without Supabase config");
  },
  localStorage: {
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null;
    },
    setItem(key, value) {
      storage[key] = String(value);
    },
  },
  setTimeout,
};

vm.createContext(context);
vm.runInContext(script, context);

setTimeout(() => {
  try {
__BODY__
  } catch (error) {
    console.error(error.stack || error.message);
    process.exit(1);
  }
}, 0);
"""
        result = subprocess.run(
            ["node", "-e", harness.replace("__BODY__", body)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_feedback_page_posts_paper_metadata_for_learning(self):
        script = Path("site/feedback.js").read_text(encoding="utf-8")

        self.assertIn('fetch("recommendations.json"', script)
        self.assertIn("findPaperMetadata", script)
        self.assertIn("title: paperMetadata.title", script)
        self.assertIn("abstract: paperMetadata.abstract", script)
        self.assertIn("authors: paperMetadata.authors", script)
        self.assertIn("affiliations: paperMetadata.affiliations", script)
        self.assertIn("categories: paperMetadata.categories", script)

    def test_feedback_page_stores_local_fallback_when_supabase_is_not_configured(self):
        self.run_feedback_script(
            """
const raw = storage.recommender_local_feedback_events;
if (!raw) throw new Error("local feedback queue was not written");
const events = JSON.parse(raw);
if (events.length !== 1) throw new Error(`expected one event, got ${events.length}`);
if (events[0].paper_id !== "p1") throw new Error("paper id not stored");
if (events[0].rating !== "like") throw new Error("rating not stored");
if (events[0].section !== "arch") throw new Error("section not stored");
if (!elements.statusDetail.textContent.includes("stored locally")) {
  throw new Error(`missing local storage status: ${elements.statusDetail.textContent}`);
}
"""
        )


if __name__ == "__main__":
    unittest.main()
