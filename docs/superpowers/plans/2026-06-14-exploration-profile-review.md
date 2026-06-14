# Exploration Profile Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 extra daily AI/ML architecture-adjacent exploration papers and generate a safe LLM profile review overlay without automatically rewriting the canonical profile.

**Architecture:** The pipeline will add explicit `exploration` candidates beside the existing core candidate pool. LLM judgement will preserve separate quotas: up to 15 core recommendations plus up to 5 exploration recommendations. A new `profile_review` module will produce deployable review JSON and attach it to the recommendation payload; the frontend will render that review on the profile page.

**Tech Stack:** Python standard library, existing OpenAI-compatible chat completion helpers, unittest, GitHub Actions, vanilla HTML/CSS/JS.

---

## File Structure

- Modify `paper_recommender/pipeline.py`: add exploration candidate selection, section label injection, CLI flags.
- Modify `paper_recommender/judge.py`: add `exploration_limit` quota handling and CLI flag.
- Create `paper_recommender/profile_review.py`: request, parse, normalize, and write constrained LLM profile review JSON.
- Modify `.github/workflows/daily.yml`: pass exploration flags and run profile review after TLDR enrichment.
- Modify `site/profile.html`, `site/profile.js`, `site/styles.css`: render profile review if present.
- Modify tests:
  - `tests/test_pipeline.py`
  - `tests/test_judge.py`
  - `tests/test_profile_review.py`
  - `tests/test_profile_page_contract.py`
  - `tests/test_workflow_contract.py`
  - `tests/test_site_contract.py` if asset versions change.

## Task 1: Pipeline Exploration Candidates

**Files:**
- Modify: `paper_recommender/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test for extra exploration recommendations**

Add a test that builds two core papers and six AI/ML architecture-adjacent non-core papers, then calls:

```python
payload = recommendation_payload(
    papers,
    "2026-06-14",
    limit=2,
    min_count=2,
    exploration_count=5,
    profile=profile,
)
```

Assert:

```python
self.assertEqual(payload["count"], 7)
self.assertEqual(sum("exploration" in item["sections"] for item in payload["recommendations"]), 5)
self.assertEqual(payload["section_labels"]["exploration"], "Exploration / AI+体系结构探索")
```

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_pipeline.PipelineTests.test_recommendation_payload_adds_extra_exploration_papers`

Expected: FAIL because `recommendation_payload` does not accept `exploration_count`.

- [ ] **Step 3: Implement minimal pipeline support**

Add:

```python
EXPLORATION_SECTION = "exploration"
EXPLORATION_LABEL = "Exploration / AI+体系结构探索"
EXPLORATION_CATEGORIES = frozenset({"cs.AI", "cs.LG", "cs.AR", "cs.PF", "cs.DC", "cs.PL"})
EXPLORATION_KEYWORDS = (
    "accelerator", "gpu", "hardware-aware", "hardware aware", "ml compiler",
    "machine learning systems", "systems for machine learning", "performance model",
    "runtime", "compiler", "inference serving", "training system", "tensor",
    "systolic", "fpga", "asic", "memory hierarchy", "interconnect",
)
```

Add an `exploration_count: int = 0` parameter to `recommendation_payload()` and `write_recommendations_json()`, add CLI flag `--exploration-count`, and append `_exploration_candidates(...)` after the core ranked list has been limited. Exploration candidates must exclude already ranked papers, accepted core papers, negative matches, and non-matching keyword/category papers. They must use:

```python
Classification(
    paper=paper,
    accepted=True,
    score=0.0,
    sections=(EXPLORATION_SECTION,),
    positive_matches=tuple(f"exploration:{match}" for match in matches),
    negative_matches=(),
)
```

- [ ] **Step 4: Run GREEN**

Run: `python3 -m unittest tests.test_pipeline`

Expected: OK.

- [ ] **Step 5: Commit**

Run:

```bash
git add paper_recommender/pipeline.py tests/test_pipeline.py
git commit -m "Add exploration recommendation candidates"
git push
```

## Task 2: LLM Judgement Preserves Core and Exploration Quotas

**Files:**
- Modify: `paper_recommender/judge.py`
- Test: `tests/test_judge.py`

- [ ] **Step 1: Write failing quota test**

Create a payload with 17 core candidates and 6 exploration candidates. The fake opener returns keep for all. Call:

```python
enriched = enrich_payload_with_judgements(
    payload,
    api_key="secret",
    limit=15,
    exploration_limit=5,
    opener=opener,
)
```

Assert 20 recommendations, 15 non-exploration, 5 exploration, and `judge_summary["exploration_limit"] == 5`.

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_judge.JudgeTests.test_enrich_payload_with_judgements_preserves_exploration_quota`

Expected: FAIL because `exploration_limit` does not exist.

- [ ] **Step 3: Implement quota split**

Add `exploration_limit: int = 0` to `enrich_payload_with_judgements()`. After sorting kept items, split with:

```python
exploration = [item for item in kept if "exploration" in item.get("sections", [])]
core = [item for item in kept if "exploration" not in item.get("sections", [])]
selected = core[:limit] + exploration[:exploration_limit]
selected.sort(key=_ranking_key)
```

Add CLI flag `--exploration-limit` and include `core_limit`, `exploration_limit`, `core_kept_count`, and `exploration_kept_count` in `judge_summary`.

- [ ] **Step 4: Run GREEN**

Run: `python3 -m unittest tests.test_judge`

Expected: OK.

- [ ] **Step 5: Commit**

Run:

```bash
git add paper_recommender/judge.py tests/test_judge.py
git commit -m "Preserve exploration quota in LLM judgement"
git push
```

## Task 3: Profile Review Module

**Files:**
- Create: `paper_recommender/profile_review.py`
- Test: `tests/test_profile_review.py`

- [ ] **Step 1: Write failing tests**

Add tests for:

```python
review = parse_profile_review_response('{"summary_zh":"反馈显示更偏好 GPU 系统。","positive_adjustments":["增强 GPU/ML systems"],"negative_adjustments":["降低泛 Web agent"],"exploration_notes":["探索反馈仍少"],"risk_notes":["样本不足"],"apply_to_runtime":true}')
self.assertFalse(review["apply_to_runtime"])
self.assertIn("GPU", review["summary_zh"])
```

And a require-API test with `HTTPError` asserting the exception mentions HTTP/model/base URL but not the API key.

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest tests.test_profile_review`

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement profile review**

Implement:

```python
def parse_profile_review_response(content: str) -> dict[str, Any]
def request_profile_review(profile: dict[str, Any], payload: dict[str, Any], api_key: str, ...)
def enrich_payload_with_profile_review(payload: dict[str, Any], profile: dict[str, Any], ...)
def main(argv: list[str] | None = None) -> int
```

Normalize arrays to at most 6 short strings, force `apply_to_runtime` to `False`, set `model` and `generated_at`, and write both `site/profile_review.json` and `payload["profile_review"]`.

- [ ] **Step 4: Run GREEN**

Run: `python3 -m unittest tests.test_profile_review`

Expected: OK.

- [ ] **Step 5: Commit**

Run:

```bash
git add paper_recommender/profile_review.py tests/test_profile_review.py
git commit -m "Add LLM profile review overlay"
git push
```

## Task 4: Workflow and Frontend Rendering

**Files:**
- Modify: `.github/workflows/daily.yml`
- Modify: `site/profile.html`
- Modify: `site/profile.js`
- Modify: `site/styles.css`
- Modify tests:
  - `tests/test_workflow_contract.py`
  - `tests/test_profile_page_contract.py`
  - `tests/test_site_contract.py`

- [ ] **Step 1: Write failing workflow and frontend tests**

Assert workflow contains:

```yaml
--exploration-count 12
--exploration-limit 5
python -m paper_recommender.profile_review
```

Assert `profile.html` has `id="profileReview"` and `profile.js` fetches `profile_review.json`.

- [ ] **Step 2: Run RED**

Run:

```bash
python3 -m unittest tests.test_workflow_contract tests.test_profile_page_contract tests.test_site_contract
```

Expected: FAIL on missing workflow/profile review hooks.

- [ ] **Step 3: Implement workflow and frontend**

Change workflow:

```bash
python -m paper_recommender.pipeline ... --limit 45 --min-count 45 --exploration-count 12
python -m paper_recommender.judge ... --limit 15 --exploration-limit 5 $REQUIRE_API
python -m paper_recommender.profile_review \
  --profile output/interests.json \
  --recommendations site/recommendations.json \
  --output site/profile_review.json $REQUIRE_API
```

Add profile page review block with Chinese labels: “LLM 画像复核”, “增强方向”, “降权方向”, “探索观察”, “风险提示”.

- [ ] **Step 4: Run GREEN**

Run:

```bash
python3 -m unittest tests.test_workflow_contract tests.test_profile_page_contract tests.test_site_contract
node --check site/profile.js
```

Expected: OK.

- [ ] **Step 5: Commit**

Run:

```bash
git add .github/workflows/daily.yml site/profile.html site/profile.js site/styles.css tests/test_workflow_contract.py tests/test_profile_page_contract.py tests/test_site_contract.py
git commit -m "Show LLM profile review overlay"
git push
```

## Task 5: Final Verification and Workflow Run

**Files:**
- No planned edits.

- [ ] **Step 1: Run full verification**

Run:

```bash
python3 -m unittest discover -s tests
node --check site/app.js
node --check site/profile.js
node --check site/feedback.js
git diff --check
rg -n --hidden --glob '!.git' --glob '!node_modules' --glob '!.venv' --glob '!__pycache__' "(sk-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{20,}\\.[A-Za-z0-9_-]{20,}\\.[A-Za-z0-9_-]{20,})" .
```

Expected: tests and syntax checks exit 0; secret scan has no matches and exits 1.

- [ ] **Step 2: Trigger workflow**

Run:

```bash
gh workflow run daily.yml --repo ForeverHYX/agentic-arch-paper-recommender
gh run list --repo ForeverHYX/agentic-arch-paper-recommender --limit 5
gh run view <run_id> --repo ForeverHYX/agentic-arch-paper-recommender --json status,conclusion,jobs
```

Expected: build and deploy success.

- [ ] **Step 3: Validate deployed payload**

Use `curl` and Python to assert:

```python
len(core) <= 15
len(exploration) == 5
payload["profile_review"]["apply_to_runtime"] is False
all("规则得分兜底" not in item["ai_judgement"]["reason"] for item in recommendations)
```

Also open the profile page and confirm the profile review text renders in Chinese.
