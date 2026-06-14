# Reader UI Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the static reader with a floating island, top type tabs, left recommendation feed, right keyword filters, and a separate profile/system tab.

**Architecture:** Keep the app as vanilla static HTML/CSS/JS. `site/app.js` will add UI state for active tab and selected keyword chips, derive keyword facets from the recommendation payload, and render either the recommendations workspace or the profile/system workspace. `site/styles.css` will adapt the Homepage articles glass-card layout without adding a build step.

**Tech Stack:** Static HTML, CSS, browser JavaScript, Python `unittest`, Node VM tests used by `tests/test_site_contract.py`.

---

## File Structure

- Modify `site/index.html`
  - Replace the old left-sidebar layout with a floating island header, a top tab bar, recommendation workspace, right filter panel, and profile/system panel.
  - Keep IDs used by existing tests: `runDate`, `summaryStats`, `recommendations`, `runHealth`, `feedbackStatus`, `feedbackInsights`, `subsystemStatus`, `resultCount`, `searchInput`, `sectionFilter`, `minAiScore`, `hasCodeFilter`, `hasAffiliationFilter`, `sortSelect`, `sectionNav`, and `toast`.
  - Add hooks: `readerTabs`, `recommendationWorkspace`, `profileSystemWorkspace`, `keywordFilters`, `typeKeywordFilters`, `contentKeywordFilters`.
- Modify `site/app.js`
  - Add `uiState.activeTab` and `uiState.selectedKeywords`.
  - Add tab event handling and tab-count rendering.
  - Add keyword facet derivation and chip toggling.
  - Extend filtering to respect active tab and selected keywords.
  - Render profile/system details in the dedicated tab.
- Modify `site/styles.css`
  - Add Homepage-inspired variables, floating island, articles-style two-column grid, glass cards, tabs, keyword chips, responsive layout.
  - Keep existing card and feedback classes working.
- Modify `tests/test_site_contract.py`
  - Add contract tests for the new layout hooks, item-type tabs, keyword filtering, and profile/system tab.
- Modify `progress.md`
  - Record the UI redesign implementation and verification.

## Task 1: Layout Contract

**Files:**
- Modify: `tests/test_site_contract.py`
- Modify: `site/index.html`
- Modify: `site/styles.css`

- [ ] **Step 1: Write failing layout tests**

Add tests that read `site/index.html` and `site/styles.css` and assert these strings exist:

```python
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
```

- [ ] **Step 2: Run RED**

Run:

```bash
python3 -m unittest tests.test_site_contract.SiteContractTests.test_index_uses_reader_tabs_and_keyword_filter_layout
```

Expected: fail because the current index has no reader tabs or keyword panel hooks.

- [ ] **Step 3: Implement static layout hooks**

Update `site/index.html` to include:

```html
<header class="site-header">
  <div class="container nav-shell">
    <div class="nav-island">
      <div class="nav-island-body">
        <a class="brand nav-brand" href="index.html">每日推荐</a>
        <nav id="readerTabs" class="reader-tabs" aria-label="推荐类型">
          <button type="button" class="reader-tab is-active" data-tab="all">全部</button>
          <button type="button" class="reader-tab" data-tab="paper">论文</button>
          <button type="button" class="reader-tab" data-tab="repository">仓库</button>
          <button type="button" class="reader-tab" data-tab="profile">画像与系统</button>
        </nav>
      </div>
    </div>
  </div>
</header>
```

Keep all existing filter IDs inside a right-side panel and move `runHealth`, `feedbackStatus`, `feedbackInsights`, and `subsystemStatus` into `profileSystemWorkspace`.

- [ ] **Step 4: Add minimal CSS hooks**

Add `.site-header`, `.nav-island`, `.reader-tabs`, `.article-grid`, `.filter-sidebar`, `.keyword-chip`, and `.profile-system-grid` styles.

- [ ] **Step 5: Run GREEN**

Run:

```bash
python3 -m unittest tests.test_site_contract.SiteContractTests.test_index_uses_reader_tabs_and_keyword_filter_layout
```

Expected: pass.

- [ ] **Step 6: Commit and push**

Run:

```bash
git add site/index.html site/styles.css tests/test_site_contract.py
git commit -m "feat: add reader tab layout hooks"
git push origin main
```

## Task 2: Type Tabs and Profile/System Tab

**Files:**
- Modify: `tests/test_site_contract.py`
- Modify: `site/app.js`
- Modify: `site/styles.css`

- [ ] **Step 1: Write failing tests**

Add a Node VM test that renders a payload with one paper and one repository, then:

```javascript
context.render(payload);
context.setActiveTab("paper");
let filtered = context.filteredRecommendations(payload.recommendations, context.collectFilterState());
if (filtered.length !== 1 || filtered[0].item_type === "repository") throw new Error("paper tab failed");
context.setActiveTab("repository");
filtered = context.filteredRecommendations(payload.recommendations, context.collectFilterState());
if (filtered.length !== 1 || filtered[0].item_type !== "repository") throw new Error("repository tab failed");
context.setActiveTab("profile");
if (!elements.profileSystemWorkspace.classList.contains("is-active")) throw new Error("profile tab inactive");
if (!elements.recommendationWorkspace.classList.contains("is-hidden")) throw new Error("recommendations still visible");
```

- [ ] **Step 2: Run RED**

Run the new test. Expected: fail because `setActiveTab` does not exist.

- [ ] **Step 3: Implement tab state**

Add:

```javascript
const uiState = {
  activeTab: "all",
  selectedKeywords: new Set(),
};

function setActiveTab(tab) {
  uiState.activeTab = ["all", "paper", "repository", "profile"].includes(tab) ? tab : "all";
  updateTabPanels();
  applyControls();
}
```

Bind tab buttons in `renderControls`, add `typeMatchesActiveTab(paper)`, and call it from `filteredRecommendations`.

- [ ] **Step 4: Run GREEN**

Run the new test and the existing site contract tests.

- [ ] **Step 5: Commit and push**

Run:

```bash
git add site/app.js site/styles.css tests/test_site_contract.py
git commit -m "feat: add reader type tabs"
git push origin main
```

## Task 3: Keyword Filters

**Files:**
- Modify: `tests/test_site_contract.py`
- Modify: `site/app.js`
- Modify: `site/styles.css`

- [ ] **Step 1: Write failing keyword tests**

Add a Node VM test that renders a repository with topic `gem5` and a paper with abstract text `branch predictor`, then verifies:

```javascript
context.render(payload);
context.toggleKeywordFilter("gem5");
let filtered = context.filteredRecommendations(payload.recommendations, context.collectFilterState());
if (filtered.length !== 1 || filtered[0].paper_id !== "repo:example/gem5-tools") throw new Error("gem5 keyword failed");
context.toggleKeywordFilter("gem5");
context.toggleKeywordFilter("branch predictor");
filtered = context.filteredRecommendations(payload.recommendations, context.collectFilterState());
if (filtered.length !== 1 || filtered[0].paper_id !== "2606.00001") throw new Error("paper content keyword failed");
```

- [ ] **Step 2: Run RED**

Run the new keyword test. Expected: fail because `toggleKeywordFilter` does not exist.

- [ ] **Step 3: Implement keyword derivation and filtering**

Add:

```javascript
function keywordFacetsFor(recommendations, sectionLabels) {
  return {
    type: [
      { keyword: "paper", label: "paper", count: recommendations.filter((item) => !isRepositoryItem(item)).length },
      { keyword: "repository", label: "repository", count: recommendations.filter(isRepositoryItem).length },
    ],
    content: deriveContentKeywords(recommendations, sectionLabels),
  };
}
```

Use normalized keyword matching against `searchTextFor(paper)` and render chips into `typeKeywordFilters` and `contentKeywordFilters`.

- [ ] **Step 4: Run GREEN**

Run the keyword test and site contract suite.

- [ ] **Step 5: Commit and push**

Run:

```bash
git add site/app.js site/styles.css tests/test_site_contract.py
git commit -m "feat: add recommendation keyword filters"
git push origin main
```

## Task 4: Visual Polish and Full Verification

**Files:**
- Modify: `site/styles.css`
- Modify: `progress.md`

- [ ] **Step 1: Polish Homepage-inspired styling**

Ensure the first viewport shows the floating island and recommendation workspace. Use restrained light glass styling, 8px-or-less card radius for recommendation cards, non-overlapping responsive controls, and no nested cards.

- [ ] **Step 2: Run contract tests**

Run:

```bash
python3 -m unittest tests.test_site_contract tests.test_profile_page_contract
```

Expected: all tests pass.

- [ ] **Step 3: Run full tests**

Run:

```bash
python3 -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 4: Start local server and inspect UI**

Run:

```bash
python3 -m http.server 8000 --directory site
```

Open `http://localhost:8000/`, verify desktop and mobile layout, tab switching, keyword chips, feedback buttons, and profile/system tab.

- [ ] **Step 5: Record progress**

Add a progress entry with changed files and verification commands.

- [ ] **Step 6: Commit and push**

Run:

```bash
git add site/styles.css progress.md
git commit -m "style: polish reader articles layout"
git push origin main
```

