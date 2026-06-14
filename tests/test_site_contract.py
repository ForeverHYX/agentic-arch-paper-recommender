import json
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
const storage = {};

function element(id) {
  if (!elements[id]) {
    const classes = new Set();
    elements[id] = {
      textContent: "",
      innerHTML: "",
      dataset: {},
      value: "",
      checked: false,
      addEventListener() {},
      classList: {
        add(name) { classes.add(name); },
        contains(name) { return classes.has(name); },
      },
      scrollIntoView() {
        this.scrolled = true;
      },
      scrolled: false,
    };
  }
  return elements[id];
}

const context = {
  window: { RECOMMENDER_CONFIG: {}, location: { search: "" } },
  document: { getElementById: element },
  fetch: async () => ({
    ok: true,
    json: async () => ({ recommendations: [], section_labels: {} }),
  }),
  localStorage: {
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null;
    },
    setItem(key, value) {
      storage[key] = String(value);
    },
  },
  encodeURIComponent,
  URLSearchParams,
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

    def test_recommendation_page_renders_tldr_and_chinese_actions(self):
        script = Path("site/app.js").read_text(encoding="utf-8")

        self.assertIn("paper.tldr", script)
        self.assertIn("核心解读", script)
        self.assertIn("paper.ai_judgement", script)
        self.assertIn("AI 判断", script)
        self.assertIn("paper.affiliations", script)
        self.assertIn("作者单位", script)
        self.assertIn("paper.url", script)
        self.assertIn("paper.pdf_url", script)
        self.assertIn("paper.code_urls", script)
        self.assertIn("paper.code_search_url", script)
        self.assertIn("arXiv", script)
        self.assertIn("PDF", script)
        self.assertIn("代码", script)
        self.assertIn("搜代码", script)
        self.assertIn("喜欢", script)
        self.assertIn("不喜欢", script)

    def test_recommendation_cards_use_inline_feedback_buttons(self):
        script = Path("site/app.js").read_text(encoding="utf-8")

        self.assertIn("recordInlineFeedback", script)
        self.assertIn("data-feedback-rating", script)
        self.assertNotIn('class="feedback-button like" href="${likeUrl}"', script)
        self.assertNotIn('class="feedback-button dislike" href="${dislikeUrl}"', script)

    def test_inline_like_marks_card_with_star(self):
        self.run_app_script(
            """
const payload = {
  run_date: "2026-06-14",
  recommendations: [{
    rank: 1,
    score: 7,
    paper_id: "2606.00001",
    title: "Agentic Architecture Exploration",
    abstract: "Architecture design space exploration.",
    authors: ["A. Architect"],
    affiliations: [],
    categories: ["cs.AR"],
    sections: ["agentic_architecture"],
  }],
  section_labels: { agentic_architecture: "Agentic 架构" },
};
context.render(payload);
context.markFeedbackState("2606.00001", "like");
const html = context.renderPaper(payload.recommendations[0]);
if (!html.includes("paper-favorite-star")) throw new Error(`star missing: ${html}`);
if (!html.includes("已喜欢")) throw new Error(`liked label missing: ${html}`);
"""
        )

    def test_inline_dislike_hides_today_recommendation(self):
        self.run_app_script(
            """
const payload = {
  run_date: "2026-06-14",
  recommendations: [
    { paper_id: "hide-me", rank: 1, score: 7, title: "Hide", abstract: "", sections: ["arch"] },
    { paper_id: "keep-me", rank: 2, score: 6, title: "Keep", abstract: "", sections: ["arch"] },
  ],
  section_labels: { arch: "架构" },
};
context.render(payload);
context.markFeedbackState("hide-me", "dislike");
const filtered = context.filteredRecommendations(payload.recommendations, {
  query: "",
  section: "",
  minAiScore: 0,
  hasCode: false,
  hasAffiliation: false,
  sort: "rank",
});
if (filtered.length !== 1 || filtered[0].paper_id !== "keep-me") {
  throw new Error(`hidden paper still visible: ${filtered.map((paper) => paper.paper_id).join(",")}`);
}
"""
        )

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
if (!withAffiliations.includes("作者单位")) {
  throw new Error("explicit author affiliation label missing");
}

const withoutAffiliations = context.renderPaper({
  ...basePaper,
  affiliations: [],
});
if (!withoutAffiliations.includes("未解析到作者单位")) {
  throw new Error("missing-affiliation status not rendered");
}
if (!withoutAffiliations.includes("作者单位")) {
  throw new Error("explicit missing affiliation label missing");
}
"""
        )

    def test_committed_sample_payload_exercises_affiliation_ui(self):
        payload = json.loads(Path("site/recommendations.json").read_text(encoding="utf-8"))
        recommendations = payload.get("recommendations", [])

        self.assertTrue(recommendations)
        self.assertTrue(all(isinstance(item.get("affiliations"), list) for item in recommendations))
        self.assertTrue(any(item.get("affiliations") for item in recommendations))

    def test_index_busts_app_cache_for_affiliation_ui(self):
        html = Path("site/index.html").read_text(encoding="utf-8")

        self.assertIn("app.js?v=20260614-inline-feedback", html)

    def test_index_contains_run_health_placeholder_and_cache_bust(self):
        html = Path("site/index.html").read_text(encoding="utf-8")

        self.assertIn('id="runHealth"', html)
        self.assertIn('class="run-health"', html)
        self.assertIn('id="statusDetails"', html)
        self.assertIn("反馈与系统细节", html)
        self.assertIn("app.js?v=20260614-inline-feedback", html)

    def test_sidebar_keeps_secondary_status_in_collapsible_details(self):
        html = Path("site/index.html").read_text(encoding="utf-8")
        styles = Path("site/styles.css").read_text(encoding="utf-8")

        self.assertIn('id="profileSystemWorkspace"', html)
        self.assertIn('id="statusDetails"', html)
        self.assertLess(html.index('id="profileSystemWorkspace"'), html.index('id="runHealth"'))
        self.assertLess(html.index('id="runHealth"'), html.index('id="statusDetails"'))
        self.assertLess(html.index('id="statusDetails"'), html.index('id="feedbackStatus"'))
        self.assertIn(".sidebar-details", styles)
        self.assertIn(".sidebar-details summary", styles)
        self.assertIn(".profile-system-grid", styles)

    def test_index_uses_reader_tabs_and_keyword_filter_layout(self):
        html = Path("site/index.html").read_text(encoding="utf-8")
        styles = Path("site/styles.css").read_text(encoding="utf-8")

        self.assertIn('class="nav-island"', html)
        self.assertIn('id="readerTabs"', html)
        self.assertIn('data-tab="all"', html)
        self.assertIn('data-tab="paper"', html)
        self.assertIn('data-tab="repository"', html)
        self.assertIn('data-tab="profile"', html)
        self.assertIn('id="recommendationWorkspace"', html)
        self.assertIn('id="profileSystemWorkspace"', html)
        self.assertIn('id="keywordFilters"', html)
        self.assertIn('id="typeKeywordFilters"', html)
        self.assertIn('id="contentKeywordFilters"', html)
        self.assertIn(".nav-island", styles)
        self.assertIn(".article-grid", styles)
        self.assertIn(".keyword-chip", styles)

    def test_reader_shows_run_health_for_local_feedback_mode(self):
        self.run_app_script(
            """
context.renderRunHealth({
  recommendations: [
    { ai_judgement: { score: 9 }, tldr: "Good architecture paper." },
    { ai_judgement: { score: 7 }, tldr: "" },
    { tldr: "Fallback summary." },
  ],
  feedback_summary: { metrics: { total_events: 0 } },
}, {
  llm: { configured: true, model: "deepseek-v4-flash" },
  supabase: { configured: false },
});

const html = elements.runHealth.innerHTML;
if (!html.includes("运行状态")) throw new Error(`missing heading: ${html}`);
if (!html.includes("2/3 已判断")) throw new Error(`missing judgement coverage: ${html}`);
if (!html.includes("2/3 有 TLDR")) throw new Error(`missing TLDR coverage: ${html}`);
if (!html.includes("仅本地保存")) throw new Error(`missing local feedback mode: ${html}`);
if (!html.includes("尚未持久化")) throw new Error(`missing learning warning: ${html}`);
if (!html.includes("SUPABASE_URL")) throw new Error(`missing Supabase URL setup: ${html}`);
if (!html.includes("SUPABASE_ANON_KEY")) throw new Error(`missing Supabase anon setup: ${html}`);
if (!html.includes("SUPABASE_SERVICE_ROLE_KEY")) throw new Error(`missing service role setup: ${html}`);
"""
        )

    def test_reader_shows_run_health_for_supabase_mode(self):
        self.run_app_script(
            """
context.window.RECOMMENDER_CONFIG = {
  supabaseUrl: "https://example.supabase.co",
  supabaseAnonKey: "anon-key",
};
context.renderRunHealth({
  recommendations: [
    { ai_judgement: { score: 9 }, tldr: "Summary." },
    { ai_judgement: { score: 8 }, tldr: "Summary." },
  ],
  feedback_summary: { metrics: { total_events: 5 } },
}, {
  llm: { configured: true, model: "deepseek-v4-flash" },
  supabase: { configured: true },
});

const html = elements.runHealth.innerHTML;
if (!html.includes("2/2 已判断")) throw new Error(`missing judgement coverage: ${html}`);
if (!html.includes("2/2 有 TLDR")) throw new Error(`missing TLDR coverage: ${html}`);
if (!html.includes("Supabase 已启用")) throw new Error(`missing Supabase active mode: ${html}`);
if (!html.includes("5 条持久反馈")) throw new Error(`missing persisted feedback count: ${html}`);
if (html.includes("SUPABASE_SERVICE_ROLE_KEY")) throw new Error(`unexpected setup prompt: ${html}`);
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
if (!html.includes("<strong>1</strong><span>有单位</span>")) {
  throw new Error(`affiliation coverage stat missing: ${html}`);
}
"""
        )

    def test_reader_renders_repository_cards_with_trend_and_paper_links(self):
        self.run_app_script(
            """
const html = context.renderPaper({
  rank: 1,
  score: 12,
  paper_id: "repo:example/arch-agent",
  item_type: "repository",
  title: "example/arch-agent",
  abstract: "Hardware design agent for gem5.",
  authors: ["example"],
  categories: ["github", "Python", "gem5"],
  sections: ["agentic_architecture"],
  url: "https://github.com/example/arch-agent",
  code_urls: ["https://github.com/example/arch-agent"],
  repository_url: "https://github.com/example/arch-agent",
  repository_stars: 1300,
  repository_forks: 60,
  repository_stars_today: 87,
  repository_language: "Python",
  repository_topics: ["gem5", "microarchitecture"],
  paper_links: [{ label: "arXiv", url: "https://arxiv.org/abs/2606.00001" }],
});
if (!html.includes("GitHub 仓库")) throw new Error(`missing repo type label: ${html}`);
if (!html.includes("今日新增 star 87")) throw new Error(`missing star trend: ${html}`);
if (!html.includes("总 star 1300")) throw new Error(`missing total stars: ${html}`);
if (!html.includes("Python")) throw new Error(`missing language: ${html}`);
if (!html.includes("gem5")) throw new Error(`missing topics: ${html}`);
if (!html.includes("原始论文")) throw new Error(`missing original paper block: ${html}`);
if (!html.includes("https://arxiv.org/abs/2606.00001")) throw new Error(`missing paper link: ${html}`);
"""
        )

    def test_inline_feedback_preserves_repository_metadata(self):
        self.run_app_script(
            """
const event = context.buildFeedbackEvent({
  paper_id: "repo:example/arch-agent",
  item_type: "repository",
  title: "example/arch-agent",
  abstract: "Hardware design agent for gem5.",
  authors: ["example"],
  categories: ["github", "Python", "gem5"],
  sections: ["agentic_architecture"],
  repository_url: "https://github.com/example/arch-agent",
  paper_links: [{ label: "arXiv", url: "https://arxiv.org/abs/2606.00001" }],
}, "like");
if (event.item_type !== "repository") throw new Error(`item_type missing: ${JSON.stringify(event)}`);
if (event.repository_url !== "https://github.com/example/arch-agent") throw new Error(`repo url missing: ${JSON.stringify(event)}`);
if (event.paper_links.length !== 1) throw new Error(`paper links missing: ${JSON.stringify(event)}`);
"""
        )

    def test_inline_feedback_retries_legacy_payload_for_repository_when_supabase_schema_is_old(self):
        self.run_app_script(
            """
const calls = [];
context.window.RECOMMENDER_CONFIG = {
  supabaseUrl: "https://example.supabase.co",
  supabaseAnonKey: "anon-key",
};
context.fetch = async (url, options) => {
  calls.push(JSON.parse(options.body));
  return { ok: calls.length === 2, status: calls.length === 1 ? 400 : 201 };
};
context.postFeedbackEvent({
  paper_id: "repo:example/arch-agent",
  rating: "like",
  source: "page",
  section: "agentic_architecture",
  item_type: "repository",
  title: "example/arch-agent",
  abstract: "Hardware design agent for gem5.",
  authors: ["example"],
  affiliations: [],
  categories: ["github", "Python"],
  repository_url: "https://github.com/example/arch-agent",
  paper_links: [{ label: "arXiv", url: "https://arxiv.org/abs/2606.00001" }],
}).then(() => {
  if (calls.length !== 2) throw new Error(`expected retry, got ${calls.length}`);
  if (!("repository_url" in calls[0])) throw new Error(`new payload missing repo url: ${JSON.stringify(calls[0])}`);
  if ("repository_url" in calls[1]) throw new Error(`legacy payload kept repo url: ${JSON.stringify(calls[1])}`);
  if ("item_type" in calls[1]) throw new Error(`legacy payload kept item type: ${JSON.stringify(calls[1])}`);
}).catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
"""
        )

    def test_reader_shows_feedback_persistence_status(self):
        self.run_app_script(
            """
context.renderFeedbackStatus();
let html = elements.feedbackStatus.innerHTML;
if (!html.includes("仅本地保存")) {
  throw new Error(`missing local-only status: ${html}`);
}

context.window.RECOMMENDER_CONFIG = {
  supabaseUrl: "https://example.supabase.co",
  supabaseAnonKey: "anon-key",
};
context.renderFeedbackStatus();
html = elements.feedbackStatus.innerHTML;
if (!html.includes("Supabase 已启用")) {
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
if (!html.includes("3 条反馈")) {
  throw new Error(`missing feedback count: ${html}`);
}
if (!html.includes("喜欢率 67%")) {
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
if (!html.includes("邮件")) throw new Error(`missing Email status: ${html}`);
if (!html.includes("Supabase")) throw new Error(`missing Supabase status: ${html}`);
if (!html.includes("本地反馈")) throw new Error(`missing local feedback status: ${html}`);
"""
        )

    def test_reader_deep_links_to_paper_from_email_query_param(self):
        self.run_app_script(
            """
context.window.location.search = "?paper_id=2606.00001";
context.highlightTargetPaper();

const target = elements["paper-2606.00001"];
if (!target.classList.contains("is-target")) {
  throw new Error("target paper was not highlighted");
}
if (!target.scrolled) {
  throw new Error("target paper was not scrolled into view");
}
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

        self.assertIn('lang="zh-CN"', html)
        self.assertIn("每日 arXiv 推荐", html)
        self.assertIn("筛选", html)
        self.assertIn("搜索", html)
        self.assertIn("栏目", html)
        self.assertIn("最低 AI 分", html)
        self.assertIn("排序", html)
        self.assertIn("有代码仓库", html)
        self.assertIn("有作者单位", html)
        self.assertIn("编辑兴趣画像", html)
        self.assertLess(html.index('id="searchInput"'), html.index('id="profileSystemWorkspace"'))
        self.assertLess(html.index('id="profileSystemWorkspace"'), html.index('id="runHealth"'))
        self.assertIn('class="filter-sidebar sidebar"', html)
        self.assertIn('id="keywordFilters"', html)
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
        self.assertIn("highlightTargetPaper", script)
        self.assertIn("applyControls", script)
        self.assertIn("filteredRecommendations", script)
        self.assertIn("collectFilterState", script)
        self.assertIn("repository_stars_today", script)
        self.assertIn("paper_links", script)
        self.assertIn(".paper-tldr", styles)
        self.assertIn(".ai-judgement", styles)
        self.assertIn(".controls", styles)
        self.assertIn(".profile-system-grid", styles)
        self.assertIn("max-height: calc(100vh - 32px)", styles)
        self.assertIn("overflow-y: auto", styles)
        self.assertIn(".filter-row", styles)
        self.assertIn(".link-button", styles)
        self.assertIn(".section-nav", styles)
        self.assertIn(".keyword-chip", styles)


if __name__ == "__main__":
    unittest.main()
