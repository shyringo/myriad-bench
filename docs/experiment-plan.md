# 小预算实验方案(v0.2 pilot → arXiv v1 数据)

> 目标:**用极少 API 资源,产出尽可能详实、可复现、能撑起一篇 arXiv 论文的测试结果。**
> 约束:OpenCode Go 套餐($10/月,模型池+配额,2026-08 检索值,执行前以官方页复核)+ 少量备用资源(Codex 保留不用)。

## 0. 一键执行(网络就绪后)

```bash
python scripts/run_pilot.py                      # 默认 deepseek-v4-flash × 3 混合
python scripts/run_pilot.py --K 4 --D 0.6        # 单格试跑
python scripts/visuals.py --root data/pilot --out data/pilot/figures   # 出图
```

- key 解析顺序:--api-key > MYRIAD_API_KEY > ~/.pi/agent/auth.json(opencode-go)
- 端点:https://opencode.ai/zen/go/v1(chat/completions 兼容),模型 ID 见 §1 表
- **网络**:opencode.ai 需可访问国际网络;harness 自动探测并复用系统代理
  (127.0.0.1:7890 等),Clash 系代理开着即自动走;不开代理则直连尝试

## 1. 资源盘点

**OpenCode Go($10/月)模型池与配额**(opencode.ai/go,2026-08):

| 层 | 模型(Go 模型 ID) | 配额(5h/请求) | 角色 |
|---|---|---|---|
| 便宜层 | `mimo-v2.5` / `deepseek-v4-flash` / `qwen3.8-flash` / `glm-5.3-flash` / `minimax-m3` | 30.1K / 7.6K / 5.4K / 1.58K / 3.2K | 全矩阵主力 |
| 中坚层 | Grok 4.6 / GLM-5.3 / Kimi K2.7 Code / Qwen3.7 Max 等 | ~1.35K–4.3K | 精选矩阵 |
| 旗舰层 | **`gpt-5.6-luna`** / `kimi-k3` | ~2.05K / 110 | 旗舰混合,一个两格 |
| 后备 | OpenCode Zen(按 token 付费,无加价) | — | 配额不足时补充 |
| 不用 | Codex / 自备 API | — | 留给 tier-L 与后续版本 |

**一句话预算结论:全计划 ≈ 2,300 次 API 调用,便宜层模型单格成本趋近于 0,GPT 5.6 Luna 只占其配额 ~8%,Kimi K3 占其配额 ~40%(还在安全线内)。**

## 2. 设计原则:一鱼多吃

1. **一次运行 = 全部六项指标。** trace 已内置一切:checkpoint 探针(→SC)、中断前后快照(→RF)、读写日志+产物哈希(→SWC)、rarity(→LTR)、usage(→BE)、逐轮环境快照(→切换放大图)。**没有"只为一个指标而跑"的运行。**
2. **孤立基线是 IC 的对照,必须与混合同模型、同温度、同种子** —— 这是测量"多任务税"的严格对照,不省。
3. **消融内建于矩阵**:D=0 vs D=0.6 两档,同一 K —— 一次实验同时分离"交织干扰"与"中断恢复"两个机制的贡献。
4. **零成本附加分析**(不花一个 API 调用):token 累计曲线、错误模式规则分类(重复读/未读先写/路径漂移/答非所问)、warm/steady 放大图、按家族的 SC 聚合。

## 3. 实验矩阵

混合生成:seed 固定(7),家族池固定,`DEP=0.3, NV=0.2`;K、D 为自变量。每格成本 = 1 次混合运行 + K 次孤立运行 ≈ (K+1) 个 trace。

| 模型层 | 模型 | K=4, D=0.6 | K=8, D=0 | K=8, D=0.6 | 小计 calls |
|---|---|---|---|---|---|
| 便宜 ×3 | DeepSeek V4 Flash, MiMo-V2.5, Qwen3.8 Flash | ✓ (5 runs) | ✓ (9 runs) | ✓ (9 runs) | 3 × ~280 |
| 中坚 ×1 | Grok 4.6 | — | ✓ | ✓ | ~200 |
| 旗舰 | GPT 5.6 Luna | — | — | ✓ (9 runs) | ~120 |
| 旗舰(探奇) | Kimi K3 | ✓ (5 runs) | — | — | ~45 |

- 合计 ≈ 2,300 calls;**最坏情况(全部模型×全格)也能用便宜层单模型全矩阵兜底(≈280 calls)**,即可出论文主表的最小区块。
- calls 估算口径:混合 run ≈ 18–40 turns/次调用(每次 agent.step 一次);孤立 run ≈ 3–10 turns。上限按 40/10 估。

## 4. 结果呈现(论文骨架,已写入 papers/arxiv_v1.md)

- **Table 1 主表**:行 = 模型,列 = {K,D} 档 → IC / SC_first / SC_same / RF / SWC / LTR(ρ=1..4) / BE(tokens per pass)。
- **Table 2 家族级 IC**:哪些家族在混合中受害最深(预期:code_fix 在中断下最脆;math_word 无工具最稳)——"注意力碎片化"的异质性证据。
- **Table 3 消融**:D=0 vs D=0.6 的 ΔIC → 分离"交织"与"中断"贡献;同表给 RF(只存在于 D>0)。
- **图 1**:IC vs K 曲线(D 两档,便宜层 3 模型三条线)——论文主图。
- **图 2**:一个代表性 transcript 的 SC 放大(warm 窗口探针失败 → steady 成功),附错误模式标注。
- **附录**:全部 trace + metrics-*.json 作为 release assets(数据量小,几十 MB 内),复现命令逐条给出。

## 5. 执行清单(bash)

```bash
export MYRIAD_API_KEY=...   # OpenCode Go / Zen 的 key
# 全矩阵生成(一次性)
for cfg in "g1:4:0.6" "g2:8:0.0" "g3:8:0.6"; do
  IFS=: read mix k d <<< "$cfg"
  python -m harness.cli generate --out data/generated --mix-id $mix --seed 7 \
      --K $k --D $d --DEP 0.3 --NV 0.2 --tier S
done
# 每模型:便宜层三模型跑三格;中坚/旗舰按矩阵跑
for model in deepseek-v4-flash mimo-v2.5 qwen3.8-flash; do
  for mix in g1 g2 g3; do
    python -m harness.cli run --session data/generated/sessions/$mix-s7.json \
        --agent openai --model $model --base-url $GO_BASE_URL --out data/results/$model \
        --with-isolated data/generated/isolated
    python -m harness.cli report --session data/generated/sessions/$mix-s7.json \
        --trace data/results/$model/$mix-s7-openai.json \
        --isolated data/results/$model/isolated --out data/results/$model
  done
done
# 汇总表:python scripts/make_tables.py(见 §7)
```

模型字符串/端点需在 Go 接入后按实际值填写($GO_BASE_URL、精确 model id 以 OpenCode 文档为准)。

## 6. 风险与兜底

| 风险 | 兜底 |
|---|---|
| 配额口径与页面上不同 | 先用便宜层单格试跑 20 calls,核对 usage 计数;经费充裕时用 Zen 按量补 |
| 某些模型端点非 OpenAI 兼容 | harness 的 OpenAICompatAgent 支持任意 base_url;如纯 TUI 型,先写 30 行适配器(gitrepo 有 example) |
| 长会话超时/断连 | runner 有 max_total_turns 护栏 + 断点续跑(按 event 分段,重启 agent 继续,已在设计);trace 可部分可用 |
| Kimi K3 110 配额被拒 | 该行降级为可选;主结论不依赖它 |
| 结果"全是高分/全低分"不可信 | 附录须含 3 条人工复核的 transcript 片段(定性证据),并在论文中写 agent 实际回复样例 |

## 7. 附加工程(小而关键)

1. `scripts/make_tables.py`:读 data/results/*/metrics-*.json,输出 LaTeX 表格 + markdown 表(论文直接用)。
2. `scripts/plot_curves.py`:matplotlib 画 IC vs K(装到 D:\SoftwaresSetup 的 conda env,符合环境规则)。
3. 错误模式分类器(`harness/analysis.py`,v0.2):基于 trace 的规则分类,零 API 成本。
4. trace 导出为 release assets 的归档脚本。

## 8. 结论

**最低可行(烂船也有三斤钉):DeepSeek V4 Flash 单模型 × 3 混合 ≈ 280 calls ≈ $1 级成本 → 即可产出主表 1 行 + 图 1 一条曲线 + 消融 + 全部零成本分析。** 预算翻倍后覆盖 3 便宜 + 1 中坚 + GPT 5.6 Luna,论文数据丰满度足够 peer review 用。