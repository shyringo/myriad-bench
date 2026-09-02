# 发布前最终检查清单(v1 审核用)

> 你醒来逐条打勾。全部通过 → 发布。

## A. 内容与承诺

- [ ] **README 价值一句话成立**:开头 3 段讲清"远未来单一 AI 入口 → 没人测一个 agent 的一天 → MyriadBench 是第一个",无空话
- [ ] **Quick Start 在开头之后立即出现**,三条命令复制即跑,零依赖
- [ ] **无编造数据**:README/论文没有任何虚构的模型分数;战况块为"pilot 进行中"占位;合成 agent 数字(内部校准)不出现在公开文档
- [ ] **公平性表述成立**:全世界同跑一个官方套件;版本演进 = 新固定套件,不是不同模型不同题(metrics.md §8)
- [ ] **无法背题表述成立**:MI 锚定模型自己的孤立基线(E/R 轴)+ 结构不变量(SWC/RF/T)
- [ ] 中文名「万机」只出现在中文场合(README-zh 标题、传播文案)

## B. 仓库卫生(audit)

- [ ] **git 历史无私人痕迹**:已 untrack 内部交接文档(磁盘保留);commit messages 全部为工程描述
- [ ] **发布仓库策略**:本地开发库(含历史)保留;发布用**干净 release 仓库**:
  ```bash
  mkdir ~/tmp/myriad-release && cd ~/tmp/myriad-release
  git init -b main
  # 复制 README.md LICENSE CONTRIBUTING.md .gitignore assets/ data/ docs/ harness/ spec/ tests/ scripts/
  # 不要复制:docs/汇报-夜间工作.md、data/pilot/、data/results/、data/generated/、.git/
  git add -A && git commit -m "MyriadBench v0.1: single-session, unbounded multi-task benchmark protocol"
  ```
- [ ] 合成演示数据(data/pilot/)不会进入发布(release 仓库手工复制即可保证)
- [ ] LICENSE = MIT(代码)+ CC BY 4.0(数据);provenance.md 三项分类齐全

## C. GitHub 元数据(发布当天)

- [ ] Repo 名 `myriad-bench`,描述(中英两行,见 runbook-publish.md §1)
- [ ] Topics:`llm-evaluation`,`benchmark`,`llm-agents`,`multitasking`,`evaluation`,`agent-benchmark`,`session`,`myriad`
- [ ] **社交预览图**:把 `assets/hero.png`(2880×720)在仓库 Settings → Social preview 上传(GitHub 会裁成 1280×640,可先本地裁一版)
- [ ] License 显示 MIT;README 自动渲染(检查图片路径 assets/hero.png、how.png 显示正常)

## D. 灰度发布(suggested)

1. 不发 arXiv、不发推广贴,先发 GitHub 私仓/Public 观察 48h
2. 等 pilot 数据(网络恢复后 `python scripts/run_pilot.py`)→ 更新 README 战况块 + 图(visuals.py)→ 再公开发布 + arXiv
3. 发布后 smoke:全新机器 clone → Quick Start 三命令 → 出 MI 报告

## E. 内容红线(最终确认)

- [ ] 无任何"Pilot 前"版本的数字出现在 README/简介/图里
- [ ] 论文草稿(arxiv_v1.md)只有待填占位,无实测声明
- [ ] README 里 `<you>` 占位符已替换或发布前替换
- [ ] 一切 claims 均可从仓库命令复现(Quick Start + tests)