# 发现与决策

## 需求
- 用户没有 Zotero 账户，也不希望维护服务器。
- 用户希望搭建每日论文推荐系统，支持 GitHub Pages 展示。
- 用户希望增加邮件推送。
- 用户希望通过喜欢/不喜欢反馈调整后续推荐，形成“越用越懂我”的闭环。
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
- `section_weights`
- `embedding_summary`

## 遇到的问题
| 问题 | 解决方案 |
|------|---------|
| `ASSASSYN` 暂未确认准确论文链接或标题 | 等用户补充后加入 seed paper 和关键词组。 |
| 静态页面无法安全写入 GitHub 仓库 | 使用 Supabase 或后续 Cloudflare Worker/D1。 |
| 泛 AI agent 论文会污染结果 | 扩展分类必须经过领域 gate，并对泛 agent 关键词降权。 |
| 当前环境连接 `github.com:443` 下载上游代码多次超时 | 先实现自有 MVP，保留后续接入 `daily-arXiv-ai-enhanced` 的阶段任务。 |

## 资源
- `daily-arXiv-ai-enhanced`: https://github.com/dw-dengwei/daily-arXiv-ai-enhanced
- arXiv taxonomy: https://arxiv.org/category_taxonomy
- 代表方向 seed，需要后续在实现阶段固化到配置中：
  - ArchAgent: Agentic AI-driven Computer Architecture Discovery
  - Agentic Architect: Agentic AI Framework for Architecture Design Exploration and Optimization
  - Computer Architecture's AlphaZero Moment: Automated Discovery in an Encircled World

## 视觉/浏览器发现
- 上游项目 README 显示其主要能力为 GitHub Actions、Pages、AI 摘要、本地偏好存储和关键词/作者配置。
- 上游 Settings 页面包含 Interested Keywords 和 Interested Authors，但没有看到开箱即用的喜欢/不喜欢推荐学习闭环。

---
*每执行2次查看/浏览器/搜索操作后更新此文件*
*防止视觉信息丢失*
