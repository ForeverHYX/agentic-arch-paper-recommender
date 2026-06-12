# Supabase Setup

This project works without Supabase, but feedback stays `local only` until Supabase is configured. Use this checklist to turn like/dislike clicks into persistent feedback that future `Daily Paper Recommender` runs can read.

## 1. Create The Supabase Project

Create a Supabase project from the Supabase dashboard. In the SQL editor, run:

```sql
-- paste the full contents of supabase/schema.sql
```

The schema file is [supabase/schema.sql](../supabase/schema.sql). It creates:

- `feedback_events`: browser and email like/dislike events
- `recommendation_runs`: shown-paper history for repeat penalties
- `profile_state`: future profile state storage
- RLS policies that let the public anon key insert feedback but not read, update, or delete private rows

## 2. Collect Project Settings

From the Supabase project settings, collect:

- `SUPABASE_URL`: project API URL, for example `https://<project-ref>.supabase.co`
- `SUPABASE_ANON_KEY`: public anon key used by GitHub Pages for insert-only feedback
- `SUPABASE_SERVICE_ROLE_KEY`: private service role key used only by GitHub Actions

The anon key is public by design. The service role key bypasses RLS and must stay private.

## 3. Configure GitHub

Run these commands from the repository root. Replace the placeholder values with the Supabase values from step 2.

```bash
gh variable set SUPABASE_URL --body "https://<project-ref>.supabase.co" --repo ForeverHYX/agentic-arch-paper-recommender
gh variable set SUPABASE_ANON_KEY --body "<supabase-anon-key>" --repo ForeverHYX/agentic-arch-paper-recommender
gh secret set SUPABASE_SERVICE_ROLE_KEY --body "<supabase-service-role-key>" --repo ForeverHYX/agentic-arch-paper-recommender
```

Do not put the service role key in `site/config.js`, README files, issue comments, or any public GitHub Variable.

## 4. Re-run The Daily Workflow

Trigger the workflow:

```bash
gh workflow run "Daily Paper Recommender" --repo ForeverHYX/agentic-arch-paper-recommender --ref main
gh run list --repo ForeverHYX/agentic-arch-paper-recommender --workflow "Daily Paper Recommender" --limit 1
```

Watch the returned run id:

```bash
gh run watch <run-id> --repo ForeverHYX/agentic-arch-paper-recommender --exit-status
```

## 5. Verify Pages

After deployment, open the Pages reader. In the sidebar:

- `Run Health` should show `Supabase active` instead of `local only`.
- `Learning` should stop saying `not persistent yet` after persisted feedback exists.
- `Systems` should show Supabase `on`.

You can also check the public status JSON:

```bash
curl -fsSL "https://foreverhyx.github.io/agentic-arch-paper-recommender/status.json?ts=$(date +%s)"
```

Expected status after setup:

```json
{
  "supabase": {
    "configured": true
  }
}
```

## 6. Verify Feedback Writes

Click Like or Dislike on one paper from the Pages site. Then check Supabase Table Editor for a new row in `feedback_events`.

On the next workflow run, GitHub Actions reads those rows with `SUPABASE_SERVICE_ROLE_KEY`. The recommendation pipeline converts the persisted events into section, keyword, author, affiliation, and toolchain weights.

## Fallback Without Supabase

If Supabase is still unavailable, the feedback page keeps clicks in browser localStorage and can export `recommender-local-feedback.json`. Put that JSON into the GitHub Secret `LOCAL_FEEDBACK_JSON` to manually feed it into the next run. This is useful as a bridge, but it is not as reliable as Supabase because it depends on one browser and manual secret updates.

