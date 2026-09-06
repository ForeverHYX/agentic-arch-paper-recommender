# Repository guidance

- Keep API credentials in GitHub Secrets or a local secret manager. Never commit keys, print them, or place them in `site/` output.
- The daily recommendation workflow is `.github/workflows/daily.yml`; validate workflow changes with `python3 -m unittest discover -s tests`.
- Use `python3` for local commands. The workflow uses Python 3.12.
- LLM configuration is provided through `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL`; preserve the local fallback when the key is absent.
- When changing recommendation payload fields, update the renderer in `site/app.js`, styles in `site/styles.css`, and the relevant contract tests.
- Before pushing, run the full test suite and scan tracked files for secret-shaped values.
