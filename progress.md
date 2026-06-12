# 进度日志

## 会话：2026-06-12

### 阶段 1：方案确认与项目初始化
- **状态：** in_progress
- **开始时间：** 2026-06-12 Asia/Shanghai
- 执行的操作：
  - 根据用户确认的方向创建项目规划目录；后续用户决定继续使用原仓库名。
  - 生成 `task_plan.md`、`findings.md`、`progress.md` 三个规划文件。
  - 将无服务器约束、GitHub Pages、邮件推送、Supabase 反馈和领域画像写入初版计划。
  - 核对目录和文件存在性，确认初版计划已落盘。
- 创建/修改的文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

## 会话补充：推荐数量收敛
- **状态：** complete
- 执行的操作：
  - 用户反馈 60 条过多，要求不超过 15 条。
  - 保留 arXiv 候选抓取 500 条，但 workflow 输出改为 `--limit 15 --min-count 15`。
  - 更新 workflow 契约测试、README 和发现记录。
- 创建/修改的文件：
  - `.github/workflows/daily.yml`
  - `tests/test_workflow_contract.py`
  - `README.md`
  - `findings.md`
  - `progress.md`

## 会话补充：AI 判断打分与 Code Search
- **状态：** in_progress
- 执行的操作：
  - 用户要求 GitHub Pages 也展示 AI 总结、Paper/Code 链接，并让推荐打分本身引入大模型判断。
  - 增加 `paper_recommender.judge`，使用 OpenAI-compatible `/chat/completions` 为候选论文生成 `ai_judgement.score/reason/decision`，再按 AI 分数重排并截断。
  - 每日 workflow 改为规则 pipeline 先产出 45 条候选，LLM judge 再保留最多 15 条，之后生成 TLDR、发送邮件并部署 Pages。
  - `Paper` 和推荐 JSON 增加 `code_search_url`，没有显式代码仓库时也能给出 GitHub repository search 入口。
  - Pages 和邮件展示 `AI 总结`、`AI 判断`、作者单位、Paper/PDF/Code/Code Search。
  - 解析 arXiv `arxiv:affiliation` 和外部记录中的 `affiliations`，并把单位写入反馈元数据和 Supabase schema。
- 创建/修改的文件：
  - `paper_recommender/judge.py`
  - `paper_recommender/domain.py`
  - `paper_recommender/pipeline.py`
  - `paper_recommender/emailer.py`
  - `paper_recommender/feedback.py`
  - `paper_recommender/arxiv_source.py`
  - `site/app.js`
  - `site/styles.css`
  - `site/feedback.js`
  - `supabase/schema.sql`
  - `.github/workflows/daily.yml`
  - `tests/test_judge.py`
  - `tests/test_pipeline.py`
  - `tests/test_emailer.py`
  - `tests/test_site_contract.py`
  - `tests/test_workflow_contract.py`
  - `tests/test_arxiv_source.py`
  - `tests/test_feedback.py`
  - `tests/test_feedback_page_contract.py`
  - `tests/test_supabase_schema.py`

### 阶段 2：上游项目审计与改造范围确认
- **状态：** in_progress
- **开始时间：** 2026-06-12 Asia/Shanghai
- 执行的操作：
  - 尝试通过 `git clone` 拉取 `dw-dengwei/daily-arXiv-ai-enhanced` 到临时目录。
  - 尝试通过 GitHub zip archive 下载主分支快照。
  - 两种方式均因连接 `github.com:443` 超时失败；为避免重复失败，转为先开发本项目自有 MVP，后续网络可用时再接入上游。
- 创建/修改的文件：
  - `progress.md`

## 测试结果
| 测试 | 输入 | 预期结果 | 实际结果 | 状态 |
|------|------|---------|---------|------|
| 规划目录创建 | `agentic-arch-paper-recommender` | 目录存在 | 当前使用原远程仓库名；本地目录已恢复原名 | pass |
| 规划文件创建 | 三个 Markdown 文件 | 文件存在且包含初版计划 | `task_plan.md`、`findings.md`、`progress.md` 均已创建 | pass |
| 上游代码获取 | `git clone` / GitHub zip archive | 成功下载上游代码 | 连接 `github.com:443` 超时 | blocked-for-now |
| 推荐内核测试 | `python3 -m unittest discover -s tests` | 测试通过 | 15 个测试通过 | pass |
| 推荐 JSON 生成 | `python3 -m paper_recommender.pipeline --input examples/sample_papers.jsonl --profile config/interests.json --output site/recommendations.json --run-date 2026-06-12 --limit 25` | 生成推荐 JSON | 写入 2 条推荐 | pass |
| Supabase schema 测试 | `python3 -m unittest tests.test_supabase_schema` | 测试通过 | schema 契约测试通过 | pass |
| 反馈读取与排序测试 | `python3 -m unittest discover -s tests` | 测试通过 | 20 个测试通过 | pass |
| 带反馈生成推荐 JSON | `python3 -m paper_recommender.pipeline --input examples/sample_papers.jsonl --profile config/interests.json --feedback examples/sample_feedback.json --output site/recommendations.json --run-date 2026-06-12 --limit 25` | 生成带 feedback summary 的推荐 JSON | 写入 2 条推荐，包含 `agentic_architecture: 1.0` 权重 | pass |
| arXiv source RED 测试 | `python3 -m unittest tests.test_arxiv_source` | 新模块不存在时失败 | `ModuleNotFoundError: No module named 'paper_recommender.arxiv_source'` | expected-fail |
| arXiv source 单元测试 | `python3 -m unittest tests.test_arxiv_source` | 测试通过 | 3 个测试通过，覆盖 URL、Atom 解析、CLI 写 JSONL | pass |
| workflow 契约 RED 测试 | `python3 -m unittest tests.test_workflow_contract` | workflow 未接入 arXiv 时失败 | 断言缺少 `python -m paper_recommender.arxiv_source` | expected-fail |
| arXiv + workflow 局部测试 | `python3 -m unittest tests.test_arxiv_source tests.test_workflow_contract` | 测试通过 | 4 个测试通过 | pass |
| 全量测试 | `python3 -m unittest discover -s tests` | 测试通过 | 24 个测试通过 | pass |
| 反馈元数据 RED 测试 | `python3 -m unittest tests.test_feedback` | 缺少反馈元数据字段时失败 | `FeedbackEvent` 缺少 `title` 等字段 | expected-fail |
| 反馈页面契约 RED 测试 | `python3 -m unittest tests.test_feedback_page_contract` | 页面未提交论文元数据时失败 | 断言缺少 `fetch("recommendations.json"` | expected-fail |
| 反馈关键词学习 RED 测试 | `python3 -m unittest tests.test_feedback tests.test_feedback_pipeline` | 缺少文本反馈权重时失败 | 缺少 `text_feedback_weights` / `keyword_weights` | expected-fail |
| 反馈学习局部测试 | `python3 -m unittest tests.test_feedback tests.test_feedback_pipeline` | 测试通过 | 8 个测试通过 | pass |
| 反馈学习推荐生成 | `python3 -m paper_recommender.pipeline --input examples/sample_papers.jsonl --profile config/interests.json --feedback examples/sample_feedback.json --output /tmp/recommender-sample.json --run-date 2026-06-12 --limit 25` | 生成推荐 JSON 并包含关键词权重 | 写入 2 条推荐，`keyword_weights` 包含 `gem5/cache/search` 等干净 token | pass |
| 反馈学习全量测试 | `python3 -m unittest discover -s tests` | 测试通过 | 29 个测试通过 | pass |
| 推荐历史 RED 测试 | `python3 -m unittest tests.test_history tests.test_feedback_pipeline` | 缺少 history 模块时失败 | `ModuleNotFoundError: No module named 'paper_recommender.history'` | expected-fail |
| 推荐历史局部测试 | `python3 -m unittest tests.test_history tests.test_feedback_pipeline` | 测试通过 | 8 个测试通过 | pass |
| 推荐历史 workflow RED 测试 | `python3 -m unittest tests.test_workflow_contract` | workflow 未接历史时失败 | 断言缺少 `output/history.json` 初始化和 history fetch/publish | expected-fail |
| 推荐历史 workflow 契约测试 | `python3 -m unittest tests.test_workflow_contract` | 测试通过 | 2 个测试通过 | pass |
| 带历史生成推荐 JSON | `python3 -m paper_recommender.pipeline --input examples/sample_papers.jsonl --profile config/interests.json --feedback examples/sample_feedback.json --history examples/sample_history.json --output /tmp/recommender-history-sample.json --run-date 2026-06-12 --limit 25` | 生成推荐 JSON 并包含历史摘要 | 写入 2 条推荐，`history_summary.shown_counts.agentic-sample = 1` | pass |
| 推荐历史全量测试 | `python3 -m unittest discover -s tests` | 测试通过 | 36 个测试通过 | pass |
| 邮件重试 RED 测试 | `python3 -m unittest tests.test_email_delivery` | 缺少重试和空推荐跳过函数时失败 | import 缺少 `send_email_message_with_retries` | expected-fail |
| 邮件语法回归 | `python3 -m unittest tests.test_email_delivery` | 测试通过 | 首次实现把 SMTP `else` 分支放错位置导致 SyntaxError，修正后 4 个测试通过 | pass |
| 邮件 workflow RED 测试 | `python3 -m unittest tests.test_workflow_contract` | workflow 未传重试参数时失败 | 断言缺少 `--max-attempts 3` | expected-fail |
| 邮件 workflow 契约测试 | `python3 -m unittest tests.test_workflow_contract` | 测试通过 | 3 个测试通过 | pass |
| 邮件可靠性全量测试 | `python3 -m unittest discover -s tests` | 测试通过 | 40 个测试通过 | pass |
| TLDR/link/UI RED 测试 | `python3 -m unittest tests.test_pipeline tests.test_emailer tests.test_site_contract tests.test_summarizer` | 缺少链接字段、summarizer 和 UI hook 时失败 | `Paper` 缺少 `url`，缺少 `paper_recommender.summarizer`，页面未渲染 TLDR/链接 | expected-fail |
| TLDR/link/UI 局部测试 | `python3 -m unittest tests.test_workflow_contract tests.test_pipeline tests.test_emailer tests.test_site_contract tests.test_summarizer` | 测试通过 | 18 个测试通过 | pass |
| TLDR/link/UI 全量测试 | `python3 -m unittest discover -s tests` | 测试通过 | 49 个测试通过 | pass |
| TLDR/link/UI workflow 实测 | `gh workflow run "Daily Paper Recommender"` | 完整 workflow 成功，邮件和 Pages 正常 | 抓取 500 条 arXiv，生成 39 条推荐，39 条均 enrich TLDR，邮件发送成功 | pass |
| exploratory 扩展补足 RED 测试 | `python3 -m unittest tests.test_pipeline` | 核心不足时可用干净扩展分类补足 | 初始只返回核心推荐，缺少 clean expansion exploratory | expected-fail |
| exploratory 扩展补足测试 | `python3 -m unittest tests.test_pipeline` | 测试通过 | 7 个测试通过 | pass |
| exploratory 扩展补足全量测试 | `python3 -m unittest discover -s tests` | 测试通过 | 50 个测试通过 | pass |
| AI judge/code search RED 测试 | `python3 -m unittest tests.test_judge tests.test_pipeline tests.test_site_contract tests.test_emailer tests.test_workflow_contract` | 缺少 judge 模块、AI 判断展示和 Code Search 时失败 | `paper_recommender.judge` 不存在，`Paper` 缺少 `code_search_url`，Pages/邮件/workflow 契约失败 | expected-fail |
| AI judge/code search 局部测试 | `python3 -m unittest tests.test_judge tests.test_pipeline tests.test_site_contract tests.test_emailer tests.test_workflow_contract` | 测试通过 | 21 个测试通过 | pass |
| 本地 fallback 链路 smoke test | pipeline 45候选 → judge 15 → summarizer | 输出包含 `ai_judgement`、`ai_score`、`tldr`、`code_search_url` | 示例数据写入 2 条，字段完整；无 API key 时使用规则分兜底 | pass |
| 作者单位局部测试 | `python3 -m unittest tests.test_arxiv_source tests.test_pipeline tests.test_judge tests.test_site_contract tests.test_emailer tests.test_feedback tests.test_feedback_page_contract tests.test_supabase_schema` | 单位被解析、展示、存储并传入 judge | 27 个测试通过 | pass |

## 会话补充：前端未显示作者单位的根因修复
- **状态：** in_progress
- 执行的操作：
  - 检查 live `recommendations.json`，确认前端没有显示单位不是 CSS 问题，而是 8 条推荐的 `affiliations` 全为空数组。
  - 验证 OpenAlex/Semantic Scholar 对当前新 arXiv 标题匹配不稳定，不能直接用第一条结果补单位。
  - 验证 arXiv source bundle 对至少一篇当前推荐包含 `\\affil` 单位信息。
  - 新增 `paper_recommender.affiliations`，下载最终推荐的 arXiv e-print source，解析 TeX 中 `\\affil`、`\\affiliation`、`\\institute` 宏，并写回 `recommendations.json`。
  - workflow 在 LLM judge 后、TLDR 前运行单位补全。
- 创建/修改的文件：
  - `paper_recommender/affiliations.py`
  - `tests/test_affiliations.py`
  - `.github/workflows/daily.yml`
  - `tests/test_workflow_contract.py`
  - `README.md`
  - `findings.md`
  - `progress.md`

| 作者单位补全 RED 测试 | `python3 -m unittest tests.test_affiliations tests.test_workflow_contract` | 缺少 affiliations 模块和 workflow 步骤时失败 | `ModuleNotFoundError`，workflow 缺少 `paper_recommender.affiliations` | expected-fail |
| 作者单位补全局部测试 | `python3 -m unittest tests.test_affiliations tests.test_workflow_contract` | 测试通过 | 10 个测试通过 | pass |
| 作者单位补全全量测试 | `python3 -m unittest discover -s tests` | 测试通过 | 63 个测试通过 | pass |
| 真实 arXiv source smoke test | `curl https://arxiv.org/e-print/2606.11356` 后调用 parser | 能抽取 FESOM2 论文单位 | 抽取出 Alfred Wegener Institute 和 University of Bremen | pass |

## 会话补充：LLM 使用反馈画像和 provider 可配置化
- **状态：** in_progress
- 执行的操作：
  - 检查当前项目与目标差距：已有 LLM TLDR、LLM judge、反馈存储，但 judge prompt 尚未显式纳入 feedback summary。
  - 增加 judge 测试，要求 OpenAI-compatible 请求中包含 learned feedback profile。
  - `paper_recommender.judge` 现在把 `feedback_summary.section_weights` 和 `feedback_summary.keyword_weights` 格式化为 prefer/avoid sections/keywords，传给 LLM 判断。
  - workflow 的 LLM 步骤支持 GitHub Variables `OPENAI_BASE_URL`、`OPENAI_MODEL` 覆盖，默认 OpenCode Go。
  - README 增加 LLM provider 配置说明。
- 创建/修改的文件：
  - `paper_recommender/judge.py`
  - `.github/workflows/daily.yml`
  - `tests/test_judge.py`
  - `tests/test_workflow_contract.py`
  - `README.md`
  - `findings.md`
  - `progress.md`

| LLM feedback prompt RED 测试 | `python3 -m unittest tests.test_judge` | request_judgement 支持 feedback_summary 并写入 prompt | 初始因未知参数失败 | expected-fail |
| LLM feedback prompt 局部测试 | `python3 -m unittest tests.test_workflow_contract tests.test_judge` | 测试通过 | 14 个测试通过 | pass |
| LLM feedback/provider 全量测试 | `python3 -m unittest discover -s tests` | 测试通过 | 66 个测试通过 | pass |

## 会话补充：GitHub Pages 阅读筛选增强
- **状态：** complete
- 执行的操作：
  - 参考 daily arXiv 类项目常见阅读体验，给 Pages 增加本地筛选和排序控件。
  - 支持搜索标题/摘要/TLDR/AI 判断/作者/单位/分类。
  - 支持按栏目、最低 AI 分、是否有显式 Code repo、是否有单位筛选。
  - 支持按原始 rank、AI 分、规则分、标题排序。
  - 所有控件只在浏览器本地处理 `recommendations.json`，不需要后端。
- 创建/修改的文件：
  - `site/index.html`
  - `site/app.js`
  - `site/styles.css`
  - `tests/test_site_contract.py`
  - `README.md`
  - `progress.md`

| Pages 筛选控件 RED 测试 | `python3 -m unittest tests.test_site_contract` | 页面和脚本包含搜索、筛选、排序 hook | 初始缺少 `searchInput` 等控件 | expected-fail |
| Pages 筛选控件局部测试 | `python3 -m unittest tests.test_site_contract` | 测试通过 | 2 个测试通过 | pass |
| Pages 筛选控件全量测试 | `python3 -m unittest discover -s tests` | 测试通过 | 66 个测试通过 | pass |
| 本地静态资源检查 | `node --check site/app.js` 和 `curl http://localhost:8765/` | JS 语法正确，控件存在，JSON 可读取 | 通过；`agent-browser` 因本机未安装 Chrome 未运行 | pass-with-note |

## 会话补充：seed papers 个人语料锚点
- **状态：** complete
- 执行的操作：
  - 增加 `SeedPaper` 数据结构，并让 `InterestProfile` 从 `config/interests.json` 读取 `seed_papers`。
  - 推荐 payload 增加 `profile_context.seed_papers`，便于调试和后续展示。
  - LLM judge prompt 增加 `Representative seed papers`，把代表性论文标题、备注和关键词作为个性化兴趣锚点。
  - 默认配置加入 AlphaZero Moment、ArchAgent、ArchExplorer、ASSASSYN 四类代表性 seed。
  - README、计划和发现记录补充 seed papers 的维护方式和作用。
- 创建/修改的文件：
  - `config/interests.json`
  - `paper_recommender/domain.py`
  - `paper_recommender/pipeline.py`
  - `paper_recommender/judge.py`
  - `tests/test_interest_profile.py`
  - `tests/test_pipeline.py`
  - `tests/test_judge.py`
  - `README.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

| seed papers RED 测试 | `python3 -m unittest tests.test_interest_profile tests.test_pipeline tests.test_judge` | 配置加载、payload 序列化、judge prompt 注入都应失败 | 缺少 `SeedPaper`、`InterestProfile.seed_papers`、`request_judgement(seed_papers=...)` | expected-fail |
| seed papers 局部测试 | `python3 -m unittest tests.test_interest_profile tests.test_pipeline tests.test_judge` | 测试通过 | 20 个测试通过 | pass |

## 错误日志
| 时间戳 | 错误 | 尝试次数 | 解决方案 |
|--------|------|---------|---------|
| 2026-06-12 | 暂无 | 0 | 暂无 |
| 2026-06-12 | 拉取上游项目失败：连接 `github.com:443` 超时 | 3 | 停止重复同类尝试，先开发自有 MVP；后续网络可用时再接入上游 |
| 2026-06-12 | 删除误创建的新 GitHub 仓库 `ForeverHYX/daily-arxiv-recommender` 被执行审批层拒绝 | 1 | 不绕过删除限制；保留当前原仓库开发状态，请用户在 GitHub Settings > Danger Zone 手动删除，或显式重新授权后再试 |
| 2026-06-12 | 示例输出中的关键词权重混入 `search.`、作者名和分类 token | 1 | 让关键词学习只使用 title/abstract，并在 tokenizer 中剥离句尾标点 |

## 会话补充：通用化命名与兴趣配置抽离
- **状态：** in_progress
- 执行的操作：
  - 用户要求将项目从特定的 agentic architecture 推荐器改成更通用的每日 arXiv 推荐器。
  - 增加 `config/interests.json`，把分类、栏目、关键词、降权规则和恢复词从代码中抽离。
  - 更新 pipeline，让推荐 JSON 包含 `profile_name` 和 `section_labels`。
  - 更新邮件渲染和 GitHub Pages 前端，栏目名从推荐 JSON 读取。
  - 曾更新 GitHub Actions 默认 Pages URL 为 `daily-arxiv-recommender`，后按用户要求改回原仓库 Pages URL。
  - 使用 TDD 增加配置化兴趣画像测试。
  - 本地文件夹曾从 `agentic-arch-paper-recommender` 更名为 `daily-arxiv-recommender`，现已恢复为原名。
  - GitHub 远程仓库曾创建目标名新仓库；用户要求去掉新仓库并继续使用原仓库。
- 创建/修改的文件：
  - `config/interests.json`
  - `paper_recommender/domain.py`
  - `paper_recommender/pipeline.py`
  - `paper_recommender/emailer.py`
  - `paper_recommender/email_delivery.py`
  - `tests/test_interest_profile.py`
  - `tests/test_pipeline.py`
  - `tests/test_emailer.py`
  - `README.md`
  - `site/*`
  - `.github/workflows/daily.yml`

## 会话补充：反馈存储 schema
- **状态：** complete
- 执行的操作：
  - 增加 Supabase SQL schema。
  - 定义 `feedback_events`、`recommendation_runs`、`profile_state`。
  - 为 `feedback_events` 启用 RLS，并允许匿名用户仅插入合法 like/dislike 反馈。
  - 禁止匿名读取反馈、推荐运行记录和画像状态。
  - 增加 schema 契约测试。
- 创建/修改的文件：
  - `supabase/schema.sql`
  - `tests/test_supabase_schema.py`

## 会话补充：反馈读取与推荐调整
- **状态：** complete
- 执行的操作：
  - 增加 `paper_recommender.feedback`，支持从 Supabase REST 读取反馈并写入 JSON。
  - 增加反馈 JSON 解析和 section 权重汇总。
  - pipeline 增加 `--feedback` 参数，并用 section feedback weights 调整推荐排序。
  - GitHub Actions 增加条件步骤：配置 `SUPABASE_URL` 和 `SUPABASE_SERVICE_ROLE_KEY` 后自动拉取反馈。
  - 页面和邮件反馈链接增加 `section` 参数，便于后续按栏目学习。
  - README 增加 Supabase 配置说明。
- 创建/修改的文件：
  - `paper_recommender/feedback.py`
  - `paper_recommender/pipeline.py`
  - `paper_recommender/emailer.py`
  - `tests/test_feedback.py`
  - `tests/test_feedback_pipeline.py`
  - `examples/sample_feedback.json`
  - `.github/workflows/daily.yml`
  - `README.md`
  - `site/app.js`
  - `site/feedback.js`

## 会话补充：真实 arXiv 数据源
- **状态：** complete
- 执行的操作：
  - 使用 TDD 增加 `tests/test_arxiv_source.py`，先验证缺少 `paper_recommender.arxiv_source` 的 RED 状态。
  - 增加 `paper_recommender.arxiv_source`，支持根据 `config/interests.json` 的 core/expansion 分类构造 arXiv Atom API 查询。
  - Atom XML 解析为 pipeline 兼容 JSONL 记录，包含 `paper_id`、`title`、`abstract`、`authors`、`categories`、`url`、`published`、`updated`。
  - CLI 支持真实抓取，也支持 `--source-file` 读取本地 Atom XML，便于无网络测试。
  - 增加 workflow 契约测试，确认每日流程使用 `output/papers.jsonl` 而非示例 JSONL。
  - 更新 GitHub Actions：先运行 arXiv 抓取，再运行推荐 pipeline。
  - 更新 README，记录真实 arXiv 抓取命令和新的推荐生成输入。
- 创建/修改的文件：
  - `paper_recommender/arxiv_source.py`
  - `tests/test_arxiv_source.py`
  - `tests/test_workflow_contract.py`
  - `.github/workflows/daily.yml`
  - `README.md`
  - `task_plan.md`
  - `progress.md`

## 会话补充：反馈关键词学习
- **状态：** complete
- 执行的操作：
  - 扩展 `FeedbackEvent`，保存 `title`、`abstract`、`authors`、`categories`，并让 Supabase 导出 JSON 保留这些字段。
  - 更新 `site/feedback.js`，提交反馈前从 `recommendations.json` 按 `paper_id` 补全论文元数据，避免把长摘要塞进邮件链接。
  - 增加轻量文本反馈权重：like 论文中的关键词给相似候选加分，dislike 论文中的关键词给相似候选降分。
  - pipeline 的 `feedback_summary` 增加 `keyword_weights`，便于观察画像学习效果。
  - 更新 README、示例反馈和计划文件，记录当前无 embedding 依赖的学习策略。
- 创建/修改的文件：
  - `paper_recommender/feedback.py`
  - `paper_recommender/pipeline.py`
  - `site/feedback.js`
  - `tests/test_feedback.py`
  - `tests/test_feedback_pipeline.py`
  - `tests/test_feedback_page_contract.py`
  - `examples/sample_feedback.json`
  - `README.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

## 会话补充：推荐历史与重复惩罚
- **状态：** complete
- 执行的操作：
  - 增加 `paper_recommender.history`，支持读取/写入本地历史 JSON、从 Supabase 读取 `recommendation_runs`、把本次推荐 upsert 回 Supabase。
  - pipeline 增加 `--history` 参数，并在推荐排序时对历史出现过的论文按出现次数施加重复惩罚。
  - 推荐 payload 增加 `history_summary.shown_counts`，便于观察去重行为。
  - GitHub Actions 增加 `output/history.json` 初始化、Supabase 历史读取、pipeline 历史输入和生成后历史发布步骤。
  - 增加历史模块、重复惩罚和 workflow 契约测试。
  - 更新 README、示例历史文件、计划和发现记录。
- 创建/修改的文件：
  - `paper_recommender/history.py`
  - `paper_recommender/pipeline.py`
  - `.github/workflows/daily.yml`
  - `tests/test_history.py`
  - `tests/test_feedback_pipeline.py`
  - `tests/test_workflow_contract.py`
  - `examples/sample_history.json`
  - `README.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

## 会话补充：邮件重试与空推荐处理
- **状态：** complete
- 执行的操作：
  - 增加 `should_send_digest`，默认空推荐不发送邮件。
  - 增加 `send_email_message_with_retries`，SMTP 失败时按固定短延迟最多重试 3 次。
  - CLI 增加 `--max-attempts` 和 `--send-empty`。
  - GitHub Actions 邮件步骤显式使用 `--max-attempts 3`。
  - 增加邮件发送和 workflow 契约测试。
- 创建/修改的文件：
  - `paper_recommender/email_delivery.py`
  - `tests/test_email_delivery.py`
  - `tests/test_workflow_contract.py`
  - `.github/workflows/daily.yml`
  - `README.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

## 会话补充：更多推荐、TLDR 和前端重设计
- **状态：** complete
- 执行的操作：
  - `Paper` 增加 `url`、`pdf_url`、`code_urls`，pipeline 从 arXiv URL 和摘要中提取 Paper/PDF/Code 链接。
  - pipeline 增加 `--min-count`，可用 exploratory core-category papers 补足推荐数量。
  - workflow 改为抓取 500 条 arXiv 候选，输出最多 80 条，最低补足 60 条。
  - 首次真实 workflow 生成 39 条；随后放宽补足策略：核心分类优先，不足时使用无 negative/noise matches 的扩展分类作为 exploratory。
  - 新增 `paper_recommender.summarizer`，通过 OpenAI-compatible API 生成 TLDR，默认接 OpenCode Go；无 key 或调用失败时用本地 fallback。
  - 页面和邮件都展示 TLDR、Paper/PDF/Code 链接。
  - 重设计 GitHub Pages 前端为 workbench 风格：顶部统计、侧边栏目导航、清晰论文卡片和操作按钮。
  - GitHub secret `OPENAI_API_KEY` 已写入用户提供的 OpenCode Go key。
- 创建/修改的文件：
  - `paper_recommender/domain.py`
  - `paper_recommender/pipeline.py`
  - `paper_recommender/summarizer.py`
  - `paper_recommender/emailer.py`
  - `site/index.html`
  - `site/app.js`
  - `site/styles.css`
  - `.github/workflows/daily.yml`
  - `tests/test_pipeline.py`
  - `tests/test_emailer.py`
  - `tests/test_site_contract.py`
  - `tests/test_summarizer.py`
  - `tests/test_workflow_contract.py`
  - `README.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

### 当前仓库命名状态
- 当前本地路径：`/Users/foreverhyx/agentic-arch-paper-recommender`
- 当前远程仓库名：`ForeverHYX/agentic-arch-paper-recommender`
- 当前远程 URL：`git@github.com:ForeverHYX/agentic-arch-paper-recommender.git`
- 验证：最新提交已推送回原仓库。
- 备注：新仓库 `ForeverHYX/daily-arxiv-recommender` 仍存在；删除命令在本会话被执行审批层拒绝，不能改用绕过方式删除。需要用户在 GitHub 页面手动删除，或在明确接受不可逆删除风险后重新授权再试。

## 五问重启检查
| 问题 | 答案 |
|------|------|
| 我在哪里？ | 阶段 1：方案确认与项目初始化 |
| 我要去哪里？ | 继续完善真实每日 pipeline、反馈学习质量、邮件推送可靠性和上线验证 |
| 目标是什么？ | 构建一个无自有服务器、保留 GitHub Pages、带邮件和反馈学习的个性化论文推荐系统 |
| 我学到了什么？ | 见 `findings.md` |
| 我做了什么？ | 已接入真实 arXiv Atom 数据源、反馈关键词学习、推荐历史去重、邮件发送、TLDR 总结和更清爽的前端 |

---
*每个阶段完成后或遇到错误时更新此文件*
