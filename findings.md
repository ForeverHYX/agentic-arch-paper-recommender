# 发现与决策

## 需求
- 用户没有 Zotero 账户，也不希望维护服务器。
- 用户希望搭建每日论文推荐系统，支持 GitHub Pages 展示。
- 用户希望增加邮件推送。
- 用户希望通过喜欢/不喜欢反馈调整后续推荐，形成“越用越懂我”的闭环。
- 用户希望推荐打分本身也引入 AI 判断，而不是只靠关键词规则。
- 用户希望显示作者单位，并把单位作为排除低质量工作的辅助信号。
- 用户兴趣不是泛体系结构或泛 EDA，而是更窄的交叉方向：
  - agentic computer architecture design。
  - 自动架构发现和设计空间探索。
  - 全栈软硬件协同设计。
  - CPU/GPU 微架构。
  - 体系结构模拟器。
  - HPC 与以上方向的交叉。

## 研究发现
- `daily-arXiv-ai-enhanced` 的定位是每日抓取 arXiv、AI 摘要、GitHub Pages 展示，适合作为无服务器展示层起点。
- 上游 README 中默认分类偏向 `cs.CV, cs.GR, cs.CL, cs.AI`，不适合当前用户的体系结构/HPC/co-design 兴趣。
- 上游项目已有本地关键词和作者偏好能力，但主要是浏览器本地高亮/过滤，不是服务端或跨设备的反馈学习。
- GitHub Pages 是静态页面，不能安全地直接写入私有仓库或 GitHub Actions 状态。
- 反馈闭环需要外部托管存储。初始推荐 Supabase，因为它可以用免费层提供 Postgres、RLS 和前端写入能力。
- 对于当前兴趣，`cs.AI` 和 `cs.LG` 不能直接全量抓取，否则会引入大量泛 AI/agent 噪声，必须通过关键词 gate。

## 领域关键词
### Agentic Architecture / Auto-DSE
- agentic AI for computer architecture
- computer architecture discovery
- automated architecture discovery
- architecture design space exploration
- microarchitecture design space exploration
- LLM-driven architecture exploration
- architecture idea factory
- hardware design agent
- microarchitecture optimization
- cache replacement policy
- data prefetcher
- branch predictor
- cycle-accurate simulation
- simulator interface
- workload specialization
- post-silicon specialization

### Full-stack HW/SW Co-design
- software hardware co-design
- hardware software co-optimization
- full-stack co-design
- compiler architecture co-design
- ISA extension
- RISC-V custom extension
- accelerator compiler
- domain-specific architecture
- domain-specific accelerator
- workload-driven architecture
- MLIR
- CIRCT
- TVM
- Triton
- XLA
- Halide
- runtime system
- hardware-aware optimization

### CPU/GPU Microarchitecture and Simulators
- CPU microarchitecture
- GPU microarchitecture
- out-of-order
- OoO
- memory hierarchy
- cache hierarchy
- cache coherence
- TLB
- virtual memory
- NoC
- interconnect
- SIMT
- warp scheduling
- tensor core
- gem5
- ChampSim
- Sniper
- SST
- GPGPU-Sim
- Accel-Sim
- Ramulator
- DRAMSim
- McPAT
- SPEC CPU
- PARSEC
- Rodinia
- MLPerf

### HPC Cross-over
- high performance computing
- HPC
- exascale
- parallel runtime
- MPI
- OpenMP
- CUDA
- ROCm
- SYCL
- Kokkos
- RAJA
- performance portability
- roofline
- NUMA
- communication-avoiding
- sparse linear algebra
- graph analytics
- memory bandwidth
- interconnect

## 排除或降权关键词
- neural architecture search
- NAS
- software architecture
- multi-agent software framework
- cloud architecture
- enterprise architecture
- building architecture
- robot architecture
- network architecture
- LLM agent benchmark
- prompting agent
- web agent
- RAG agent

说明：`neural architecture search` 不是绝对排除。如果同时出现 `hardware-aware`、`accelerator`、`FPGA`、`compiler`、`co-design` 等关键词，应转为弱相关或候选。

## 技术决策
| 决策 | 理由 |
|------|------|
| 使用 GitHub Actions 做每日 pipeline | 无需自有服务器，和上游项目一致。 |
| 使用 GitHub Pages 保留网页展示 | 用户明确希望保留 GitHub Page。 |
| 使用 Supabase 保存反馈 | 解决静态页面无法持久化跨设备反馈的问题。 |
| 反馈以事件形式记录 | 可以保留时间、来源、论文、rating，方便后续重新训练画像。 |
| 邮件由 GitHub Actions 发送 | 不需要部署邮件服务。 |
| 推荐邮件按栏目分组 | 用户兴趣包含多个交叉子方向，分组可以避免早期排序偏科。 |
| arXiv source 输出 JSONL | 保持抓取、解析、推荐排序和页面展示解耦；后续增加 Semantic Scholar 或 RSS 时只需输出同一记录格式。 |
| workflow 契约测试覆盖真实数据源 | 防止每日 workflow 意外退回 `examples/sample_papers.jsonl`，保证自动化流程持续使用真实 arXiv 抓取结果。 |
| 反馈页面从 `recommendations.json` 补全论文元数据 | 避免在邮件/页面反馈链接中塞长摘要，同时让 Supabase 反馈事件可用于后续关键词学习。 |
| 先用轻量关键词 fallback 而非 embedding | 不需要额外 API key 或依赖，能在 GitHub Actions 中稳定运行；后续反馈量上来后再替换或叠加 embedding。 |
| `recommendation_runs` 用于跨天去重 | 每次 workflow 生成推荐后写回 Supabase，下一次读取历史并按出现次数惩罚重复论文。 |
| 空推荐默认不发邮件 | 避免用户每天收到低价值空摘要；需要时可用 `--send-empty` 显式发送。 |
| 默认抓取 500 条候选并输出最多 15 条推荐 | 候选池保持较大以保证召回，但邮件和页面保持可读，不超过用户希望的 15 条。 |
| TLDR enrichment 接 OpenCode Go | 使用 OpenAI-compatible `/chat/completions`，默认 base URL 为 `https://opencode.ai/zen/go/v1`，默认模型为 `deepseek-v4-flash`。 |
| exploratory 补足先核心、后干净扩展分类 | 真实 workflow 从 500 条候选只产出 39 条时，说明核心分类不足；扩展分类若无 negative/noise matches，可作为低优先级 exploratory 补足。 |
| LLM 判断用于最终推荐重排 | 规则排序先产出 45 条候选，OpenCode Go 对每篇论文返回 0-10 相关性分数、保留/丢弃决策和原因，再截断到最多 15 条。无 key 或请求失败时回退到规则分。 |
| Code 链接采用显式抽取 + GitHub 搜索兜底 | 摘要中出现 GitHub/GitLab/Bitbucket/Hugging Face 链接时展示直达 Code；否则用标题生成 GitHub repository search 链接。 |
| 作者单位作为弱质量信号 | arXiv Atom 通常不稳定提供单位；系统解析 `arxiv:affiliation` 和外部记录里的 `affiliations`，展示给用户，并传入 LLM judge，但不会因单位缺失直接丢弃论文。 |
| 作者单位补全从 arXiv source 提取 | 当前 live JSON 单位为空的根因是 arXiv Atom 未给出单位。新增 source bundle enrichment：对最终推荐下载 arXiv e-print，解析 TeX 中 `\\affil`、`\\affiliation`、`\\institute` 等宏。 |
| LLM judge 纳入反馈画像 | `feedback_summary` 中的 section 权重和关键词权重现在会进入 LLM prompt，作为类似 Zotero/library 相似度的轻量个性化信号。 |
| OpenCode Go 配置保持 OpenAI-compatible 形态 | `OPENAI_API_KEY` 用 Secret，`OPENAI_BASE_URL` 和 `OPENAI_MODEL` 用 GitHub Variables 覆盖；默认值仍指向 OpenCode Go 和 `deepseek-v4-flash`。 |
| seed papers 作为无服务器个人语料锚点 | `config/interests.json` 中的 `seed_papers` 会写入推荐 JSON，并进入 LLM judge prompt，让代表性论文比单纯关键词更直接地约束相关性判断。 |
| 反馈学习加入实体权重 | like/dislike 现在会学习作者、机构和体系结构/HPC 工具链权重，并同时影响规则排序和 LLM judge prompt。机构权重保持弱信号，避免 arXiv 单位缺失导致过度惩罚。 |

## 初始数据表设想
### `feedback_events`
- `id`
- `paper_id`
- `rating`: `like` 或 `dislike`
- `source`: `page` 或 `email`
- `section`
- `title`
- `abstract`
- `authors`
- `categories`
- `created_at`

### `recommendation_runs`
- `id`
- `run_date`
- `paper_id`
- `rank`
- `score`
- `section`
- `shown_in_email`
- `shown_on_page`

### `profile_state`
- `id`
- `updated_at`
- `liked_keywords`
- `disliked_keywords`
- `liked_authors`
- `liked_affiliations`
- `liked_toolchains`
- `section_weights`
- `embedding_summary`

## 遇到的问题
| 问题 | 解决方案 |
|------|---------|
| `ASSASSYN` 暂未确认准确论文链接 | 已按用户描述作为可编辑 seed 加入 `config/interests.json`；后续可补精确 URL。 |
| 静态页面无法安全写入 GitHub 仓库 | 使用 Supabase 或后续 Cloudflare Worker/D1。 |
| 泛 AI agent 论文会污染结果 | 扩展分类必须经过领域 gate，并对泛 agent 关键词降权。 |
| 当前环境连接 `github.com:443` 下载上游代码多次超时 | 先实现自有 MVP，保留后续接入 `daily-arXiv-ai-enhanced` 的阶段任务。 |

## 资源
- `daily-arXiv-ai-enhanced`: https://github.com/dw-dengwei/daily-arXiv-ai-enhanced
- arXiv taxonomy: https://arxiv.org/category_taxonomy
- 代表方向 seed，已固化到 `config/interests.json` 中：
  - ArchAgent: Agentic AI-driven Computer Architecture Discovery
  - Computer Architecture's AlphaZero Moment: Automated Discovery in an Encircled World
  - ArchExplorer: Microarchitecture Exploration Via Bottleneck Analysis
  - ASSASSYN: A Unified Abstraction for Architectural Simulation and Implementation

## 视觉/浏览器发现
- 上游项目 README 显示其主要能力为 GitHub Actions、Pages、AI 摘要、本地偏好存储和关键词/作者配置。
- 上游 Settings 页面包含 Interested Keywords 和 Interested Authors，但没有看到开箱即用的喜欢/不喜欢推荐学习闭环。

---
*每执行2次查看/浏览器/搜索操作后更新此文件*
*防止视觉信息丢失*
