# -*- coding: utf-8 -*-
"""生成最终 plan.md: 全场景覆盖最优流程"""
import json, re, sys, io
exec(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\plan_cover.py', encoding='utf-8').read().split("# ---------- 1.")[0])

D = r'C:\Users\ccxxx\Desktop\tsuki_parse'
lines = open(r'C:\Users\ccxxx\Desktop\0.txt', encoding='utf-8').read().split('\n')
st1 = json.load(open(D + r'\plan_stage1.json', encoding='utf-8'))
st2 = json.load(open(D + r'\plan_stage2.json', encoding='utf-8'))
st3 = json.load(open(D + r'\plan_stage3.json', encoding='utf-8'))

# 场景预览: s 标签后第一条中文文本
label_line = {}
for i, ln in enumerate(lines):
    m = re.match(r'^\*([A-Za-z0-9_]+)', ln)
    if m: label_line[m.group(1)] = i

def scene_preview(sname, maxlen=38):
    if sname not in label_line: return ''
    for ln in lines[label_line[sname]+1: label_line[sname]+40]:
        s = ln.strip()
        if not s or s.startswith(';') or s.startswith('*'): continue
        if re.match(r'^[a-z!#%$@\\]', s): continue  # 指令
        s = s.rstrip('\\').strip()
        if len(s) >= 4:
            return s[:maxlen] + ('…' if len(s) > maxlen else '')
    return ''

ENDING_CN = {'ark_true': '爱尔奎特 TRUE END', 'ark_good': '爱尔奎特 GOOD END',
             'arc_true': '爱尔奎特 TRUE END', 'arc_good': '爱尔奎特 GOOD END',
             'ciel_true': '希耶尔 TRUE END', 'ciel_good': '希耶尔 GOOD END',
             'akiha_true': '秋叶 TRUE END', 'akiha_good': '秋叶 GOOD END',
             'hisui_true': '翡翠 TRUE END', 'hisui_good': '翡翠 GOOD END',
             'kohaku_true': '琥珀 TRUE END (结局名「向日葵」)'}
CTX_REQ = {0: '无（一周目）', 5: '需已通关任一表线', 23: '需已通关爱尔奎特 TE',
           31: '需已通关翡翠线'}

plan = st1['plan']
trips = st2['trips']
trips_by_pt = {}
for t in st2['trips']:
    trips_by_pt.setdefault(t['pt'], []).append(t)

out = []
out.append('# 《月姬》全剧情无遗漏最优流程（由游戏脚本解析生成）\n')
out.append('数据来源：对 `0.txt`（NScripter 明文剧本）的完整解析 —— 467 个流程块、'
           '452 个场景、全部选项与分支条件。\n')
out.append('**方法**：符号执行 32 种全局进度上下文（约 5000 万游戏状态）→ 贪心集合覆盖选周目 → '
           '支线用「存档-改选-读档」覆盖 → 剩余场景用速通补课。'
           '已验证覆盖全部 450 个可达场景（另 2 个为游戏内死代码，任何玩法都无法触发）。\n')
out.append('**操作约定**：已读场景会出现「跳过吗？」提示，选「跳过」即可速推；'
           '【支线】= 在该选项前存档 → 改选 → 看到提示的场景后读档回来继续主线。\n')
out.append('---\n')

for i, P in enumerate(plan):
    out.append(f"## 周目 {i+1}：{ENDING_CN[P['ending']]}")
    out.append(f"前提：{CTX_REQ.get(P['ctx'], 'ctx=' + str(P['ctx']))}｜本线新场景 {len(P['scenes'])} 个\n")
    out.append('**主线选项**：\n')
    for j, s in enumerate(P['sels'], 1):
        sc = blocks[s['at']]['scene']
        pv = scene_preview(sc) if sc else ''
        loc = f"（{sc}：{pv}）" if pv else f"（{sc}）"
        out.append(f"{j}. {loc} 选 **{s['pick']}**")
    out.append('')
    if i in trips_by_pt:
        out.append('**支线（存档绕路）**：\n')
        for t in trips_by_pt[i]:
            sc = blocks[t['at']]['scene']
            pv = scene_preview(sc) if sc else ''
            news = '、'.join(t['new'])
            how = '看到新剧情汇入已读场景即可读档' if t['how'] == 'rejoin' else '一路看到 BAD END 后读档'
            out.append(f"- 在 {sc}（{pv}）的选项处：存档 → 改选 **{t['pick']}** → {how}\n"
                       f"  （覆盖：{news}）")
        out.append('')
    out.append('---\n')

out.append('## 补课速通周目（全程跳过已读场景，只读新场景）\n')
for k, r in enumerate(st3['runs'], 1):
    tgt_pv = scene_preview(r['target'])
    newsc = [s for s in r['scenes']]
    out.append(f"### 补课 {k}（目标：{r['target']}：{tgt_pv}）\n")
    ch = r['choices']
    # 重放拿到有序选项
    _, scenes, _, sels, _ = simulate(r['ctx'], ch)
    for j, s in enumerate(sels, 1):
        sc = blocks[s['at']]['scene']
        out.append(f"{j}. （{sc}）选 **{s['pick']}**")
    out.append('')

out.append('---\n')
out.append('## 最终解锁')
out.append('9 个结局全部达成后，标题画面变为「月蝕」版本 → 选择第二项进入 **月蚀（Eclipse）** 特别篇。\n')
out.append('## 附：无法触发的内容（游戏死代码，非流程问题）')
out.append('- `s415`：一段有完整正文（学校中庭，白天）但无任何入口的删减场景')
out.append('- `s53`：爱尔奎特线相关，流程块 `f53` 存在但入口代码被作者注释掉，且场景正文本身已不存在\n')
out.append('## 附：文件清单')
out.append('- `flow_graph.json`：机器可读分支图（块/场景/条件/选项/效果）')
out.append('- `reachability.json` / `witnesses.json`：32 上下文可达性与见证路径')
out.append('- `plan_stage1/2/3.json`：本流程的结构化数据')

open(D + r'\plan.md', 'w', encoding='utf-8').write('\n'.join(out))
print(f'plan.md 已生成, {len(out)} 行')
print(f'周目数 {len(plan)}, 支线 {len(st2["trips"])}, 补课 {len(st3["runs"])}')
