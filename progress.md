# 进度日志

## 会话：2026-06-12

### 阶段 1：方案确认与项目初始化
- **状态：** in_progress
- **开始时间：** 2026-06-12 Asia/Shanghai
- 执行的操作：
  - 根据用户确认的方向创建项目规划目录，后续将更名为 `daily-arxiv-recommender`。
  - 生成 `task_plan.md`、`findings.md`、`progress.md` 三个规划文件。
  - 将无服务器约束、GitHub Pages、邮件推送、Supabase 反馈和领域画像写入初版计划。
  - 核对目录和文件存在性，确认初版计划已落盘。
- 创建/修改的文件：
  - `task_plan.md`
  - `findings.md`
  - `progress.md`

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
| 规划目录创建 | `daily-arxiv-recommender` | 目录存在 | 初始目录存在，准备更名为通用项目名 | pass |
| 规划文件创建 | 三个 Markdown 文件 | 文件存在且包含初版计划 | `task_plan.md`、`findings.md`、`progress.md` 均已创建 | pass |
| 上游代码获取 | `git clone` / GitHub zip archive | 成功下载上游代码 | 连接 `github.com:443` 超时 | blocked-for-now |
| 推荐内核测试 | `python3 -m unittest discover -s tests` | 测试通过 | 15 个测试通过 | pass |
| 推荐 JSON 生成 | `python3 -m paper_recommender.pipeline --input examples/sample_papers.jsonl --profile config/interests.json --output site/recommendations.json --run-date 2026-06-12 --limit 25` | 生成推荐 JSON | 写入 2 条推荐 | pass |
| Supabase schema 测试 | `python3 -m unittest tests.test_supabase_schema` | 测试通过 | schema 契约测试通过 | pass |

## 错误日志
| 时间戳 | 错误 | 尝试次数 | 解决方案 |
|--------|------|---------|---------|
| 2026-06-12 | 暂无 | 0 | 暂无 |
| 2026-06-12 | 拉取上游项目失败：连接 `github.com:443` 超时 | 3 | 停止重复同类尝试，先开发自有 MVP；后续网络可用时再接入上游 |

## 会话补充：通用化命名与兴趣配置抽离
- **状态：** in_progress
- 执行的操作：
  - 用户要求将项目从特定的 agentic architecture 推荐器改成更通用的每日 arXiv 推荐器。
  - 增加 `config/interests.json`，把分类、栏目、关键词、降权规则和恢复词从代码中抽离。
  - 更新 pipeline，让推荐 JSON 包含 `profile_name` 和 `section_labels`。
  - 更新邮件渲染和 GitHub Pages 前端，栏目名从推荐 JSON 读取。
  - 更新 GitHub Actions 默认 Pages URL 为 `daily-arxiv-recommender`。
  - 使用 TDD 增加配置化兴趣画像测试。
  - 本地文件夹已从 `agentic-arch-paper-recommender` 更名为 `daily-arxiv-recommender`。
  - GitHub 远程仓库重命名普通请求连接失败；随后创建目标名新仓库并将本地 `origin` 切换过去。
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

### 当前仓库命名状态
- 本地路径：`/Users/foreverhyx/daily-arxiv-recommender`
- 期望远程仓库名：`ForeverHYX/daily-arxiv-recommender`
- 当前远程仓库名：`ForeverHYX/daily-arxiv-recommender`
- 当前远程 URL：`git@github.com:ForeverHYX/daily-arxiv-recommender.git`
- 验证：`gh repo view ForeverHYX/daily-arxiv-recommender` 返回 public 仓库，默认分支为 `main`。
- 备注：旧仓库 `ForeverHYX/agentic-arch-paper-recommender` 仍存在，因为 GitHub API rename/PATCH 调用失败；当前代码已同步到新仓库。

## 五问重启检查
| 问题 | 答案 |
|------|------|
| 我在哪里？ | 阶段 1：方案确认与项目初始化 |
| 我要去哪里？ | 审计上游项目，确定最小改造范围，然后实现领域过滤、反馈存储、邮件推送和推荐学习闭环 |
| 目标是什么？ | 构建一个无自有服务器、保留 GitHub Pages、带邮件和反馈学习的个性化论文推荐系统 |
| 我学到了什么？ | 见 `findings.md` |
| 我做了什么？ | 创建规划目录和三份规划文件 |

---
*每个阶段完成后或遇到错误时更新此文件*
