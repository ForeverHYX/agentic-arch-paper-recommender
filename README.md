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
  --max-results 200
```

Build recommendations from JSONL:

```bash
python3 -m paper_recommender.pipeline \
  --input output/papers.jsonl \
  --profile config/interests.json \
  --feedback examples/sample_feedback.json \
  --output site/recommendations.json
```

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
