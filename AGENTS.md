# Repository guidance

- Keep API credentials in GitHub Secrets or a local secret manager. Never commit keys, print them, or place them in `site/` output.
- The daily recommendation workflow is `.github/workflows/daily.yml`; validate workflow changes with `python3 -m unittest discover -s tests`.
- Use `python3` for local commands. The workflow uses Python 3.12.
- LLM configuration is provided through `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL`; preserve the local fallback when the key is absent.
- When changing recommendation payload fields, update the renderer in `site/app.js`, styles in `site/styles.css`, and the relevant contract tests.
- Before pushing, run the full test suite and scan tracked files for secret-shaped values.
- Every local experiment or background job (long-running processes, Docker containers, bulk downloads) must declare a wall-time budget before it starts; the default cap is 2 hours on this machine. Workloads that cannot finish within the cap must run in CI instead (e.g., the Accel-Sim smoke matrix takes ~25 min on GitHub Actions x86_64 vs 1–2 days under Rosetta).
- Anything left running after a session ends must be registered in its experiment directory: what is running, the exact stop command, and the expected end time. When the budget expires (or the user stops it), stop the job and append a termination note — never leave unattended jobs running past their budget.
