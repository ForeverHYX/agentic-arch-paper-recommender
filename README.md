# Daily arXiv Recommender

Configurable daily arXiv recommender with GitHub Pages publishing, email digests, and feedback hooks.

The target deployment model is serverless:

- GitHub Actions runs the daily pipeline.
- GitHub Pages hosts the static reading interface.
- Supabase stores feedback events.
- Email delivery is handled from GitHub Actions through SMTP.

This repository is self-contained, with selected design cues from `daily-arXiv-ai-enhanced` and `zotero-arxiv-daily`: GitHub Actions scheduling, GitHub Pages reading, optional email delivery, LLM summaries, affiliation/code links, and a no-server personalization loop.

## Interest Profile

The active keyword/category profile lives in:

`config/interests.json`

Edit that file to change the recommender's domain without touching Python code. The initial profile is seeded for agentic computer architecture, full-stack hardware/software co-design, CPU/GPU microarchitecture, simulators, and HPC cross-over work.

The profile controls:

- arXiv core categories
- arXiv expansion categories
- representative seed papers used as interest anchors for the LLM judge
- recommendation sections and display labels
- weighted keywords
- negative/noise rules
- recovery terms for ambiguous topics

`seed_papers` is the closest no-server equivalent to a small Zotero library. Add papers that represent what you want more of, with short notes and keywords. The daily workflow serializes those seeds into `recommendations.json`, and the LLM judge reads them when deciding whether a candidate is genuinely close to the profile.

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
  --limit 45 \
  --min-count 45
```

Rerank candidates with an OpenAI-compatible model and keep at most 15 final recommendations:

```bash
OPENAI_API_KEY=... python3 -m paper_recommender.judge \
  --input site/recommendations.json \
  --output site/recommendations.json \
  --limit 15
```

Enrich author affiliations from arXiv source TeX when available:

```bash
python3 -m paper_recommender.affiliations \
  --input site/recommendations.json \
  --output site/recommendations.json \
  --max-items 15
```

Add TLDR summaries:

```bash
OPENAI_API_KEY=... python3 -m paper_recommender.summarizer \
  --input site/recommendations.json \
  --output site/recommendations.json
```

The default OpenAI-compatible endpoint is OpenCode Go: `https://opencode.ai/zen/go/v1`, using model `deepseek-v4-flash`. The judge uses the model to add `ai_judgement` and `ai_score`, rerank candidates by AI relevance, and truncate the final digest to 15 papers. If the API key is missing or a request fails, the judge falls back to the rule score and the summarizer falls back to a local title/abstract TLDR so the daily workflow still completes.

`--min-count` fills with exploratory papers. Core arXiv categories are preferred first; if there still are not enough candidates, clean expansion-category papers without negative/noise matches are added as exploratory items.

Each recommendation includes author affiliations when the source provides them, direct `Paper`, `PDF`, explicit `Code` links when found, and a `Code Search` GitHub repository search URL based on the paper title. arXiv Atom often omits affiliations, so the workflow also tries to download the final papers' arXiv source bundles and parse common LaTeX affiliation macros. Missing affiliations are stored as an empty list rather than guessed.

The GitHub Pages reader includes local controls for search, section filtering, minimum AI score, explicit code repository availability, affiliation availability, and rank/AI/rule/title sorting. These controls run entirely in the browser against `recommendations.json`.

## LLM Provider Configuration

GitHub Actions reads the OpenAI-compatible provider configuration from:

- GitHub Secret: `OPENAI_API_KEY`
- GitHub Variable: `OPENAI_BASE_URL`, optional, defaults to `https://opencode.ai/zen/go/v1`
- GitHub Variable: `OPENAI_MODEL`, optional, defaults to `deepseek-v4-flash`

OpenCode documents OpenCode Go API keys under its provider docs and documents custom OpenAI-compatible providers with a configurable `baseURL`. This repository keeps the same shape at the workflow level: the API key stays secret, while base URL and model can be changed without code edits.

The daily pipeline uses the LLM twice:

- `paper_recommender.judge`: applies the fixed interest profile, representative seed papers, and learned like/dislike feedback when scoring candidates.
- `paper_recommender.summarizer`: generates concise Chinese TLDRs for the final papers.

## Feedback Storage

Run [supabase/schema.sql](supabase/schema.sql) in your Supabase SQL editor, then configure:

- GitHub Variables: `SUPABASE_URL`, `SUPABASE_ANON_KEY`
- GitHub Secrets: `SUPABASE_SERVICE_ROLE_KEY`

The public Pages app uses the anon key only to insert feedback. GitHub Actions uses the service role key to read feedback and adjust the learned profile.

Feedback records include paper metadata when available:

- `title`
- `abstract`
- `authors`
- `affiliations`
- `categories`

The daily pipeline converts likes and dislikes into lightweight learning signals:

- section weights, so preferred recommendation sections rank higher
- keyword weights from liked/disliked paper text, so similar future papers move up or down without requiring an embedding service
- author weights, so papers from repeatedly liked/disliked authors move accordingly
- affiliation weights, used as a weak signal because arXiv affiliation data is incomplete
- toolchain weights for architecture/HPC tooling such as `gem5`, `MLIR`, `CIRCT`, `Accel-Sim`, `GPGPU-Sim`, `Ramulator`, `CUDA`, `ROCm`, `SYCL`, `OpenMP`, and `MPI`

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
