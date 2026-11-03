# Repository guidance

- Keep API credentials in GitHub Secrets or a local secret manager. Never commit keys, print them, or place them in `site/` output.
- The daily recommendation workflow is `.github/workflows/daily.yml`; validate workflow changes with `python3 -m unittest discover -s tests`.
- Use `python3` for local commands. The workflow uses Python 3.12.
- LLM configuration is provided through `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` (defaults: Zhipu GLM coding-plan endpoint `https://open.bigmodel.cn/api/coding/paas/v4` and `glm-5.3`; legacy `OPENAI_*`/`DEEPSEEK_*` names still work as fallbacks); preserve the local fallback when the key is absent.
- When changing recommendation payload fields, update the renderer in `site/app.js`, styles in `site/styles.css`, and the relevant contract tests.
- Before pushing, run the full test suite and scan tracked files for secret-shaped values.
