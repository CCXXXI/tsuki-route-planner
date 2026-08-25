# 月姬（NScripter）路线解析与全收集流程生成

从游戏明文剧本 `0.txt`（NScripter/ONScripter 格式，15 万行）解析出机器可读的路线分支图，
用符号执行 + 集合覆盖 + 存档复用搜索，生成**全剧情无遗漏、操作最少化的攻略流程单**。

## 最终交付

**`plan3.md`** —— 存档复用版流程单：

- **9 个周目**（= 结局数，理论下界；每条线 TE/GE 各一，琥珀单结局）
- 103 条单选项支线 + 20 组多步支线，全部 inline 在主线选项点处（save → 支线 → load 回来继续）
- 只需 **6 个存档栏位**（区间图着色回收复用，栏位事件流已验证）
- 覆盖 **450/450** 个可达场景（按实际执行段验证）+ 月蚀特别篇
- 验证全部脚本化：每条路径在对应全局进度下逐块模拟复现

## 管线（按数据流向）

| 脚本 | 作用 | 输出 |
|---|---|---|
| `parse2.py` | 解析 0.txt → 块/场景/条件/选项/效果 图 | `flow_graph.json` |
| `reach2.py` | 32 种全局进度上下文 × 带见证 BFS（约 5000 万状态） | `reachability.json`, `witnesses.json`* |
| `rebuild_v2.py` | 结局候选周目 + 贪心集合覆盖 + 支线发现 | `plan_stage1/2/3_v2.json` |
| `pipeline_v3.py` | 9 周目版：支线重算 + 存档复用合并 + 宽松挂载 | `plan_stage1/2/4_v3.json`, `attach_v3.json` |
| `merge_runs.py` | （v3 已并入 pipeline_v3）状态兼容存档复用 | `plan_stage4.json` |
| `attach_bukou.py` | （v3 已并入 pipeline_v3）补课→支线 | `attach.json` |
| `gen_plan3.py` | 渲染最终文档 + 栏位回收 + 全部验证 | `plan3.md` |

\* `witnesses.json`（15MB）未入库：`python reach2.py` 约 5 分钟可重新生成。

## 关键机制结论（从脚本实证）

- 分支全部集中在 467 个 `*fNNN` 流程块；14 万行场景正文无任何分支
- 路线门控只读 5 个全局变量（`cleared/clear_ark/clear_ciel/clear_hisui/ark_normalcleared`）
- 解锁顺序：一周目只能表线（Arc/希耶尔）→ 任一通关开里线（f46 门）→ 翡翠 TE 后开琥珀线（f321）→
  Arc GE 需 TE 先通（f199/f503）、翡翠 GE 需 TE 先通（f409/f411）→ 全 9 结局开月蚀
- 死代码：`s415`（有正文无入口）、`s53`（入口被作者注释，正文已删）——任何玩法都读不到

## 早期/废弃脚本

`parse.py` `scan2.py` `enumerate.py` `statespace.py` `reachability.py` `plan_slots.py`
`side_trips.py` `stage3.py` `planner.py` `gen_plan.py` `gen_plan2.py` 为探索过程稿；
`plan.md`/`plan2.md` 为被 plan3.md 取代的旧版流程单。保留仅供参考。

## 解析陷阱（已踩过）

- `skip N` 按物理行数（含注释/标签/续行）；本游戏所有 skip 不出块
- 无结尾 goto/select 的块**按文件顺序落入下一标签**；条件 goto 不成立时也落空
- `*skipNNN`（含 `*skip47a` 类带字母后缀）是块内内部标签，不能打断块解析
- 存档复用必须验证：续段序列一致 ∧ 增量场景在续段内 ∧ 前缀场景已被实际执行段覆盖 ∧ 锚点在锚 run 的执行段内
