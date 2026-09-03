# MyriadBench(万机)— 中文导览

> **One model. One session. All tasks.**
> 远未来,AI 将收敛为一个模型:你数字生活的唯一入口,日理万机——一个永远不会结束的会话里,处理数不清的、交织的、互相依赖的任务。
> **今天没有任何 benchmark 在测这件事。**

**唯一核心指标:Myriad Index(MI)** —— 0–100 单个数字,榜单唯一排序键。
**公平性原则:全世界所有模型跑同一个官方套件**——固定题集、固定流程,分数直接可比;未来若逼近满分,发布新的固定套件(版本演进),绝不出现"不同模型跑不同题"。

**战况(实测矩阵,OpenCode Go,seed=7;D=交织密度;每格任务集完全相同,只有事件流不同):**

| 不同会话大小 K 下的 MI | K=2 | K=4 | K=8 | K=16 |
|---|---|---|---|---|
| DeepSeek-V4-Flash,D=0 | **100.0** | **100.0** | 51.5 | 31.7 |
| DeepSeek-V4-Flash,D=0.6 | **100.0** | 33.7 | 33.6 | 42.5* |
| MiMo-V2.5,D=0 | **100.0** | 94.7 | 50.1 | 47.9 |
| MiMo-V2.5,D=0.6 | 40.0 | 85.0 | 50.1 | 33.1 |

*K=16 加中断:agent 激进重排任务"意外"保住了部分分数——这是状态网违约,不是胜利。seed=11 复现:DeepSeek 46.8/34.1、MiMo 53.2/35.5,稳定。
两个任务免费,十六个不免费:干扰税(混合 vs 孤立)从 0.00 涨到 0.93–1.00;中断叠加恶化——除非弱模型干脆在重负载下"偷懒"(MiMo 的"一切已是最新状态"式回复在 trace 里可见)。满分在结构上拿不到;MI 越高越真实,因为每成分都锚定模型自己的孤立基线,无法背题。

## Quick Start(Python 3.10+,零依赖)

```bash
# 1. 生成混合会话 + 每任务孤立基线(同 seed,可复现)
python -m harness.cli generate --out data/generated --mix-id demo --seed 7 \
    --K 8 --H 0.6 --D 0.5 --DEP 0.4 --IR 0.3 --NV 0.2 --tier S

# 2. 跑模型(OpenAI 兼容端点,MYRIAD_API_KEY)
python -m harness.cli run --session data/generated/sessions/demo-s7.json \
    --agent openai --model gpt-4o-mini --out data/results \
    --with-isolated data/generated/isolated

# 3. 出报告:MI + 全部分解
python -m harness.cli report --session data/generated/sessions/demo-s7.json \
    --trace data/results/demo-s7-openai.json \
    --isolated data/results/isolated --out data/results

# 自检
python -m unittest discover -s tests
```

没有 key 也能跑通全流程(`--agent echo` 见下限)与上限(种子测试的满分脚本)。

## MI 怎么算(权重公开固定)

| 成分 | 权重 | 含义 |
|---|---|---|
| R 会话保留率 | 40% | 混合 vs 孤立的表现保持(IC = 1−R) |
| S 状态保持 | 30% | 依赖网一致(SWC)+ 中断恢复(RF) |
| T 长尾稳健 | 20% | 最难一族(ρ=3/4)的保持率 |
| E 预算效率 | 10% | 每 token 产出 vs 孤立基线 |

未受压的轴不计入分子分母——摆烂 agent 约 0 分,没有保底分;无孤立基线则拒绝出分。精确定义见 `docs/metrics.md`。

## 文档索引

- `docs/design.md` 协议与原则 | `docs/data-format.md` 数据格式 | `docs/metrics.md` 指标与向前兼容
- `docs/survey.md` **相关工作总结 + gap 分析(中文,立项依据)**
- `docs/experiment-plan.md` **小预算 pilot 方案(OpenCode Go)** | `docs/naming.md` 命名调研
- `docs/runbook-publish.md` 发布路线图(GitHub / arXiv / HF)
- `data/seeds/` 三个手工种子会话(A 轻交织 / B 依赖网 / C 长程+注入)
- `papers/arxiv_v1.md` 论文骨架(摘要 + Table 模板 + 假设 H1–H5)

## 状态

v0.1:协议 + 生成器 + runner + 验证器 + MI 套件 + 10 家族 + 3 种子会话 + 32 测试全绿。
v0.2(待跑):OpenCode Go 小预算 pilot → 论文数据与首版榜单。