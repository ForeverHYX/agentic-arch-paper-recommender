# 任务计划：Daily arXiv Recommender

## 目标
基于 `daily-arXiv-ai-enhanced` 思路，构建一个不依赖自有服务器、可通过独立兴趣配置泛化到不同领域的每日 arXiv 推荐系统：保留 GitHub Pages 展示，增加邮件推送和喜欢/不喜欢反馈。默认兴趣配置仍聚焦 agentic computer architecture、自动设计空间探索、软硬件协同、CPU/GPU 微架构、模拟器和 HPC 交叉方向。

## 当前阶段
阶段 1：方案确认与项目初始化

## 项目边界
- 不需要 Zotero 账户。
- 不维护 VPS 或常驻后端服务。
- 保留 GitHub Actions 定时抓取和 GitHub Pages 静态展示。
- 使用托管存储保存反馈，初始推荐 Supabase 免费层。
- 邮件由 GitHub Actions 定时发送，邮件内包含喜欢/不喜欢反馈入口。
- 第一版聚焦 arXiv；Semantic Scholar、会议官网和 RSS 源作为后续增强。
- 关键词、分类、栏目和降权规则必须通过 `config/interests.json` 独立配置，避免写死在代码中。

## 领域画像
### 核心兴趣
- Agentic AI for computer architecture。
- 自动化架构发现和设计空间探索，类似 ArchAgent、Agentic Architect、Computer Architecture's AlphaZero Moment。
- 全栈软硬件协同设计，包括编译器、运行时、ISA、微架构、加速器和仿真器协同优化。
- CPU/GPU 微架构、cache/prefetch/branch predictor/memory hierarchy/NoC/SIMT 等。
- 体系结构模拟器和评估框架，例如 gem5、ChampSim、Sniper、SST、GPGPU-Sim、Accel-Sim、Ramulator。
- HPC 与上述方向的交叉，包括 performance portability、runtime、GPU/HPC 编译和 memory/interconnect 优化。

### 明确降低权重的内容
- 泛 AI agent 应用。
- 泛软件工程 agent。
- 普通 RAG、网页 agent、benchmark agent。
- 泛 neural architecture search，除非同时出现 hardware-aware、accelerator、FPGA、compiler 或 co-design。
- 企业架构、云架构、软件架构、建筑学 architecture。

## 推荐数据源策略
### arXiv 分类
- 核心分类：`cs.AR,cs.PF,cs.DC,cs.PL`
- 扩展分类：`cs.AI,cs.LG`
- 扩展分类必须经过领域关键词 gate，否则噪声太大。

### 推荐栏目
1. Agentic Architecture / Auto-DSE
2. Full-stack HW/SW Co-design
3. CPU/GPU Microarchitecture and Simulators
4. HPC x Architecture / Compiler / Runtime
5. Exploratory but Maybe Relevant

## 初版系统架构
### 组件
- GitHub Actions：每日抓取论文、调用 LLM 摘要、读取反馈、计算推荐、生成页面和邮件。
- GitHub Pages：展示每日论文、搜索、过滤、反馈按钮和反馈落地页。
- Supabase：存储反馈事件和可选的推荐历史，不运行自有服务器。
- SMTP 邮箱：由 GitHub Actions 发送 HTML 邮件。

### 数据流
1. GitHub Actions 定时运行。
2. 抓取 arXiv 核心分类和扩展分类论文。
3. 对扩展分类执行关键词 gate。
4. 对候选论文生成摘要、标签和 embedding 或文本特征。
5. 读取 Supabase 中历史喜欢/不喜欢反馈。
6. 计算混合推荐分数。
7. 生成当天 JSON/Markdown/HTML 数据，发布到 GitHub Pages。
8. 发送邮件，邮件中包含论文链接、页面链接、喜欢/不喜欢链接。
9. 用户点击反馈链接，GitHub Pages 的 `feedback.html` 写入 Supabase。
10. 次日推荐读取反馈并更新画像。

## 推荐算法初版
### 分数组成
```text
 语义上接近喜欢过的论文
- 语义上接近不喜欢的论文
+ 命中核心领域关键词
+ 命中喜欢过的作者、实验室或工具链
+ 所属栏目符合历史偏好
- 命中泛 AI agent / 泛 NAS / 泛软件架构噪声
- 已多次推荐但无反馈的轻微惩罚
```

### 冷启动策略
- 用用户确认的领域关键词作为初始规则。
- 使用代表性 seed papers 建立初始兴趣向量。
- 早期邮件按栏目分配名额，避免某一类候选淹没其他方向。
- 当反馈超过约 20 条后，提高 feedback embedding 权重。

## 计划阶段
### 阶段 1：方案确认与项目初始化
- [x] 创建项目规划目录。
- [x] 创建 `task_plan.md`、`findings.md`、`progress.md`。
- [x] 记录当前需求、约束、领域画像和初步技术路线。
- [x] 用户确认初版计划并要求开始开发。
- [x] 使用原 GitHub 远程仓库 `ForeverHYX/agentic-arch-paper-recommender` 并推送最新提交。
- **状态：** complete

### 阶段 2：上游项目审计与改造范围确认
- [ ] Fork 或 clone `daily-arXiv-ai-enhanced` 到本地工作区。
- [ ] 审计现有 workflow、爬虫、AI 摘要、Pages 数据格式和前端偏好逻辑。
- [ ] 明确最小改造点：分类配置、推荐排序、反馈页面、邮件发送、Supabase 接入。
- [ ] 记录不改动或延后改动的范围。
- **状态：** in_progress

备注：2026-06-12 首次尝试 `git clone` 和 GitHub zip archive 下载均因连接 `github.com:443` 超时失败。当前先推进自有 MVP，后续网络可用时再补做上游审计。

### 阶段 3：领域过滤和推荐画像 MVP
- [x] 配置核心分类和扩展分类。
- [x] 增加真实 arXiv Atom API 数据源，按独立兴趣配置生成抓取分类查询。
- [x] 实现领域关键词 gate。
- [ ] 建立 seed paper 列表和手动关键词权重。
- [x] 实现栏目分配和初版排序。
- [x] 添加排除词和降权逻辑。
- [x] 将关键词画像抽离到 `config/interests.json`。
- [x] 增加 exploratory 补足策略，避免每日推荐数量过少。
- [x] 增加 LLM 判断与重排：规则召回 45 条候选，AI 判断后输出最多 15 条。
- **状态：** in_progress

### 阶段 4：反馈存储
- [ ] 创建 Supabase 项目。
- [x] 设计 `recommendation_runs`、`feedback_events`、`profile_state` 表。
- [x] 配置 RLS：前端只允许插入反馈，不允许读取、更新、删除敏感数据。
- [x] 在 GitHub Actions 中使用服务密钥读取反馈。
- [ ] 记录滥用风险和后续加固方案。
- **状态：** in_progress

### 阶段 5：GitHub Pages 反馈体验
- [x] 在论文卡片中加入喜欢/不喜欢按钮。
- [x] 增加 `feedback.html`，支持从邮件或页面记录反馈。
- [x] 反馈成功后显示简洁确认和返回链接。
- [ ] 保留现有关键词/作者设置页，并考虑导入到推荐画像。
- **状态：** in_progress

### 阶段 6：邮件推送
- [x] 选择 SMTP 服务和邮件模板。
- [x] 在 GitHub Secrets 中配置邮箱凭据。
- [x] 生成按栏目分组的 HTML 邮件。
- [x] 每篇论文包含 GitHub Pages 详情、喜欢、不喜欢链接。
- [x] 添加失败重试和空推荐处理。
- [x] 增加 TLDR、AI 判断、Paper/PDF/Code/Code Search 直达链接。
- [x] 在邮件和页面中展示作者单位，供质量判断和后续反馈学习使用。
- **状态：** in_progress

### 阶段 7：推荐学习闭环
- [x] 将喜欢/不喜欢反馈转换为 section 权重。
- [x] 实现轻量文本关键词 fallback，根据喜欢/不喜欢论文文本调整排序。
- [x] 调整不同栏目权重。
- [ ] 调整作者和工具链权重。
- [x] 调整反馈关键词权重。
- [x] 记录推荐历史，避免重复推荐。
- [x] 推荐本身引入大模型相关性判断，用于最终重排与过滤。
- [ ] 加入简单评估指标：打开率、反馈率、喜欢率、负反馈主题。
- **状态：** in_progress

### 阶段 8：验证与上线
- [ ] 本地或 GitHub Actions 手动运行一次真实 arXiv 完整流程。
- [x] 增加 workflow 契约测试，防止每日流程退回示例 JSONL。
- [ ] 验证 GitHub Pages 能加载当天数据。
- [ ] 验证邮件能收到并正确跳转。
- [ ] 验证反馈写入 Supabase。
- [ ] 验证次日或手动重跑时反馈影响排序。
- **状态：** pending

## 关键问题
1. `ASSASSYN` 的准确论文标题或链接需要用户补充，以便作为 full-stack co-design seed。
2. 邮件服务使用哪一个邮箱服务商，需要按服务商确认 SMTP host、port 和授权码规则。
3. embedding 使用 OpenAI 兼容 API、DeepSeek 兼容服务、还是本地轻量 TF-IDF/SentenceTransformer fallback，需要结合成本和可用性确认。
4. GitHub Pages 是否需要访问密码。如果需要，沿用上游项目的 `ACCESS_PASSWORD` 机制。

## 已做决策
| 决策 | 理由 |
|------|------|
| 基于 `daily-arXiv-ai-enhanced` 改造 | 现有项目已经覆盖 GitHub Actions、AI 摘要和 GitHub Pages，最接近目标。 |
| 使用 Supabase 作为初始反馈存储 | 不需要自有服务器，前端可写入，GitHub Actions 可读取，成本低。 |
| 核心 arXiv 分类为 `cs.AR,cs.PF,cs.DC,cs.PL` | 更贴近体系结构、性能、分布式/HPC 和编译器协同。 |
| `cs.AI,cs.LG` 只作为扩展分类并经过 gate | 用户关注 agentic architecture，但泛 AI/ML 论文噪声很大。 |
| 邮件和页面共用同一反馈入口 | 避免维护两套反馈逻辑。 |
| arXiv 抓取输出 JSONL 后交给现有 pipeline | 保持数据源、推荐排序和反馈学习解耦，便于后续替换或增加 Semantic Scholar/RSS。 |
| 使用 `recommendation_runs` 做重复惩罚 | 不依赖浏览器本地状态，GitHub Actions 可跨天读取历史并减少重复推荐。 |
| TLDR 使用 OpenAI-compatible enrichment 且有本地 fallback | 让邮件和页面更易扫读，同时避免 LLM 服务失败导致每日 workflow 失败。 |
| 推荐排序采用“规则召回 + LLM 判断重排” | 关键词规则保证召回和稳定兜底，LLM 判断负责理解论文是否真正贴合 agentic architecture、co-design、microarchitecture、simulator 和 HPC 交叉兴趣。 |
| 作者单位只做展示和弱质量信号 | arXiv 经常不提供单位，因此不伪造单位；若数据源提供 `affiliations`，页面、邮件、反馈和 LLM judge 都会使用。 |

## 遇到的错误
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| 暂无 | 0 | 暂无 |

## 后续执行原则
- 先做能闭环的 MVP，再逐步提高推荐质量。
- 每次新增数据源或模型前先评估噪声。
- 所有外部研究发现写入 `findings.md`。
- 每个阶段完成后更新本文件和 `progress.md`。
