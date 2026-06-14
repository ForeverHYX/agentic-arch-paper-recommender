# Exploration Recommendations and Profile Review Design

## Goal

Add a daily exploration block with up to 5 extra papers that are popular or promising in computer architecture-adjacent AI/ML systems, while keeping the existing interest-profile recommendations stable. Use LLM review to summarize feedback-driven profile adjustments, but do not let the workflow automatically rewrite the canonical profile.

## Scope

- Keep the existing core recommendation path capped at 15 LLM-selected papers.
- Add an additional `exploration` section with up to 5 papers outside the core cap.
- Prefer exploration papers that are related to computer architecture through AI/ML systems, accelerators, hardware-aware ML, ML compilers, GPU systems, runtime systems, performance modeling, or systems for ML.
- Let likes and dislikes on exploration papers enter the same feedback stream as other recommendations.
- Generate a constrained daily profile review overlay from the LLM, based on current profile, feedback summary, and the final recommendation payload.
- Surface the profile review in the generated site so the user can inspect what the system learned.

## Non-Goals

- Do not automatically commit changes to `config/interests.json`.
- Do not use LLM output to silently bypass API failures or schema errors.
- Do not switch away from `deepseek-v4-flash` unless the user explicitly approves.
- Do not create a separate feedback table for exploration; reuse the existing feedback event shape.

## Recommended Architecture

The canonical profile remains `config/interests.json`, plus any explicit workflow override provided through `PROFILE_OVERRIDE_JSON`. A new LLM-reviewed overlay is generated as deployable data, not as source configuration. This keeps the base profile stable while allowing daily feedback to influence ranking and explanations.

The pipeline should split recommendations into two logical tracks:

1. Core track: existing profile-matched candidates, LLM judged and capped at 15.
2. Exploration track: AI/ML architecture-adjacent candidates, selected separately and capped at 5.

Both tracks share the same paper schema and feedback path. Exploration papers should use `sections: ["exploration"]`, and `section_labels` should include a Chinese label such as `Exploration / AI+体系结构探索`.

## Data Flow

1. arXiv fetch includes enough categories to see AI/ML systems candidates, using current core and expansion categories.
2. Rule scoring builds a high-recall candidate pool.
3. Exploration candidate selection identifies candidates that are not already accepted as core papers, are in AI/ML categories or architecture categories, and contain architecture-adjacent AI/ML keywords.
4. Feedback and history penalties are applied to exploration candidates using the existing feedback weighting helpers.
5. LLM judgement receives both core and exploration candidates, but final selection preserves quotas: up to 15 core and up to 5 exploration.
6. TLDR enrichment runs for the final combined list.
7. Profile review runs after final recommendations and writes a structured review into `site/profile_review.json` and the recommendation payload.

## Profile Review Overlay

The profile review should be a JSON object with these fields:

- `model`: model used for review.
- `generated_at`: UTC timestamp.
- `summary_zh`: concise Chinese summary of feedback and profile movement.
- `positive_adjustments`: array of short Chinese suggestions for topics to strengthen.
- `negative_adjustments`: array of short Chinese suggestions for topics to downweight.
- `exploration_notes`: array of short Chinese observations about exploration feedback.
- `risk_notes`: array of short Chinese warnings about potential drift or insufficient evidence.
- `apply_to_runtime`: boolean. It must remain `false` for now, documenting that this is a reviewed overlay, not an automatic source-profile edit.

If the API is configured and the profile review call fails, the workflow should stop instead of producing a fake review. If the API is not configured, the system may omit the review only when not running in require-API mode.

## Frontend Behavior

The recommendation page should show the exploration section alongside other sections, with a clear Chinese label. Existing filters should work. Like/dislike behavior remains inline:

- Like keeps the card visible and shows the star.
- Dislike removes the card from today's list.
- Feedback event metadata includes section `exploration`, letting the existing feedback learner adjust future ranking.

The profile page should show the profile review summary if available, below the core rules summary and above the raw JSON editor.

## Testing

Tests should cover:

- Exploration selection adds up to 5 extra recommendations without reducing the core quota.
- Exploration papers use the `exploration` section and Chinese section label.
- LLM judgement preserves separate core and exploration caps.
- Feedback on exploration contributes to section and keyword weights through the existing feedback path.
- Profile review parser accepts valid JSON, rejects malformed output in require-API mode, and never leaks API keys in error messages.
- Workflow contract includes profile review generation and publishes the resulting JSON.
- Frontend contract includes exploration label and profile review rendering hooks.

## Rollout

Implement in small commits:

1. Add exploration candidate selection and quota tests.
2. Add LLM judgement quota handling.
3. Add profile review generation and workflow wiring.
4. Add frontend profile review display.
5. Run local verification, scan for secrets, commit, push, trigger workflow, and inspect online output.
