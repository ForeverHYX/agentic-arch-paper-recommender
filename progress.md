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

## 会话补充：反馈闭环状态诊断与本地导出
- **状态：** in_progress
- 执行的操作：
  - 在 Pages 侧边栏增加反馈持久化状态，区分 `Supabase active` 和 `local only`。
  - `local only` 模式显示当前浏览器保存的本地反馈数量，避免误以为点击已经进入跨天推荐学习。
  - 反馈页在 Supabase 未配置时展示本地反馈 JSON，并提供下载链接。
  - README 增加本地反馈导出、Supabase RLS、服务密钥和后续滥用加固说明。
- 创建/修改的文件：
  - `site/index.html`
  - `site/app.js`
  - `site/feedback.html`
  - `site/feedback.js`
  - `site/styles.css`
  - `tests/test_site_contract.py`
  - `tests/test_feedback_page_contract.py`
  - `README.md`
  - `task_plan.md`
  - `progress.md`

| 反馈状态诊断 RED 测试 | `python3 -m unittest tests.test_site_contract tests.test_feedback_page_contract` | 缺少 `renderFeedbackStatus`、`feedbackStatus` 和本地导出时失败 | `renderFeedbackStatus is not a function`，页面缺少导出元素 | expected-fail |
| 反馈状态诊断局部测试 | `python3 -m unittest tests.test_site_contract tests.test_feedback_page_contract` | 测试通过 | 9 个测试通过 | pass |

## 会话补充：反馈学习指标
- **状态：** in_progress
- 执行的操作：
  - 增加 `feedback_metrics`，统计反馈总数、like/dislike、like rate、来源/栏目分布和正负反馈主题。
  - `recommendations.json` 的 `feedback_summary.metrics` 写入上述指标。
  - Pages 侧边栏显示学习指标摘要：反馈量、喜欢率、liked/disliked topics。
  - 邮件 digest 顶部显示同一组反馈指标，便于每天查看推荐画像状态。
  - README 和计划说明邮件打开率需要外部追踪，MVP 只做可验证的反馈指标。
- 创建/修改的文件：
  - `paper_recommender/feedback.py`
  - `paper_recommender/pipeline.py`
  - `paper_recommender/emailer.py`
  - `site/index.html`
  - `site/app.js`
  - `site/styles.css`
  - `tests/test_feedback.py`
  - `tests/test_feedback_pipeline.py`
  - `tests/test_site_contract.py`
  - `tests/test_emailer.py`
  - `README.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

| 反馈指标 RED 测试 | `python3 -m unittest tests.test_feedback tests.test_feedback_pipeline tests.test_site_contract tests.test_emailer` | 缺少 metrics 函数、payload 字段、页面函数和邮件摘要时失败 | import/key/function/assertion 失败 | expected-fail |
| 反馈指标局部测试 | `python3 -m unittest tests.test_feedback tests.test_feedback_pipeline tests.test_site_contract tests.test_emailer` | 测试通过 | 22 个测试通过 | pass |

## 会话补充：无 Supabase 的反馈回灌
- **状态：** in_progress
- 执行的操作：
  - 增加 `feedback_events_from_json_text`，支持读取 Pages 本地导出的反馈 JSON。
  - `paper_recommender.feedback` 增加 `--from-env`，可从指定环境变量读取反馈 JSON 并写入标准 `output/feedback.json`。
  - workflow 增加 `LOCAL_FEEDBACK_JSON` Secret fallback：Supabase 未启用且该 Secret 存在时，自动加载本地导出的反馈进入推荐 pipeline。
  - README、计划和发现记录补充该 fallback 的使用方式和边界。
- 创建/修改的文件：
  - `.github/workflows/daily.yml`
  - `paper_recommender/feedback.py`
  - `tests/test_feedback.py`
  - `tests/test_workflow_contract.py`
  - `README.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

| 本地反馈 Secret fallback RED 测试 | `python3 -m unittest tests.test_feedback tests.test_workflow_contract` | 缺少 JSON text parser、`--from-env` 和 workflow step 时失败 | import 失败，workflow 断言失败 | expected-fail |
| 本地反馈 Secret fallback 局部测试 | `python3 -m unittest tests.test_feedback tests.test_workflow_contract` | 测试通过 | 18 个测试通过 | pass |

## 会话补充：兴趣设置页和 profile override
- **状态：** in_progress
- 执行的操作：
  - 增加 `paper_recommender.profile_config`，从 `PROFILE_OVERRIDE_JSON` 环境变量读取并验证兴趣画像 JSON。
  - workflow 初始化 `output/interests.json`，可用 `PROFILE_OVERRIDE_JSON` 覆盖默认 `config/interests.json`。
  - arXiv 抓取和推荐 pipeline 都改为使用 `output/interests.json`，并把该文件发布为 Pages `interests.json`。
  - 新增 `site/profile.html` 和 `site/profile.js`，支持浏览器编辑、保存本地 copy、下载 `recommender-profile.json`。
  - README、计划和发现记录补充设置页和 Secret 导入说明。
- 创建/修改的文件：
  - `.github/workflows/daily.yml`
  - `paper_recommender/profile_config.py`
  - `site/profile.html`
  - `site/profile.js`
  - `site/index.html`
  - `site/styles.css`
  - `tests/test_interest_profile.py`
  - `tests/test_workflow_contract.py`
  - `tests/test_profile_page_contract.py`
  - `README.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

| profile override RED 测试 | `python3 -m unittest tests.test_interest_profile tests.test_workflow_contract tests.test_profile_page_contract` | 缺少 profile_config、workflow override 和 profile 页面时失败 | module/html/js/workflow 断言失败 | expected-fail |
| profile override 局部测试 | `python3 -m unittest tests.test_interest_profile tests.test_workflow_contract tests.test_profile_page_contract` | 测试通过 | 15 个测试通过 | pass |

## 会话补充：部署状态诊断
- **状态：** in_progress
- 执行的操作：
  - 增加 `paper_recommender.status`，生成不含密钥值的 `status.json`。
  - workflow 增加 `HAS_LLM` 和 `Publish subsystem status` 步骤，发布 LLM、SMTP、Supabase、本地反馈 fallback、profile override 的启用状态。
  - Pages 侧边栏显示 Systems 状态，包含 LLM 模型名和各子系统 on/off。
  - README、计划和发现记录补充状态诊断说明。
- 创建/修改的文件：
  - `.github/workflows/daily.yml`
  - `paper_recommender/status.py`
  - `site/index.html`
  - `site/app.js`
  - `site/styles.css`
  - `tests/test_status.py`
  - `tests/test_workflow_contract.py`
  - `tests/test_site_contract.py`
  - `README.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

| 部署状态诊断 RED 测试 | `python3 -m unittest tests.test_status tests.test_workflow_contract tests.test_site_contract` | 缺少 status 模块、workflow step 和前端函数时失败 | module/function/workflow 断言失败 | expected-fail |
| 部署状态诊断局部测试 | `python3 -m unittest tests.test_status tests.test_workflow_contract tests.test_site_contract` | 测试通过 | 19 个测试通过 | pass |

## 会话补充：邮件到 Pages 论文深链
- **状态：** in_progress
- 执行的操作：
  - 发现邮件标题链接已经携带 `?paper_id=...`，但 Pages 没有读取该参数定位论文卡片。
  - 增加 `highlightTargetPaper`，在渲染/筛选后根据 `paper_id` 查询对应卡片、加高亮并滚动到可视区域。
  - 为目标论文卡片增加 `.paper.is-target` 高亮样式。
- 创建/修改的文件：
  - `site/app.js`
  - `site/index.html`
  - `site/styles.css`
  - `tests/test_site_contract.py`
  - `progress.md`

| 邮件深链 RED 测试 | `python3 -m unittest tests.test_site_contract.SiteContractTests.test_reader_deep_links_to_paper_from_email_query_param tests.test_site_contract.SiteContractTests.test_recommendation_page_has_workbench_layout_hooks` | 缺少 `highlightTargetPaper` 时失败 | `highlightTargetPaper is not a function` | expected-fail |
| 邮件深链局部测试 | 同上 | 测试通过 | 2 个测试通过 | pass |

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

## 会话补充：作者/机构/工具链反馈学习
- **状态：** complete
- 执行的操作：
  - 增加 `author_feedback_weights`、`affiliation_feedback_weights`、`toolchain_feedback_weights`。
  - pipeline 排序在 section、关键词、历史去重之外，额外应用作者、机构和工具链反馈权重。
  - `feedback_summary` 增加 `author_weights`、`affiliation_weights`、`toolchain_weights`，便于观察画像状态。
  - LLM judge prompt 增加 prefer/avoid authors、affiliations、toolchains。
  - README、计划和发现记录补充实体反馈学习说明。
- 创建/修改的文件：
  - `paper_recommender/feedback.py`
  - `paper_recommender/pipeline.py`
  - `paper_recommender/judge.py`
  - `tests/test_feedback.py`
  - `tests/test_feedback_pipeline.py`
  - `tests/test_judge.py`
  - `README.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

| 实体反馈学习 RED 测试 | `python3 -m unittest tests.test_feedback tests.test_feedback_pipeline tests.test_judge` | 缺少实体权重函数、payload 字段和 LLM prompt 内容时失败 | 缺少 `author_feedback_weights`、`author_weights` 和 prompt 字段 | expected-fail |
| 实体反馈学习局部测试 | `python3 -m unittest tests.test_feedback tests.test_feedback_pipeline tests.test_judge` | 测试通过 | 20 个测试通过 | pass |

## 会话补充：上游项目审计复核
- **状态：** complete
- 执行的操作：
  - 重新尝试 clone `daily-arXiv-ai-enhanced` 和 `zotero-arxiv-daily`，本地 git 仍因 `github.com:443` 连接超时失败。
  - 改用 GitHub 页面/raw 文件完成只读审计。
  - 确认 `daily-arXiv-ai-enhanced` 的主要可借鉴点是 GitHub Actions + Pages + AI 摘要/邮件形态。
  - 确认 `zotero-arxiv-daily` 的主要可借鉴点是 Zotero library/collection 作为兴趣锚点；本仓库已用 `seed_papers` 和反馈画像替代 Zotero 账户依赖。
  - 更新 README、计划和发现记录，去掉“等待网络可用再审计”的旧表述。
- 创建/修改的文件：
  - `README.md`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

| 上游 clone 复核 | `git clone --depth 1 ...` | 能拉取上游代码 | 两个仓库均因 `github.com:443` 超时失败 | failed-network |
| 上游 raw 审计 | GitHub 页面/raw 文件 | 能确认上游功能和可借鉴范围 | 完成审计并更新文档 | pass |

## 会话补充：反馈未配置时的本地 fallback
- **状态：** complete
- 执行的操作：
  - 定位到 `site/feedback.js` 在 Supabase 未配置时显示 “Feedback captured locally”，但没有真正写入本地存储。
  - 增加浏览器 `localStorage` 队列 `recommender_local_feedback_events`，保存 paper id、rating、section 和论文元数据。
  - 更新页面提示，明确本地存储只保存在当前浏览器；跨天推荐学习仍需要 Supabase。
  - 更新 README 说明 Supabase 与 localStorage fallback 的边界。
- 创建/修改的文件：
  - `site/feedback.js`
  - `tests/test_feedback_page_contract.py`
  - `README.md`
  - `progress.md`

| 反馈本地 fallback RED 测试 | `python3 -m unittest tests.test_feedback_page_contract` | Supabase 未配置时应写入 localStorage | 初始没有写入 `recommender_local_feedback_events` | expected-fail |
| 反馈本地 fallback 局部测试 | `python3 -m unittest tests.test_feedback_page_contract` | 测试通过 | 2 个测试通过 | pass |

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

## 会话补充：作者单位前端可见性
- **状态：** complete
- 执行的操作：
  - 验证线上 `recommendations.json` 已有部分论文作者单位：当前 12 篇中 6 篇带 `affiliations`。
  - 将论文卡片单位标签从“单位”改为更明确的“作者单位”。
  - 更新 `app.js` 查询版本号，避免浏览器继续使用旧缓存。
  - 给仓库自带示例推荐数据补充 `affiliations` 和 `affiliation_summary`，避免本地静态预览误以为页面没有单位展示。
  - 增加站点契约测试，覆盖明确标签、示例数据和缓存版本号。
- 创建/修改的文件：
  - `site/app.js`
  - `site/index.html`
  - `site/recommendations.json`
  - `tests/test_site_contract.py`
  - `progress.md`

## 会话补充：上线验证状态同步
- **状态：** complete
- 执行的操作：
  - 查询 GitHub Actions run `27405554116`，确认 `Daily Paper Recommender` 在提交 `4c6415203374113e8ba879070d8a57d842ce5693` 上成功完成。
  - 查询线上 `status.json`，确认 LLM 和 SMTP 已配置，Supabase、`LOCAL_FEEDBACK_JSON` 和 `PROFILE_OVERRIDE_JSON` 尚未配置。
  - 查询线上 `recommendations.json`，确认 2026-06-12 页面加载 12 条推荐，12 条都有 TLDR 和 AI 判断。
  - 同步 `task_plan.md` 阶段 8 状态：真实 workflow、Pages 当天数据加载、邮件跳转链路标记为已验证；Supabase 写入和反馈影响排序继续保留未完成。
- 创建/修改的文件：
  - `task_plan.md`
  - `progress.md`

## 会话补充：Run Health 安静状态提示
- **状态：** complete
- 执行的操作：
  - 增加 GitHub Pages 侧边栏 `Run Health` 状态块。
  - 页面现在显示 AI 判断覆盖率和 TLDR 覆盖率，例如 `12/12 judged, 12/12 TLDR`。
  - 页面现在显示反馈模式：`Supabase active` 或 `local only`。
  - Supabase 未启用时显示 `not persistent yet`，并列出 `SUPABASE_URL`、`SUPABASE_ANON_KEY`、`SUPABASE_SERVICE_ROLE_KEY` 作为下一步配置项。
  - 增加站点契约测试覆盖 HTML 占位、cache bust、local-only 模式和 Supabase active 模式。
  - 触发 GitHub Actions run `27413293913` 并成功部署 Pages。
  - 线上验证：`index.html` 已包含 `runHealth` 占位和 `app.js?v=20260612-run-health`；线上 `recommendations.json` 当前 12 条推荐中 12 条有 AI 判断、12 条有 TLDR；线上 `status.json` 显示 LLM/SMTP 已启用、Supabase 未启用。
- 创建/修改的文件：
  - `site/index.html`
  - `site/app.js`
  - `site/styles.css`
  - `tests/test_site_contract.py`
  - `progress.md`
  - `docs/superpowers/plans/2026-06-12-run-health.md`

## 会话补充：Supabase 配置清单
- **状态：** complete
- 执行的操作：
  - 增加 `docs/setup-supabase.md`，把持久化反馈所需步骤从 README 简述扩展为可执行清单。
  - 清单覆盖运行 `supabase/schema.sql`、配置 `SUPABASE_URL`、`SUPABASE_ANON_KEY`、`SUPABASE_SERVICE_ROLE_KEY`、重跑 `Daily Paper Recommender` workflow、检查 Pages `Run Health` 和验证 `feedback_events` 写入。
  - README 的 `Feedback Storage` 段落增加配置清单链接。
  - 增加 `tests/test_docs_contract.py`，防止 Supabase 配置入口和关键变量名从文档中丢失。
- 创建/修改的文件：
  - `docs/setup-supabase.md`
  - `README.md`
  - `tests/test_docs_contract.py`
  - `progress.md`

## 会话补充：Supabase 配置验证、中文化和长 TLDR
- **状态：** in_progress
- 执行的操作：
  - 按用户要求继续在原 `main` 分支迭代，并注意不把任何密钥明文写入仓库。
  - 验证 GitHub Variables 中存在 `SUPABASE_URL`、`SUPABASE_ANON_KEY`，GitHub Secrets 中存在 `SUPABASE_SERVICE_ROLE_KEY`；未把密钥值写入文件。
  - 查询线上 `status.json`，确认 Supabase configured 为 true；查询线上 `config.js`，确认 Pages 已注入公开 Supabase 配置。
  - 查询 GitHub Actions run `27473671636` job JSON，确认 `Fetch Supabase feedback`、`Fetch Supabase recommendation history`、`Publish Supabase recommendation history` 均成功。
  - 审批层拒绝了直接 Supabase REST 探针；未绕过该限制，因此真实用户点击写入 `feedback_events` 仍保留待验证。
  - 将站点首页、反馈页、兴趣画像页、邮件正文、默认兴趣画像显示名、示例推荐数据和主要 Python CLI 日志文案中文化。
  - 将 TLDR prompt 从“45 字短句”改为 180-260 字左右的中文结构化核心解读，要求覆盖研究问题、核心方法、关键结论和推荐理由。
  - 将本地 fallback TLDR 从英文截断改为中文结构化摘要，避免 LLM 不可用时继续产出无信息量摘要。
  - 优化左侧栏：运行状态、反馈状态、学习画像和系统状态移到筛选控件上方；sidebar 设置视口内滚动，避免信息卡片被压到侧栏底部。
- 创建/修改的文件：
  - `config/interests.json`
  - `paper_recommender/*.py`
  - `site/index.html`
  - `site/app.js`
  - `site/styles.css`
  - `site/feedback.html`
  - `site/feedback.js`
  - `site/profile.html`
  - `site/profile.js`
  - `site/recommendations.json`
  - `tests/test_summarizer.py`
  - `tests/test_emailer.py`
  - `tests/test_site_contract.py`
  - `tests/test_feedback_page_contract.py`
  - `tests/test_profile_page_contract.py`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

| 中文化/TLDR/侧栏焦点测试 | `python3 -m unittest tests.test_summarizer tests.test_emailer tests.test_site_contract tests.test_feedback_page_contract tests.test_profile_page_contract` | 测试通过 | 28 个测试通过 | pass |
| 全量测试 | `python3 -m unittest discover -s tests` | 测试通过 | 101 个测试通过 | pass |
| 前端语法检查 | `node --check site/app.js`、`node --check site/feedback.js`、`node --check site/profile.js` | JS 语法正确 | 通过 | pass |
| JSON 语法检查 | `python3 -m json.tool config/interests.json`、`python3 -m json.tool site/recommendations.json` | JSON 可解析 | 通过 | pass |
| diff 密钥扫描 | `git diff | rg ...` | 不出现 Supabase/OpenAI/SMTP 密钥明文 | 无匹配 | pass |

---
*每个阶段完成后或遇到错误时更新此文件*
