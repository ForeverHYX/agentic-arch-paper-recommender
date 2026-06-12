import unittest
import subprocess
from pathlib import Path


class SiteContractTests(unittest.TestCase):
    def run_app_script(self, body):
        harness = r"""
const fs = require("fs");
const vm = require("vm");
const script = fs.readFileSync("site/app.js", "utf8");
const elements = {};

function element(id) {
  if (!elements[id]) {
    elements[id] = {
      textContent: "",
      innerHTML: "",
      dataset: {},
      value: "",
      checked: false,
      addEventListener() {},
    };
  }
  return elements[id];
}

const context = {
  window: { RECOMMENDER_CONFIG: {} },
  document: { getElementById: element },
  fetch: async () => ({
    ok: true,
    json: async () => ({ recommendations: [], section_labels: {} }),
  }),
  localStorage: {
    getItem() { return null; },
  },
  encodeURIComponent,
};

vm.createContext(context);
vm.runInContext(script, context);

__BODY__
"""
        result = subprocess.run(
            ["node", "-e", harness.replace("__BODY__", body)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_recommendation_page_renders_tldr_and_external_links(self):
        script = Path("site/app.js").read_text(encoding="utf-8")

        self.assertIn("paper.tldr", script)
        self.assertIn("AI 总结", script)
        self.assertIn("paper.ai_judgement", script)
        self.assertIn("AI 判断", script)
        self.assertIn("paper.affiliations", script)
        self.assertIn("单位", script)
        self.assertIn("paper.url", script)
        self.assertIn("paper.pdf_url", script)
        self.assertIn("paper.code_urls", script)
        self.assertIn("paper.code_search_url", script)
        self.assertIn("Paper", script)
        self.assertIn("PDF", script)
        self.assertIn("Code", script)
        self.assertIn("Code Search", script)

    def test_recommendation_cards_always_render_affiliation_status(self):
        self.run_app_script(
            """
const basePaper = {
  rank: 1,
  score: 7,
  paper_id: "2606.00001",
  title: "Agentic Architecture Exploration",
  abstract: "Architecture design space exploration.",
  authors: ["A. Architect"],
  categories: ["cs.AR"],
  sections: ["agentic_architecture"],
};

const withAffiliations = context.renderPaper({
  ...basePaper,
  affiliations: ["University of Architecture", "National HPC Lab"],
});
if (!withAffiliations.includes("paper-affiliations")) {
  throw new Error("affiliation block class missing");
}
if (!withAffiliations.includes("University of Architecture")) {
  throw new Error("affiliation value missing");
}

const withoutAffiliations = context.renderPaper({
  ...basePaper,
  affiliations: [],
});
if (!withoutAffiliations.includes("未解析到作者单位")) {
  throw new Error("missing-affiliation status not rendered");
}
"""
        )

    def test_summary_stats_show_affiliation_coverage(self):
        self.run_app_script(
            """
context.renderSummaryStats({
  recommendations: [
    { sections: ["agentic_architecture"], affiliations: ["University of Architecture"], code_urls: [] },
    { sections: ["agentic_architecture"], affiliations: [], code_urls: [] },
    { sections: ["hpc_cross_over"], code_search_url: "https://github.com/search?q=x", code_urls: [] },
  ],
});

const html = elements.summaryStats.innerHTML;
if (!html.includes("<strong>1</strong><span>with units</span>")) {
  throw new Error(`affiliation coverage stat missing: ${html}`);
}
"""
        )

    def test_reader_shows_feedback_persistence_status(self):
        self.run_app_script(
            """
context.renderFeedbackStatus();
let html = elements.feedbackStatus.innerHTML;
if (!html.includes("local only")) {
  throw new Error(`missing local-only status: ${html}`);
}

context.window.RECOMMENDER_CONFIG = {
  supabaseUrl: "https://example.supabase.co",
  supabaseAnonKey: "anon-key",
};
context.renderFeedbackStatus();
html = elements.feedbackStatus.innerHTML;
if (!html.includes("Supabase active")) {
  throw new Error(`missing Supabase status: ${html}`);
}
"""
        )

    def test_reader_shows_feedback_learning_metrics(self):
        self.run_app_script(
            """
context.renderFeedbackInsights({
  total_events: 3,
  like_count: 2,
  dislike_count: 1,
  like_rate: 0.6667,
  top_liked_keywords: ["gem5", "mlir"],
  top_disliked_keywords: ["browser"],
  top_liked_toolchains: ["gem5"],
  top_disliked_toolchains: ["cuda"],
});

const html = elements.feedbackInsights.innerHTML;
if (!html.includes("3 feedback events")) {
  throw new Error(`missing feedback count: ${html}`);
}
if (!html.includes("67% like rate")) {
  throw new Error(`missing like rate: ${html}`);
}
if (!html.includes("gem5")) {
  throw new Error(`missing liked topic: ${html}`);
}
if (!html.includes("browser")) {
  throw new Error(`missing disliked topic: ${html}`);
}
"""
        )

    def test_reader_shows_subsystem_status(self):
        self.run_app_script(
            """
context.renderSubsystemStatus({
  llm: { configured: true, model: "deepseek-v4-flash" },
  smtp: { configured: true },
  supabase: { configured: false },
  local_feedback: { configured: true },
  profile_override: { configured: false },
});

const html = elements.subsystemStatus.innerHTML;
if (!html.includes("LLM")) throw new Error(`missing LLM status: ${html}`);
if (!html.includes("deepseek-v4-flash")) throw new Error(`missing model: ${html}`);
if (!html.includes("Email")) throw new Error(`missing Email status: ${html}`);
if (!html.includes("Supabase")) throw new Error(`missing Supabase status: ${html}`);
if (!html.includes("local feedback")) throw new Error(`missing local feedback status: ${html}`);
"""
        )

    def test_index_uses_versioned_frontend_assets(self):
        html = Path("site/index.html").read_text(encoding="utf-8")

        self.assertIn('href="styles.css?v=', html)
        self.assertIn('src="app.js?v=', html)

    def test_recommendation_page_has_workbench_layout_hooks(self):
        html = Path("site/index.html").read_text(encoding="utf-8")
        styles = Path("site/styles.css").read_text(encoding="utf-8")
        script = Path("site/app.js").read_text(encoding="utf-8")

        self.assertIn('id="summaryStats"', html)
        self.assertIn('id="sectionNav"', html)
        self.assertIn('id="searchInput"', html)
        self.assertIn('id="sectionFilter"', html)
        self.assertIn('id="minAiScore"', html)
        self.assertIn('id="hasCodeFilter"', html)
        self.assertIn('id="hasAffiliationFilter"', html)
        self.assertIn('id="sortSelect"', html)
        self.assertIn('id="resultCount"', html)
        self.assertIn('id="feedbackStatus"', html)
        self.assertIn('id="feedbackInsights"', html)
        self.assertIn('id="subsystemStatus"', html)
        self.assertLess(html.index("config.js"), html.index("app.js"))
        self.assertIn("renderSummaryStats", script)
        self.assertIn("renderSectionNav", script)
        self.assertIn("renderControls", script)
        self.assertIn("renderFeedbackStatus", script)
        self.assertIn("renderFeedbackInsights", script)
        self.assertIn("renderSubsystemStatus", script)
        self.assertIn("applyControls", script)
        self.assertIn("filteredRecommendations", script)
        self.assertIn("collectFilterState", script)
        self.assertIn(".paper-tldr", styles)
        self.assertIn(".ai-judgement", styles)
        self.assertIn(".controls", styles)
        self.assertIn(".filter-row", styles)
        self.assertIn(".link-button", styles)
        self.assertIn(".section-nav", styles)


if __name__ == "__main__":
    unittest.main()
