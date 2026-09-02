# 发布路线图(GitHub → HF → arXiv)

> 本文件是你醒来后可以直接照做的清单。所有"对外发布"动作(创建仓库、push、投稿)
> 都留给你本人确认后执行 —— 代码和内容已全部就绪。

## 0. 发布前自查(已就绪项)

- [x] 代码零依赖、29 个测试全绿
- [x] README(EN)+ docs/README-zh.md
- [x] LICENSE(MIT 代码 + CC BY 4.0 数据)
- [x] provenance.md(原创性声明,发布必须)
- [x] docs/survey.md(调研报告)、design.md、metrics.md
- [x] 三个手写种子会话 + 10 个任务家族 + 生成器
- [x] 本地 git 历史干净(见下,提交信息均为纯工程描述)

## 0. 发布仓库策略(重要)

本地开发库(含草稿/历史/内部文档)保留原样;公开仓库用**干净 release 仓库**:

```bash
mkdir /tmp/myriad-release && cd /tmp/myriad-release
git init -b main
# 只复制:README.md LICENSE CONTRIBUTING.md .gitignore assets/
#         data/ docs/ harness/ spec/ tests/ scripts/(papers/ 可选,建议投稿后放)
# 不复制:.git/ docs/汇报-夜间工作.md data/pilot/ data/results/ data/generated/
git add -A && git commit -m "MyriadBench v0.1: single-session, unbounded multi-task benchmark protocol"
```

理由:本地历史含内部交接 commit(skill 要求公共历史零私人痕迹);干净仓库零风险。

## 1. GitHub 发布(约 10 分钟)

```bash
# 1) 登录
gh auth login                    # 或 gh auth status 检查

# 2) 建仓库(名称: myriad-bench;描述中英各一句,要求:吸引眼球 + 数据钩子)
gh repo create myriad-bench --public --source . --remote origin --push

# 3) GitHub 设置页补:
#    Description(英文,首行): The benchmark for the day in the life of one AI: how much
#    of a model's ability survives an endless session of countless interleaved tasks?
#    One ranking index (MI). Pilot numbers forthcoming.
#    Description(中文,第二行): 一个 AI 的一天:数不清的混合任务在一个会话里交织,
#    它还能保住多少?唯一指数 MI 排序。实测数据发布中。
#    Topics: llm-evaluation, benchmark, agents, multitasking, agi, llm-agents,
#            evaluation-benchmark, session
#    Homepage: 留空或挂 GitHub Pages(可选)
#    Social preview: Settings → Social preview 上传 assets/hero.png
#    (先本地裁成 1280x640 再传,避免压缩失真)
```

🚨 **承诺前审一遍公共表面**:commit messages、README 中的 `github.com/<you>` 占位符、
`papers/` 里的草稿不需要进公开仓库(建议把论文草稿放私有仓库或本地,公开仓库只留
`docs/whitepaper.md` 的精修版或在论文投稿后再附)。

## 2. 首发内容建议(让 star/讨论起来)

1. **先发 README + 种子会话 + 一张 demo 图**:`docs/` 里加一页
   `VISUALS.md` 放 IC/SWC 横条图(用数据跑一次 pilot 后画)。
2. **发布 3 个种子会话的 replay trace** 到 `data/results/`,让用户不用 API key
   也能看到完整 transcript + 指标输出(可运行示例即传播力)。
3. **Hugging Face 数据集**(v0.2 生成 100+ 会话后):
   - 仓库名 `myriad-bench`,Dataset Card 写清 schema、seed、contamination 策略;
   - 国内用户友好:同时传 ModelScope(可选)。
4. **awesome-* 列表**(等 v0.2 论文/榜单后再投):
   - awesome-llm-evaluation、awesome-agent-benchmarks 等;投 PR 前先看各自规则。

## 3. 论文(arXiv)

1. `papers/arxiv_v1.md` 已有完整提纲 + 摘要初稿;v0.2 pilot 数据出来后填结果。
2. 投稿前核对 `docs/survey.md` 引用锚点(逐条打开确认编号与作者)。
3. 同时投 NeurIPS/ICML Datasets & Benchmarks Track 或 ACL ARR;arXiv 先占坑。
4. 论文主张务必只基于公开可复现的 demo 命令。

## 4. 发布后 48 小时

- [ ] 在 HF 数据集页发一条 factual Discussion(按各平台规则,不自夸)
- [ ] X / 微博 / 即刻各一条原生文案(不跨帖复制);标题钩子建议:
      "MMLU measures how well a model answers questions. IC measures how well
      it survives its own day." (可用,但发布时再校准)
- [ ] 记录 issue 里的第一波问题 → 收进 README FAQ

## 5. 合规备忘

- 发布即视为你确认:内容无私人信息、无未授权数据、无夸大宣传。
- 任何删除(含 fork 清理)都按你的全局规则先征求同意。