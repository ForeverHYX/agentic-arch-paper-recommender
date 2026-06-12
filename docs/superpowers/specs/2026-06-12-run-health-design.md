# Run Health Sidebar Design

## Context

The project already publishes `recommendations.json` and `status.json` to GitHub Pages. The sidebar currently shows separate feedback, learning, and subsystem snippets, but it does not clearly answer whether the daily run actually produced AI judgement/TLDR coverage or whether feedback will affect future runs.

This design adds a quiet status block to the existing sidebar. It does not add a new page, backend service, or recommendation algorithm.

## Goals

- Show daily run quality at a glance.
- Make LLM output coverage visible, not just whether an API key is configured.
- Make the feedback learning mode explicit.
- Keep setup guidance short and actionable when Supabase is missing.
- Preserve the current static GitHub Pages deployment model.

## Non-Goals

- Do not create a full setup wizard.
- Do not expose secrets or private configuration values.
- Do not change scoring, LLM prompts, feedback storage, or email behavior.
- Do not block page rendering if `status.json` is unavailable.

## User Experience

Add a compact `Run Health` block in the sidebar near the existing `Systems`, `Feedback`, and `Learning` sections.

The block should display:

- `AI`: judgement coverage and TLDR coverage, for example `12/12 judged, 12/12 TLDR`.
- `Feedback`: `Supabase active` when public Supabase config exists, otherwise `local only`.
- `Learning`: persisted feedback count when available, otherwise `not persistent yet`.
- `Next setup`: shown only when Supabase is not active. It lists the missing persistent-learning settings: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY`.

The copy should stay terse and operational. It should help the user understand current state without turning the reader into documentation.

## Data Flow

The block uses only public static data already loaded by the reader:

- `recommendations.json`
  - final recommendation count
  - per-paper `ai_judgement`
  - per-paper `tldr`
  - `feedback_summary.metrics.total_events`
- `status.json`
  - public booleans for LLM, SMTP, Supabase, local feedback, and profile override
- `window.RECOMMENDER_CONFIG`
  - public Supabase URL and anon key presence
- browser `localStorage`
  - local feedback count, using the existing helper

No secret values should be rendered. The service role key is mentioned only as a missing setup item.

## Components

### HTML

Add one sidebar placeholder:

```html
<div id="runHealth" class="run-health" aria-live="polite"></div>
```

### JavaScript

Add a pure renderer:

```text
renderRunHealth(payload, status)
```

It should tolerate missing `status` and missing payload sections.

The existing `render(payload)` flow should call `renderRunHealth(payload, null)` immediately, then update it after `loadStatus()` resolves. This keeps the page useful even if `status.json` fails to load.

### CSS

Reuse the visual language of existing sidebar status blocks. The block should be compact, text-first, and not styled as a large card.

## Error Handling

- If `status.json` fails, show run coverage from `recommendations.json` and mark systems status as unavailable.
- If there are zero recommendations, show `0/0 judged, 0/0 TLDR`.
- If feedback metrics are absent, treat persisted feedback count as zero.
- If Supabase public config is absent, show `local only` even when browser-local clicks exist.

## Testing

Add site contract tests that execute `site/app.js` in the existing Node VM harness:

- `renderRunHealth` reports AI judgement and TLDR coverage.
- `renderRunHealth` reports `Supabase active` when public Supabase config exists.
- `renderRunHealth` reports `local only`, `not persistent yet`, and the three Supabase setup names when Supabase is absent.
- `index.html` contains the `runHealth` placeholder and bumps the app script version for cache busting.

Existing full test and syntax checks remain required:

```bash
python3 -m unittest discover -s tests
node --check site/app.js
node --check site/feedback.js
node --check site/profile.js
git diff --check
```

## Rollout

The change is static and backward-compatible. After merging, manually trigger the `Daily Paper Recommender` workflow so GitHub Pages publishes the updated sidebar.

