# Inline Feedback And Favorites Archive Design

## Scope

This change keeps recommendation feedback on the main page and adds an automated public archive for liked papers.

The target archive repository is `ForeverHYX/daily-recommender-paper-favorites`. It is public. The user-facing name is "daily recommender paper favorites"; the GitHub repository slug uses hyphens because repository names should not depend on spaces.

## Main Page Feedback

Recommendation cards replace the current `feedback.html` navigation links with in-page buttons. Clicking a button records the same feedback event shape currently used by `feedback.js`: paper id, rating, source, section, title, abstract, authors, affiliations, categories, and timestamp.

When Supabase public config is available, the page posts directly to `feedback_events` with the anon key. When Supabase is not configured or the request fails, the event is stored in the existing `recommender_local_feedback_events` localStorage queue. No API keys or service-role keys are exposed in the browser.

After a successful or locally queued click:

- `like` marks the card as liked for the current `run_date` and shows a star in the card's upper-right corner.
- `dislike` hides the card from today's rendered recommendations immediately and persists that hide decision for the current `run_date`.
- A small in-page toast reports whether the feedback was recorded remotely or saved locally.

The daily JSON remains unchanged. Local liked/hidden state is purely a display overlay on top of today's recommendations.

## Favorites Archive

A new Python module exports liked papers from Supabase feedback into a filesystem archive. It reads `feedback_events`, keeps `rating=like`, groups by feedback month and the paper's primary section/category label, and downloads arXiv PDFs when an arXiv id is available.

Archive layout:

```text
YYYY-MM/
  <section-label-slug>/
    <paper-id-slug>.pdf
    <paper-id-slug>.json
```

The JSON sidecar stores title, abstract, authors, affiliations, categories, source paper id, arXiv URL/PDF URL, rating date, and section. Existing files are kept unless metadata changes.

## GitHub Workflow

The daily workflow gets an optional step after recommendation history publishing. It runs only when all of these are configured:

- `HAS_SUPABASE=true`
- `vars.LIKED_PAPERS_REPO` is set, expected value `ForeverHYX/daily-recommender-paper-favorites`
- `secrets.LIKED_PAPERS_REPO_TOKEN` is set

The step checks out the archive repository into a sibling directory, runs the exporter, commits archive changes if any, and pushes to the archive repository. The token is used only by git/GitHub operations and is never printed.

The archive repository will be created as public with `gh repo create ForeverHYX/daily-recommender-paper-favorites --public` if it does not already exist.

## Error Handling

Inline feedback failures never navigate away from the page. They either store a local fallback event or show a concise failure toast when neither remote nor local storage can be used.

Archive export treats PDF download failure as non-fatal for the rest of the batch: it writes metadata with the download error and continues. Supabase authentication or GitHub push failures fail the workflow step because the archive would otherwise silently drift.

## Testing

Front-end contract tests cover:

- Feedback buttons no longer link to `feedback.html`.
- A liked paper displays a star and persists liked state by `run_date`.
- A disliked paper is removed from today's rendered list and persists hidden state by `run_date`.
- Feedback events still include learning metadata.

Python tests cover:

- Liked feedback records become archive entries grouped by month and section.
- PDF download URLs are derived from arXiv paper ids.
- Metadata sidecars are written without secrets.

Workflow contract tests cover the optional archive step and its required env guards.
