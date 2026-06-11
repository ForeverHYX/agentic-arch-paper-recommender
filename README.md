# Daily arXiv Recommender

Configurable daily arXiv recommender with GitHub Pages publishing, email digests, and feedback hooks.

The target deployment model is serverless:

- GitHub Actions runs the daily pipeline.
- GitHub Pages hosts the static reading interface.
- Supabase stores feedback events.
- Email delivery is handled from GitHub Actions through SMTP.

The current repository starts with a self-contained MVP while upstream `daily-arXiv-ai-enhanced` integration is pending network availability.

## Interest Profile

The active keyword/category profile lives in:

`config/interests.json`

Edit that file to change the recommender's domain without touching Python code. The initial profile is seeded for agentic computer architecture, full-stack hardware/software co-design, CPU/GPU microarchitecture, simulators, and HPC cross-over work.

The profile controls:

- arXiv core categories
- arXiv expansion categories
- recommendation sections and display labels
- weighted keywords
- negative/noise rules
- recovery terms for ambiguous topics

## Development

Run tests:

```bash
python3 -m unittest discover -s tests
```

Fetch recent arXiv records from the categories in `config/interests.json`:

```bash
python3 -m paper_recommender.arxiv_source \
  --profile config/interests.json \
  --output output/papers.jsonl \
  --max-results 500
```

Build recommendations from JSONL:

```bash
python3 -m paper_recommender.pipeline \
  --input output/papers.jsonl \
  --profile config/interests.json \
  --feedback examples/sample_feedback.json \
  --history examples/sample_history.json \
  --output site/recommendations.json \
  --limit 15 \
  --min-count 15
```

Add TLDR summaries:

```bash
OPENAI_API_KEY=... python3 -m paper_recommender.summarizer \
  --input site/recommendations.json \
  --output site/recommendations.json
```

The default OpenAI-compatible endpoint is OpenCode Go: `https://opencode.ai/zen/go/v1`, using model `deepseek-v4-flash`. If the API key is missing or a request fails, the summarizer falls back to a local title/abstract TLDR so the daily workflow still completes.

`--min-count` fills with exploratory papers. Core arXiv categories are preferred first; if there still are not enough candidates, clean expansion-category papers without negative/noise matches are added as exploratory items.

## Feedback Storage

Run [supabase/schema.sql](supabase/schema.sql) in your Supabase SQL editor, then configure:

- GitHub Variables: `SUPABASE_URL`, `SUPABASE_ANON_KEY`
- GitHub Secrets: `SUPABASE_SERVICE_ROLE_KEY`

The public Pages app uses the anon key only to insert feedback. GitHub Actions uses the service role key to read feedback and adjust section weights.

Feedback records include paper metadata when available:

- `title`
- `abstract`
- `authors`
- `categories`

The daily pipeline converts likes and dislikes into two lightweight learning signals:

- section weights, so preferred recommendation sections rank higher
- keyword weights from liked/disliked paper text, so similar future papers move up or down without requiring an embedding service

## Recommendation History

When Supabase is configured, GitHub Actions also stores rows in `recommendation_runs`.
The next daily run reads those rows and applies a repeat penalty to papers that have already been shown, reducing duplicate recommendations over time.

Local commands:

```bash
python3 -m paper_recommender.history fetch --output output/history.json --limit 1000
python3 -m paper_recommender.history publish --recommendations site/recommendations.json
```

## Email Delivery

The email step is optional and runs only when SMTP secrets are configured. By default, empty recommendation days are skipped instead of sending a low-value digest. SMTP delivery retries three times in GitHub Actions.

Local command:

```bash
python3 -m paper_recommender.email_delivery \
  --recommendations site/recommendations.json \
  --max-attempts 3
```

Use `--send-empty` only if you explicitly want an email even when there are no matching papers.
