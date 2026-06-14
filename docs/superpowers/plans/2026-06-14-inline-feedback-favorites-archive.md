# Inline Feedback Favorites Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep feedback interactions on the recommendation page and archive liked papers into the public `ForeverHYX/daily-recommender-paper-favorites` repository.

**Architecture:** Front-end feedback moves into `site/app.js` as a small in-page service that reuses the same event shape as `site/feedback.js`. A new `paper_recommender.favorites_archive` module reads liked feedback records from Supabase, downloads arXiv PDFs, writes month/category folders, and is called by an optional daily workflow step.

**Tech Stack:** Static HTML/CSS/JS, browser `fetch` and `localStorage`, Python stdlib, GitHub Actions, GitHub CLI.

---

### Task 1: Inline Recommendation Feedback

**Files:**
- Modify: `site/app.js`
- Modify: `site/styles.css`
- Modify: `site/index.html`
- Test: `tests/test_site_contract.py`

- [ ] **Step 1: Write failing tests**

Add tests in `tests/test_site_contract.py` that assert:

```python
def test_recommendation_cards_use_inline_feedback_buttons(self):
    script = Path("site/app.js").read_text(encoding="utf-8")

    self.assertIn("recordInlineFeedback", script)
    self.assertIn("data-feedback-rating", script)
    self.assertNotIn('class="feedback-button like" href="${likeUrl}"', script)
    self.assertNotIn('class="feedback-button dislike" href="${dislikeUrl}"', script)

def test_inline_like_marks_card_with_star(self):
    self.run_app_script(
        """
const storage = {};
context.localStorage = {
  getItem(key) { return Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null; },
  setItem(key, value) { storage[key] = String(value); },
};
context.activePayload = {
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
context.markFeedbackState("2606.00001", "like");
const html = context.renderPaper(context.activePayload.recommendations[0]);
if (!html.includes("paper-favorite-star")) throw new Error(`star missing: ${html}`);
if (!html.includes("已喜欢")) throw new Error(`liked label missing: ${html}`);
"""
    )

def test_inline_dislike_hides_today_recommendation(self):
    self.run_app_script(
        """
const storage = {};
context.localStorage = {
  getItem(key) { return Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null; },
  setItem(key, value) { storage[key] = String(value); },
};
context.activePayload = {
  run_date: "2026-06-14",
  recommendations: [
    { paper_id: "hide-me", rank: 1, score: 7, title: "Hide", abstract: "", sections: ["arch"] },
    { paper_id: "keep-me", rank: 2, score: 6, title: "Keep", abstract: "", sections: ["arch"] },
  ],
  section_labels: { arch: "架构" },
};
context.markFeedbackState("hide-me", "dislike");
const filtered = context.filteredRecommendations(context.activePayload.recommendations, {
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
```

- [ ] **Step 2: Verify tests fail**

Run: `python3 -m unittest tests.test_site_contract.SiteContractTests.test_recommendation_cards_use_inline_feedback_buttons tests.test_site_contract.SiteContractTests.test_inline_like_marks_card_with_star tests.test_site_contract.SiteContractTests.test_inline_dislike_hides_today_recommendation`

Expected: fail because `recordInlineFeedback`, `markFeedbackState`, and the star UI are not implemented.

- [ ] **Step 3: Implement inline feedback**

In `site/app.js`:

- Replace feedback `<a>` links with `<button type="button" class="feedback-button ..." data-feedback-rating="...">`.
- Add `recordInlineFeedback(paperId, rating)`, `buildFeedbackEvent(paper, rating)`, `postFeedbackEvent(event)`, `storeLocalFeedback(event)`, `markFeedbackState(paperId, rating)`, `feedbackStateFor(paperId)`, `hiddenPaperIdsForRun()`, and `showToast(message, kind)`.
- Add one delegated click listener in `renderControls` or `render` for `.feedback-button`.
- Update `filteredRecommendations` to skip paper ids hidden for `activePayload.run_date`.
- Update `renderPaper` to show a right-corner star when `feedbackStateFor(paper.paper_id) === "like"`.

In `site/index.html`, add `<div id="toast" class="toast" role="status" aria-live="polite" hidden></div>` near the app root and bump the `app.js`/`styles.css` asset version.

In `site/styles.css`, add styles for `.paper-favorite-star`, `.toast`, `.toast.is-error`, and button feedback states.

- [ ] **Step 4: Verify tests pass**

Run: `python3 -m unittest tests.test_site_contract`

Expected: all site contract tests pass.

- [ ] **Step 5: Commit**

```bash
git add site/app.js site/index.html site/styles.css tests/test_site_contract.py
git commit -m "Handle recommendation feedback inline"
git push
```

### Task 2: Favorites Archive Exporter

**Files:**
- Create: `paper_recommender/favorites_archive.py`
- Test: `tests/test_favorites_archive.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_favorites_archive.py` with tests for:

```python
def test_export_liked_papers_groups_by_month_and_section(self):
    # Use a fake opener returning one Supabase liked record and one fake PDF response.
    # Expected files:
    # 2026-06/agentic-arch/2606.00001.pdf
    # 2026-06/agentic-arch/2606.00001.json

def test_archive_skips_dislikes_and_records_download_error(self):
    # Use records with one dislike and one like whose PDF opener raises.
    # Expected: no dislike files; like JSON contains download_error.
```

- [ ] **Step 2: Verify tests fail**

Run: `python3 -m unittest tests.test_favorites_archive`

Expected: import fails because `paper_recommender.favorites_archive` does not exist.

- [ ] **Step 3: Implement exporter**

Create `paper_recommender/favorites_archive.py` with:

- `fetch_liked_feedback_events(supabase_url, service_role_key, limit=1000, opener=urlopen)`
- `export_favorites(records, output_dir, opener=urlopen)`
- `paper_pdf_url(paper_id)`
- `slugify(value)`
- CLI args: `--output-dir`, `--limit`

The fetch query selects `paper_id,rating,section,title,abstract,authors,affiliations,categories,created_at` from `feedback_events`, filters to `rating=eq.like`, orders by `created_at.desc`, and uses the service role key only in request headers.

The exporter writes `YYYY-MM/<section-slug>/<paper-id-slug>.json` for every liked record and downloads the PDF to the same folder when the paper id looks like an arXiv id. Download failures are recorded in the JSON sidecar as `download_error`.

- [ ] **Step 4: Verify tests pass**

Run: `python3 -m unittest tests.test_favorites_archive`

Expected: all archive tests pass.

- [ ] **Step 5: Commit**

```bash
git add paper_recommender/favorites_archive.py tests/test_favorites_archive.py
git commit -m "Export liked papers to favorites archive"
git push
```

### Task 3: Workflow And Public Archive Repository

**Files:**
- Modify: `.github/workflows/daily.yml`
- Modify: `tests/test_workflow_contract.py`

- [ ] **Step 1: Write failing workflow contract test**

Add a test that asserts:

```python
def test_daily_workflow_optionally_exports_liked_papers_archive(self):
    workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

    self.assertIn("HAS_FAVORITES_ARCHIVE", workflow)
    self.assertIn("LIKED_PAPERS_REPO: ${{ vars.LIKED_PAPERS_REPO }}", workflow)
    self.assertIn("LIKED_PAPERS_REPO_TOKEN: ${{ secrets.LIKED_PAPERS_REPO_TOKEN }}", workflow)
    self.assertIn("python -m paper_recommender.favorites_archive", workflow)
    self.assertIn("daily-recommender-paper-favorites", workflow)
```

- [ ] **Step 2: Verify test fails**

Run: `python3 -m unittest tests.test_workflow_contract.WorkflowContractTests.test_daily_workflow_optionally_exports_liked_papers_archive`

Expected: fail because the workflow has no archive step.

- [ ] **Step 3: Implement workflow**

Add env:

```yaml
HAS_FAVORITES_ARCHIVE: ${{ vars.LIKED_PAPERS_REPO != '' && secrets.LIKED_PAPERS_REPO_TOKEN != '' }}
```

Add a step after `Publish Supabase recommendation history`:

```yaml
- name: Export liked papers archive
  if: env.HAS_SUPABASE == 'true' && env.HAS_FAVORITES_ARCHIVE == 'true'
  env:
    SUPABASE_URL: ${{ vars.SUPABASE_URL }}
    SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
    LIKED_PAPERS_REPO: ${{ vars.LIKED_PAPERS_REPO }}
    LIKED_PAPERS_REPO_TOKEN: ${{ secrets.LIKED_PAPERS_REPO_TOKEN }}
  run: |
    git clone "https://x-access-token:${LIKED_PAPERS_REPO_TOKEN}@github.com/${LIKED_PAPERS_REPO}.git" ../favorites-archive
    python -m paper_recommender.favorites_archive --output-dir ../favorites-archive
    cd ../favorites-archive
    git config user.name "github-actions[bot]"
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
    if [ -n "$(git status --porcelain)" ]; then
      git add .
      git commit -m "Update liked paper archive"
      git push
    else
      echo "No liked paper archive changes"
    fi
```

Before running this workflow, create the public archive repository if missing:

```bash
gh repo view ForeverHYX/daily-recommender-paper-favorites >/dev/null 2>&1 || gh repo create ForeverHYX/daily-recommender-paper-favorites --public --description "Liked papers exported from the daily architecture paper recommender"
```

- [ ] **Step 4: Verify workflow tests pass**

Run: `python3 -m unittest tests.test_workflow_contract`

Expected: all workflow contract tests pass.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/daily.yml tests/test_workflow_contract.py
git commit -m "Archive liked papers to public repository"
git push
```

### Task 4: Final Verification

**Files:**
- All changed files

- [ ] **Step 1: Run complete verification**

Run:

```bash
python3 -m unittest discover -s tests
node --check site/app.js
node --check site/profile.js
node --check site/feedback.js
git diff --check
rg -n --hidden --glob '!.git' --glob '!node_modules' --glob '!.venv' --glob '!__pycache__' "(sk-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{20,}\\.[A-Za-z0-9_-]{20,}\\.[A-Za-z0-9_-]{20,})" .
```

Expected:

- Python tests pass.
- Node syntax checks pass.
- `git diff --check` has no output.
- Secret scan has no matches.

- [ ] **Step 2: Trigger workflow**

Run:

```bash
gh workflow run daily.yml --repo ForeverHYX/agentic-arch-paper-recommender
gh run list --repo ForeverHYX/agentic-arch-paper-recommender --workflow daily.yml --limit 5
```

Expected: new run starts.

- [ ] **Step 3: Verify run and site**

Run:

```bash
gh run view <run_id> --repo ForeverHYX/agentic-arch-paper-recommender --json status,conclusion,jobs
```

Expected: workflow succeeds. If archive variables are not configured yet, archive step is skipped. If configured, archive step commits changes only when liked papers exist.

Use `agent-browser` to verify:

- Clicking `喜欢` does not leave the recommendations page and shows a star.
- Clicking `不喜欢` does not leave the recommendations page and removes the card.
- A toast appears for both actions.

---

## Self-Review

- Spec coverage: Task 1 covers inline feedback and local UI state. Task 2 covers PDF/metadata archive generation. Task 3 covers the public archive repository and optional workflow step. Task 4 covers final verification.
- Placeholder scan: no open marker text remains.
- Type consistency: front-end uses existing paper fields and feedback event metadata; archive module consumes the existing Supabase feedback table shape.
