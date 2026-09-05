# 命名:调研与最终决策

> **最终决策(2026-08):官方名 = MyriadBench(唯一名字)。**
> 「万机」仅作中文语境下的译名,绝大多数场合不需要出现(见 §4)。
> 核心指标 = **Myriad Index (MI)**,与产品名完全一致。

## 1. 热度视角的最终 review(2026-08 实查)

**结论:未发现比 MyriadBench 更好的方案,正式启用。**

候选热度的核查结果:

| 候选 | 热度/撞名核查 | 裁决 |
|---|---|---|
| **MyriadBench** | LLM/agent benchmark 领域**零同名**;"Myriad Index" 无 AI 排名撞名。注意项:旧金山合规 AI 公司 Myriad Technology Inc.(myriad.ai,约 30 人)于 2026-02 申请了 "MYRIAD" 商标(软件服务类,非终局状态)| **启用**。风险判断:领域完全不同(学术评测 vs 企业合规 SaaS),"MyriadBench" 带 -Bench 后缀已与其裸词商标区分,且学术 benchmark 存在大量同类先例(GAIA/HELM/ARC 均有非学术同名),实际冲突概率极低;若未来出现实质纠纷,改名窗口仍在(发布初期) |
| WanjiBench | 无同名,但 2026 年"万"字头评测已被 Wan-Bench 2.0(阿里)、WBench(美团)、万智(零一万物)占用 | 淘汰 |
| OSBench / OneSessionBench | OS 隐喻好,但易与 OSWorld 混淆,且"OneSession"过于描述性 | 淘汰 |
| OmniTask / OmniSession | "Omni" 前缀已被 OmniBench/OmniEPIC 等占满,辨识度低 | 淘汰 |

命名规律佐证(2026 领跑者):Arena(单字品牌)、GAIA(神话单字 + 开头悬殊数据:人类 92% vs GPT-4 15%)、τ-bench、Artificial Analysis("一个 Index 说话")。
**MyriadBench 的配方:myriad = "无数"(名字即是论文命题 a myriad of tasks)+ -Bench 标准后缀 + 单数核心指标 MI。**

## 2. 为什么是 myriad

源自古希腊语 *myrioi*(一万);英语常用词,意为"无数、数不清",可作名词/形容词;与道家 "ten thousand things"(万物)意象同源——与"数不清的任务"宇宙观一致。发音 my-ri-ad,好念、好拼、好搜。

## 3. 一致性要求(产品名 = 指标名)

- Benchmark 名:**MyriadBench**
- 核心指标名:**Myriad Index(MI)** —— 与产品名同源,全世界只有一个名字体系
- 环境变量:MYRIAD_API_KEY;域名占位:myriad-bench.dev;repo:myriad-bench
- 中文译名「万机」只允许出现在必须使用中文的场景(中文导览、中文传播文案)

## 4. 中文名使用原则

「万机」(日理万机)是中文译名,不是第二个名字。使用规则:

- **英文语境(README、GitHub 简介、论文、代码):一律 MyriadBench,不出现中文名**;
- 必须以中文呈现时(中文导览 docs/README-zh.md、中文帖子):标题可写 MyriadBench(万机);
- 指标在中文中直写 MI,不译名。

## 5. 传播句

- 中文:"日理万机,不再是一句成语。MyriadBench 正在把它变成可以测量的东西。"
- 英文:"MMLU asks how well a model answers. MyriadBench asks how well one agent survives its day."
- 数据钩子(等真实 pilot 数据):"Frontier models score in the 20s–40s on the day-of-one-AI test — how much of their ability survives a single mixed session?"(以实测为准)

## 6. 爆火(virality)角度 review —— 最终确认

用户追问:哪个名字最能帮项目**风靡全球**?三轮 review 结论:名字本身无更优解,
爆火的真正引擎是「名字的可传播性 × 可视化 × 数据钩子」的组合。

- 可传播性:MyriadBench 三音节、英语常用词、m 开头(logo 友好)、"myriad of
  tasks" 本身就是一句口号。对比:WanjiBench(不可发音拼写)、Omni*(已被占)、
  OS*(与 OSWorld 混淆)。无更好候选。
- 命名决定不改。把火力集中在:AA 式深色可视化(figures 套件)+ 开场悬殊数据
  (真实模型低分,以 pilot 实测为准)+ 一句话使命(One model. One session. All tasks.)。
