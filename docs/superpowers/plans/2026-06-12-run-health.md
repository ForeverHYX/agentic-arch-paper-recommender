# Run Health Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a compact GitHub Pages sidebar block that shows daily AI coverage and whether feedback is persistent enough to affect future recommendations.

**Architecture:** The static reader already loads `recommendations.json`, `status.json`, `config.js`, and local feedback state. Add one HTML placeholder, one pure `renderRunHealth(payload, status)` renderer in `site/app.js`, and compact sidebar styling in `site/styles.css`. The renderer derives coverage from public recommendation data and setup state from existing public config/status without exposing secrets.

**Tech Stack:** Static HTML/CSS/JavaScript, existing Node VM site contract tests in `tests/test_site_contract.py`, Python `unittest`.

---

## File Structure

- Modify `site/index.html`
  - Add `<div id="runHealth" class="run-health" aria-live="polite"></div>` after the existing subsystem status block.
  - Bump `app.js` cache query to `20260612-run-health`.
- Modify `site/app.js`
  - Call `renderRunHealth(payload, null)` during initial render.
  - Update both `renderSubsystemStatus(status)` and `renderRunHealth(payload, status)` after `loadStatus()` resolves.
  - Add helpers for recommendation coverage and feedback mode.
- Modify `site/styles.css`
  - Reuse sidebar status block styling for `.run-health`.
- Modify `tests/test_site_contract.py`
  - Add contract tests for the `runHealth` placeholder, cache version, AI/TLDR coverage, Supabase active mode, local-only mode, and missing Supabase setup names.
- Modify `progress.md`
  - Record the implementation and deployment evidence after verification.

## Task 1: Failing Site Contract Tests

**Files:**
- Modify: `tests/test_site_contract.py`
- Test: `tests/test_site_contract.py`

- [ ] **Step 1: Add tests for the HTML placeholder and app cache version**

Add this test near the existing index cache-busting tests:

```python
def test_index_contains_run_health_placeholder_and_cache_bust(self):
    html = Path("site/index.html").read_text(encoding="utf-8")

    self.assertIn('id="runHealth"', html)
    self.assertIn('class="run-health"', html)
    self.assertIn("app.js?v=20260612-run-health", html)
```

- [ ] **Step 2: Add tests for Run Health render output**

Add this test to `SiteContractTests`:

```python
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
if (!html.includes("Run Health")) throw new Error(`missing heading: ${html}`);
if (!html.includes("2/3 judged")) throw new Error(`missing judgement coverage: ${html}`);
if (!html.includes("2/3 TLDR")) throw new Error(`missing TLDR coverage: ${html}`);
if (!html.includes("local only")) throw new Error(`missing local feedback mode: ${html}`);
if (!html.includes("not persistent yet")) throw new Error(`missing learning warning: ${html}`);
if (!html.includes("SUPABASE_URL")) throw new Error(`missing Supabase URL setup: ${html}`);
if (!html.includes("SUPABASE_ANON_KEY")) throw new Error(`missing Supabase anon setup: ${html}`);
if (!html.includes("SUPABASE_SERVICE_ROLE_KEY")) throw new Error(`missing service role setup: ${html}`);
"""
    )
```

Add this test to cover active Supabase mode:

```python
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
if (!html.includes("2/2 judged")) throw new Error(`missing judgement coverage: ${html}`);
if (!html.includes("2/2 TLDR")) throw new Error(`missing TLDR coverage: ${html}`);
if (!html.includes("Supabase active")) throw new Error(`missing Supabase active mode: ${html}`);
if (!html.includes("5 persisted events")) throw new Error(`missing persisted feedback count: ${html}`);
if (html.includes("SUPABASE_SERVICE_ROLE_KEY")) throw new Error(`unexpected setup prompt: ${html}`);
"""
    )
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
python3 -m unittest \
  tests.test_site_contract.SiteContractTests.test_index_contains_run_health_placeholder_and_cache_bust \
  tests.test_site_contract.SiteContractTests.test_reader_shows_run_health_for_local_feedback_mode \
  tests.test_site_contract.SiteContractTests.test_reader_shows_run_health_for_supabase_mode
```

Expected: failures because `runHealth` placeholder and `renderRunHealth` do not exist yet.

## Task 2: Minimal HTML and JavaScript Implementation

**Files:**
- Modify: `site/index.html`
- Modify: `site/app.js`
- Test: `tests/test_site_contract.py`

- [ ] **Step 1: Add the sidebar placeholder and cache bust**

In `site/index.html`, add the placeholder after `subsystemStatus`:

```html
<div id="runHealth" class="run-health" aria-live="polite"></div>
```

Change:

```html
<script src="app.js?v=20260612-affiliations"></script>
```

to:

```html
<script src="app.js?v=20260612-run-health"></script>
```

- [ ] **Step 2: Wire Run Health into status loading**

Update `render(payload)` in `site/app.js` to render a status-independent first pass and update it when `status.json` loads:

```javascript
renderRunHealth(payload, null);
loadStatus().then((status) => {
  renderSubsystemStatus(status);
  renderRunHealth(payload, status);
}).catch(() => {
  renderSubsystemStatus(null);
  renderRunHealth(payload, null);
});
```

- [ ] **Step 3: Add the renderer and helper functions**

Add these functions near the existing sidebar renderers:

```javascript
function renderRunHealth(payload, status) {
  const target = document.getElementById("runHealth");
  if (!target) return;

  const recommendations = Array.isArray(payload?.recommendations) ? payload.recommendations : [];
  const total = recommendations.length;
  const judged = recommendations.filter((paper) => paper.ai_judgement || paper.ai_score !== undefined).length;
  const summarized = recommendations.filter((paper) => String(paper.tldr || "").trim()).length;
  const metrics = payload?.feedback_summary?.metrics || {};
  const persistedEvents = Number(metrics.total_events || 0);
  const supabaseActive = isSupabaseActive(status);
  const feedbackMode = supabaseActive ? "Supabase active" : "local only";
  const learningState = supabaseActive
    ? `${persistedEvents} persisted event${persistedEvents === 1 ? "" : "s"}`
    : "not persistent yet";
  const setup = supabaseActive
    ? ""
    : '<span>Next setup: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY</span>';

  target.innerHTML = `
    <strong>Run Health</strong>
    <span>AI: ${judged}/${total} judged, ${summarized}/${total} TLDR</span>
    <span>Feedback: ${escapeHtml(feedbackMode)}</span>
    <span>Learning: ${escapeHtml(learningState)}</span>
    ${setup}
  `;
}

function isSupabaseActive(status) {
  const config = window.RECOMMENDER_CONFIG || {};
  return Boolean(
    status?.supabase?.configured ||
    (config.supabaseUrl && config.supabaseAnonKey)
  );
}
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run the same focused command from Task 1.

Expected: all three focused tests pass.

## Task 3: Styling and Existing Status Consistency

**Files:**
- Modify: `site/styles.css`
- Modify: `site/app.js`
- Test: `tests/test_site_contract.py`

- [ ] **Step 1: Reuse existing sidebar status styling**

In `site/styles.css`, include `.run-health` with the existing sidebar status blocks:

```css
.feedback-status,
.feedback-insights,
.subsystem-status,
.run-health {
  display: grid;
  gap: 6px;
  border-top: 1px solid var(--line);
  padding-top: 12px;
  font-size: 12px;
  color: var(--muted);
}
```

If the exact block already differs, add `.run-health` to that selector rather than duplicating properties.

- [ ] **Step 2: Keep existing subsystem behavior unchanged**

Confirm `renderSubsystemStatus` still produces `LLM`, `Email`, `Supabase`, `local feedback`, and `profile override` rows.

- [ ] **Step 3: Run site contract tests**

Run:

```bash
python3 -m unittest tests.test_site_contract
```

Expected: all site contract tests pass.

## Task 4: Progress Docs, Verification, Commit, Deploy

**Files:**
- Modify: `progress.md`
- Read: `.github/workflows/daily.yml`
- Test: full repo verification commands

- [ ] **Step 1: Update progress**

Append a short `会话补充：Run Health 安静状态提示` section to `progress.md` listing:

- sidebar now shows AI judgement/TLDR coverage
- sidebar shows Supabase/local-only learning mode
- Supabase setup names are shown when persistent feedback is missing
- tests and deployment evidence after verification

- [ ] **Step 2: Run full verification**

Run:

```bash
python3 -m unittest discover -s tests
node --check site/app.js
node --check site/feedback.js
node --check site/profile.js
python3 -m json.tool site/recommendations.json >/tmp/aapr-recommendations-json-check.txt
git diff --check
<run the repository sensitive-token scan command from the current handoff notes>
```

Expected: all commands exit 0 and the secret scan prints `no sensitive tokens found`.

- [ ] **Step 3: Commit and push**

Run:

```bash
git add site/index.html site/app.js site/styles.css tests/test_site_contract.py progress.md docs/superpowers/plans/2026-06-12-run-health.md
git commit -m "Add run health sidebar status"
git push
```

- [ ] **Step 4: Trigger and watch deployment**

Run:

```bash
gh workflow run "Daily Paper Recommender" --repo ForeverHYX/agentic-arch-paper-recommender --ref main
gh run list --repo ForeverHYX/agentic-arch-paper-recommender --workflow "Daily Paper Recommender" --limit 1
gh run watch <run-id> --repo ForeverHYX/agentic-arch-paper-recommender --exit-status
```

Expected: workflow and Pages deploy finish with conclusion `success`.

- [ ] **Step 5: Verify Pages output**

Run:

```bash
curl -fsSL "https://foreverhyx.github.io/agentic-arch-paper-recommender/index.html?ts=$(date +%s)" -o /tmp/aapr-index-run-health.html
curl -fsSL "https://foreverhyx.github.io/agentic-arch-paper-recommender/app.js?v=20260612-run-health&ts=$(date +%s)" -o /tmp/aapr-app-run-health.js
rg -n "runHealth|20260612-run-health" /tmp/aapr-index-run-health.html /tmp/aapr-app-run-health.js
```

Expected: online HTML contains `runHealth` and `app.js?v=20260612-run-health`; online JS contains `renderRunHealth`.
