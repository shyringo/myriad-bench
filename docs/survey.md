# MyriadBench 立项调研报告(中文)

> One model. One session. All tasks. —— 单会话极致多任务的评测空缺
> 2026-08, v0.1

## 0. 核心论点

AI 的远未来收敛形态是:**一个模型/agent 作为人类数字生活的唯一入口,在同一个长会话中处理数量级上不可数的、异构的、互相交织的任务**。此时"多任务"不再是 N 个独立任务的并集,而是一个**任务连续体**(task continuum):

- 任务种类不可枚举(数不清)→ 评测必须基于**开放任务空间**,而非封闭任务清单;
- 任务在**同一会话中交织**,存在上下文切换、中断、挂起/恢复、优先级抢占、跨任务依赖;
- 会话**无限延长**,上下文与状态持续累积,存在遗忘、干扰、状态漂移、上下文资源耗尽;
- 能力的本质问题是:**极值多任务下的性能保持率**。

本调研回答:(1) 业界/学界是否已有此范式的评测?(2) 最近的邻居们覆盖了什么、漏了什么?(3) MyriadBench 的定位与差异。

**结论先行:没有。现有评测全部落在"平行多任务"(parallel multi-task)或"单任务长程"(single-task long-horizon)两个极端;没有任何系统以"单会话内异构任务极致混合"为主要测量量。** 最近邻是个人助理类评测(PAUSE、π-Bench、ASTRA-bench)与任务干扰研究(EMNLP 2024),前者域受限、任务浅,后者只在玩具规模证明了现象的存在。

## 1. 相关工作全景(按评测范式分类)

### A. 静态/平行多任务知识评测(closed, single-turn, tasks in parallel)

| 基准 | 形式 | 局限(对本目标而言) |
|---|---|---|
| MMLU / MMLU-Pro | 选择题多领域 | 无会话、无状态、无工具;任务间零交互 |
| Humanity's Last Exam (HLE) | 极难问答 | 同上 |
| GPQA | 专家级科学问答 | 同上 |
| ARC-AGI | 抽象推理 | 单任务类型 |
| BIG-bench / Natural Instructions | 千级任务集 | 任务分散独立,无交织;用于训练/单测,非会话评测 |
| C-Eval / SuperCLUE(中文) | 静态知识 | 同上 |
| MT-Bench / Chatbot Arena | 多轮对话质量 | 聊天气质,非任务执行 |

> 这类评测的"multi"是**有限枚举的平行集合**;评测对象是单轮能力,不是"在一个会话里同时扛住一堆事"的能力。

### B. 单任务/单域长程 agent 评测(single-task long-horizon)

| 基准 | 域 | 形式 | 局限 |
|---|---|---|---|
| SWE-bench 系列 | 代码库 | 单 issue 修复 | 单任务、单域 |
| WebArena / WebVoyager / Mind2Web | 网页 | 单目标浏览 | 单域、目标单一 |
| OSWorld / OSWorld 2.0 / WindowsAgentArena | 桌面 OS | 单工作流(2.0 为长程) | 单工作流即"一个任务",域仍为计算机操作 |
| τ-bench (Sierra, ICLR 2025) | 零售/航空 | 工具-用户-策略交互,数据库状态验证 | 任务单目标;多域也只是"两种客服场景" |
| GAIA | 通用问题 | 每问一任务,工具+推理 | 问题彼此独立,无会话累积 |
| AssistantBench (EMNLP 2024) | 网页研究 | 214 个耗时任务 | 每任务独立 session |
| MLE-bench (OpenAI) | ML 工程 | 24h 单任务 | 长但"单" |
| Long-Horizon Terminal-Bench (LHTB) | 终端 | 46 个长程任务,密集奖励 | 单任务/单域 |
| OdysseyBench | 办公软件 | 长程复杂工作流 | 域为办公应用;多步骤但仍单目标 |
| MCP-Bench | MCP 工具 | 250 工具跨域 | 任务仍为原子式单目标 |
| WeaveBench | 混合界面 | 114 个长程任务 | 同上 |

> 这类评测的"多"体现在**多任务样本**(数据集规模),而非**多任务同时/交织存在于一个会话**。长程≠多任务。

### C. 长上下文 / 长记忆评测

| 基准 | 测量 | 局限 |
|---|---|---|
| LongBench v2 / RULER / HELMET / InfiniteBench | 长上下文检索与推理 | 被动读取,无主动执行 |
| Loong (arxiv 2406.17419) | 多文档 QA | 任务类型单一(QA),非 agent 会话 |
| AgentLongBench (arxiv 2601.20730) | 长上下文 agent | 侧重检索,任务异构度低 |
| LongMemEval / Memora (ACL 2026 Findings) | 跨周/月记忆 | 记忆=事实召回,任务浅 |
| RealMem (ACL 2026 Findings) | 项目制长程记忆 | 单项目主线 |
| AgentMemBench (arxiv 2608.00009) | 记忆策略对比 | 策略评测,非能力评测 |
| TOKENS (ICLR 2026) | 跨轮一致性(指令遵循、事件排序、矛盾消解) | 对话层能力,非任务执行 |

> 这类评测关心"上下文/记忆"这一**单轴**,而 MyriadBench 关心"多任务 × 状态 × 上下文"的**多轴交互**。

### D. 多域对话评测(表面最接近)

| 基准 | 形式 | 局限 |
|---|---|---|
| MultiWOZ 2.x / 3 / Multi2WOZ / MULTI3WOZ | 多域任务型对话(订酒店+找餐厅+问路) | "域"共享同一对话本体(slots),任务浅(填槽),无执行、无真实状态、无长上下文;领域数 ≤10 |
| Schema-Guided Dialogue | 同 | 同上 |
| τ-bench | 客服单域 | 已归入 B |

> 关键区别:MultiWOZ 的"多域"是**同一类任务(信息查询/预订)的不同槽位组合**,不是异构任务;MyriadBench 的"多任务"是**写代码、做研究、排日程、写邮件、数据分析的异质混合**。

### E. 个人助理/统一服务环境评测(最近邻!)

| 基准 | 内容 | 覆盖 | 与 MyriadBench 的差异 |
|---|---|---|---|
| PAUSE (arxiv 2607.27354) | 统一服务环境中的个人助理:持久用户状态、配置、权限、跨服务长程交互 | 用户状态推理 | 域集受限(服务/配置/权限),任务为"服务请求",不追求任务种类不可数;无干扰/切换度量 |
| π-Bench | 长程多会话工作流,5 人格化角色、隐藏意图、主动服务(Proactivity/Completeness) | 主动性与完成度 | 100 任务、5 persona,单任务一线索;不测跨任务干扰;会话内任务数小 |
| ASTRA-bench (arxiv 2603.01357) | 2413 场景,时间演进个人上下文 + 工具 + 多步意图 | 事件驱动生成 | 上下文时间演进但任务仍为"个人助理请求"型;异构度有限 |
| VitaBench (arxiv 2509.26490) | 真实应用中的交互任务 | 交互 | 任务域现实但每任务独立 |
| Auto-SLURP | 多 agent 框架评测 | — | 方向相反(多 agent 编排),而远未来收敛于单 agent |

> PAUSE/π-Bench/ASTRA-bench 证明"统一环境 + 持久用户状态 + 长程"的评测范式已出现,但**它们的任务空间是"个人服务"外壳内封闭的、每会话任务数小(个位~十位)、不测切换代价与干扰、不求任务种类不可数**。MyriadBench 把它们打开:任务空间开放注册、会话内任务数可到百级、显式度量干扰/切换/恢复/长尾。

### F. 任务干扰 / 多任务行为研究(现象证据)

| 工作 | 结论 |
|---|---|
| "LLM Task Interference" (EMNLP 2024 main, arxiv 2402.18216) | 会话历史中任务切换可导致显著性能下降;5 数据集 15 种切换 |
| "Degradation of Multi-Task Prompting Across Six NLP Tasks" (Electronics 2025) | 6 个 NLP 任务并入单 prompt 即性能劣化 |
| "SFT Conflicts, RL Coexists" (arxiv 2608.03573) | 训练侧:多任务 SFT 有任务冲突,RL 更新正交 |
| "Mitigating Cross-Task Interference in Multi-Task Instruction Tuning" | 训练侧干扰的成因与缓解 |

> **这些工作证明了"干扰"是真实且可测量的现象,但全部停留在玩具规模(单 prompt、6 任务、NLP 分类层)。没有任何工作把干扰/切换/恢复提升为体系化的、开放任务空间下的评测协议。** 这正是 MyriadBench 的立足点。

### G. 一般智能体 / 开放生成方向(方法论借力)

| 工作 | 可借鉴 |
|---|---|
| OMNI-EPIC (ICLR 2025) | 程序化环境生成,开放任务连续体的生成哲学 |
| GTA (ACL 2026) | 大规模长程 web 任务自动生成管线 |
| MultiNet v1.0 / General-Level & General-Bench / OmniBench / MEGA-Bench | 异构 VLM/VLA 通用性评测;模态多样性即"任务多样性"的另一面 |
| General Agent Evaluation (arxiv 2602.22953) | 跨异构协议统一评测的工程方法 |
| AIOS (arxiv 2403.16971) | "Agent 作操作系统"的架构隐喻(调度/上下文切换),MyriadBench 借用其词汇表:进程=任务、调度=事件流、上下文切换=切换代价、内存=状态 |

### H. 终身学习/持续学习(相邻但不同)

LifelongAgentBench、LLM 持续学习综述(arxiv 2501.07278)等关心**训练侧**随时间学新任务不忘旧任务;MyriadBench 关心**推理侧单会话内**的状态保持。二者互补:会话内遗忘(上下文坍缩)与训练侧灾难性遗忘是不同机制。

## 2. Gap 分析:为什么说"没有"

把现有工作投影到四个轴上:

| 轴 | 现状 | 空缺 |
|---|---|---|
| **任务空间开放性** | 封闭清单(MMLU 57 域、MultiWOZ 10 域、π-Bench 100 任务)或单域(代码/网页/办公) | **开放注册 + 程序化组合 + 新奇混合分布**的评测 |
| **会话内任务数 K** | K=1(长程单任务)或 K≤10(多域对话/助理) | **K=数十~数百的混合会话协议** |
| **任务异构度 H** | 同构(同域同本体)或平行无关(静态题库) | **同会话异构交织(代码+研究+日程+写作+数据)**,以及显式的 H 控制变量 |
| **干扰/切换/状态度量** | 现象研究(玩具 NLP 任务);工程系统(缓存/压缩)无标准化度量 | **体系化指标:干扰系数、切换代价、恢复保真、状态网一致性、长尾稳健性** |

**结论:范式空缺确认。** 没有任何一个公开 benchmark 把"单会话内、开放任务空间、极致混合交织、显式度量干扰与状态保持"作为评测对象。最近邻(PAUSE/π-Bench/ASTRA-bench)证明范式可行且受欢迎;任务干扰研究证明现象显著。**方向正确、空地存在、奠基时机成熟。**

## 3. MyriadBench 定位

> **MyriadBench(万机):超越多任务的评测 —— 度量 agent 在单会话内处理不可数、异构、交织任务的极限。**

- 对象:单 agent 实例(远未来形态),而非多 agent 编排;
- 载体:单会话事件流 + 持续世界状态(工作区/日历/邮箱/数据源/代码仓);
- 任务空间:开放家族注册表 + 程序化混合生成,"数不清"由**组合爆炸 + 动态注入 + 新奇分布**实现;
- 指标:干扰系数、切换代价、恢复保真、状态网一致性、长尾稳健性、上下文预算效率(详见 `metrics.md`);
- 产出:协议规范、数据生成器、评测 harness、种子数据、初版结果(后续接入模型 pilot)。

## 4. 引用锚点(写论文时用)

τ-bench (arXiv:2406.12045, ICLR 2025);AgentBench (arXiv:2308.03688);HELM (arXiv:2211.09110);AssistantBench (arXiv:2407.15711, EMNLP 2024);GAIA (arXiv:2311.12983);Loong (arXiv:2406.17419);OSWorld (arXiv:2404.07972);MLE-bench (arXiv:2410.07095);MultiWOZ (arXiv:1810.00278);LLM Task Interference (arXiv:2402.18216, EMNLP 2024 main);AIOS (arXiv:2403.16971);OMNI-EPIC (arXiv:2405.15568, ICLR 2025);PAUSE (arXiv:2607.27354);π-Bench (github.com/Simplified-Reasoning/Pi-Bench);ASTRA-bench (arXiv:2603.01357);VitaBench (arXiv:2509.26490);General Agent Evaluation (arXiv:2602.22953);AgentLongBench (arXiv:2601.20730);Memora (ACL 2026 Findings);RealMem (ACL 2026 Findings);AgentMemBench (arXiv:2608.00009);GTA (ACL 2026);MultiNet v1.0 (arXiv:2512.11315);LHTB (github.com/zli12321/LHTB);OdysseyBench (OpenReview tMbmBCfSTz);WeaveBench (weavebench.github.io);LifelongAgentBench / 持续学习路线图 (arXiv:2501.07278);SFT Conflicts, RL Coexists (arXiv:2608.03573)。

*注:引用信息以正式检索为准,发布前逐条核对。*