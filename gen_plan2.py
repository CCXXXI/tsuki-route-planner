# -*- coding: utf-8 -*-
"""生成 plan2.md: 以 saveN/loadN 栏位操作为中心的线性流程单
- 主线选项按时间顺序列出
- 有支线的选项点: saveN → (每条支线: 改选… → 看完 → loadN) → 主线选择
- 支线内部若再有选项, 展开为具体指令 (重跑 detrip 记录内部选择)
"""
import json, re, sys, io
exec(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\plan_cover.py', encoding='utf-8').read().split("# ---------- 1.")[0])

D = r'C:\Users\ccxxx\Desktop\tsuki_parse'
lines = open(r'C:\Users\ccxxx\Desktop\0.txt', encoding='utf-8').read().split('\n')
st1 = json.load(open(D + r'\plan_stage1_v2.json', encoding='utf-8'))
st2 = json.load(open(D + r'\plan_stage2_v2.json', encoding='utf-8'))
st3 = json.load(open(D + r'\plan_stage3_v2.json', encoding='utf-8'))

label_line = {}
for i, ln in enumerate(lines):
    m = re.match(r'^\*([A-Za-z0-9_]+)', ln)
    if m: label_line[m.group(1)] = i

def scene_preview(sname, maxlen=30):
    if sname not in label_line: return ''
    for ln in lines[label_line[sname]+1: label_line[sname]+40]:
        s = ln.strip()
        if not s or s.startswith(';') or s.startswith('*'): continue
        if re.match(r'^[a-z!#%$@\\]', s): continue
        s = s.rstrip('\\').strip()
        if len(s) >= 4:
            return s[:maxlen] + ('…' if len(s) > maxlen else '')
    return ''

def simulate_snaps(ctx_bits, choices):
    st = tuple((ctx_bits >> i) & 1 for i in range(NG)) + (0,) * (len(VARS) - NG)
    name = 'f20'
    bseq, sels, snaps = [], [], {}
    for _ in range(3000):
        if name in ('endofplay','END','title','title2','title_tochu','gamestart_menu','ending') or name not in blocks:
            break
        b = blocks[name]
        hit = None
        for e in b['pre']:
            if e['kind']=='if' and e['act']=='goto' and ev_c(e['cond'], st): hit = e['target']; break
            if e['kind']=='goto': hit = e['target']; break
        if hit is not None: name = hit; continue
        for e in b['effects']: st = apply(e, st)
        bseq.append(name)
        nxt = None
        for e in b['branch']:
            if e['kind']=='select' or (e['kind']=='if' and e['act']=='select' and ev_c(e['cond'], st)):
                opts = e.get('options', [])
                pick = choices.get(name)
                chosen = next((o for o in opts if o['text'].strip()==pick), opts[0] if opts else None)
                if chosen is None: break
                snaps[name] = st
                sels.append({'at': name, 'pick': chosen['text'].strip(),
                             'options': [(o['text'].strip(), o['target']) for o in opts]})
                nxt = chosen['target']; break
            if e['kind']=='if' and e['act']=='select': continue
            if e['kind']=='if' and e['act']=='goto':
                if ev_c(e['cond'], st): nxt = e['target']; break
                continue
            if e['kind']=='goto': nxt = e['target']; break
            if e['kind']=='end': nxt = 'END'; break
        if nxt is None: nxt = b['fallthrough'] or 'END'
        name = nxt
    return bseq, sels, snaps

def detrip_full(start, st, main_pos, min_pos, max_steps=80):
    """支线全程, 记录内部选择与经过场景. 内部选项默认第一项.
    汇合: 到达主线块序列中位置 > min_pos 的块即停止. 返回 (scenes, inner, how, rejoin_block)"""
    name, cur = start, st
    scenes, inner = [], []
    rejoin_pending = False
    for _ in range(max_steps):
        if name in ('endofplay','END','title','title2','title_tochu','gamestart_menu','ending') or name not in blocks:
            return scenes, inner, 'terminate', None
        if name in main_pos and main_pos[name] > min_pos:
            if blocks[name]['scene']:
                return scenes, inner, 'rejoin', name
            rejoin_pending = True  # 无场景派发块: 顺流到下一个有场景的块作参照
        b = blocks[name]
        hit = None
        for e in b['pre']:
            if e['kind']=='if' and e['act']=='goto' and ev_c(e['cond'], cur): hit = e['target']; break
            if e['kind']=='goto': hit = e['target']; break
        if hit is not None: name = hit; continue
        for e in b['effects']: cur = apply(e, cur)
        if b['scene']:
            if rejoin_pending:
                return scenes, inner, 'rejoin', name
            scenes.append(b['scene'])
        nxt = None
        for e in b['branch']:
            if e['kind']=='select' or (e['kind']=='if' and e['act']=='select' and ev_c(e['cond'], cur)):
                opts = e.get('options', [])
                if not opts: break
                inner.append({'at': name, 'pick': opts[0]['text'].strip()})
                nxt = opts[0]['target']; break
            if e['kind']=='if' and e['act']=='select': continue
            if e['kind']=='if' and e['act']=='goto':
                if ev_c(e['cond'], cur): nxt = e['target']; break
                continue
            if e['kind']=='goto': nxt = e['target']; break
            if e['kind']=='end': return scenes, inner, 'terminate', None
        if nxt is None: nxt = b['fallthrough'] or 'END'
        name = nxt
    return scenes, inner, 'overflow', None

ENDING_CN = {'ark_true': '爱尔奎特 TRUE END', 'ark_good': '爱尔奎特 GOOD END',
             'arc_true': '爱尔奎特 TRUE END', 'arc_good': '爱尔奎特 GOOD END',
             'ciel_true': '希耶尔 TRUE END', 'ciel_good': '希耶尔 GOOD END',
             'akiha_true': '秋叶 TRUE END', 'akiha_good': '秋叶 GOOD END',
             'hisui_true': '翡翠 TRUE END', 'hisui_good': '翡翠 GOOD END',
             'kohaku_true': '琥珀 TRUE END'}
CTX_REQ = {0: '无（必须是一周目）', 5: '需已通关任一表线', 23: '需已通关爱尔奎特线',
           31: '需已通关翡翠线'}

plan = st1['plan']
trips_by_pt_at = {}
for t in st2['trips']:
    trips_by_pt_at.setdefault((t['pt'], t['at']), []).append(t)

out = []
out.append('# 《月姬》全剧情收集流程（存档栏位版）\n')
out.append('## 使用说明\n')
out.append('- **开始前先到 标题 → 选项 → 设置，把第 2 项「场景跳过」打开**（图标旁显示 OK）。'
           '之后已读场景会弹出「该场景曾显示过。跳过吗？」→ 选「跳过」即可速推。')
out.append('- 流程为线性操作：`saveN`/`loadN` 即存档栏位 N（栏位号每周目从 1 重新计，跨周目可覆盖）。')
out.append('- 有支线的选项点：**先 save → 逐条做支线（每条做完 load 回来）→ 最后选主线项**。')
out.append('- 支线的终点分两种：标注了**汇合场景**的，读到该场景开头（对照编号和第一句台词）就 load 回来——'
           '该场景及之后的内容在主线里会正常读到；标注 **BAD END** 的一路看到结局再 load。')
out.append('- 括号里 `s123` 是场景编号，`「…」` 是该场景开头第一句台词，用来对照位置。\n')
out.append('---\n')

for i, P in enumerate(plan):
    bseq, sels, snaps = simulate_snaps(P['ctx'], P['choices'])
    main_pos = {}
    for idx, bn in enumerate(bseq):
        main_pos.setdefault(bn, idx)
    at_pos = {}
    for idx, bn in enumerate(bseq):
        if bn not in at_pos: at_pos[bn] = idx
    out.append(f"## 周目 {i+1}：{ENDING_CN[P['ending']]}")
    out.append(f"前提：{CTX_REQ.get(P['ctx'], '')}\n")
    slot = 0
    step = 0
    for s in sels:
        at = s['at']
        sc = blocks[at]['scene']
        pv = scene_preview(sc) if sc else ''
        loc = f"{sc}「{pv}」" if pv else (f"{sc}" if sc else f"选项点 {at}")
        my_trips = trips_by_pt_at.get((i, at), [])
        if not my_trips:
            step += 1
            out.append(f"{step}. {loc} → 选 **{s['pick']}**")
            continue
        slot += 1
        sn, ln = f'save{slot}', f'load{slot}'
        step += 1
        out.append(f"{step}. {loc} 出现选项 → 💾 **{sn}**")
        for t in my_trips:
            st_snap = snaps[at]
            tgt = next(tg for txt, tg in s['options'] if txt == t['pick'])
            dsc, inner, how, rej = detrip_full(tgt, st_snap, main_pos, at_pos.get(at, 0))
            news = '、'.join(t['new'])
            if t['how'] == 'terminate':
                lesson_new = [x for x in t['new'] if re.match(r'^s5\d\d$', x)]
                pre = [c for c in inner if c['pick'] != '１、是。']
                pre_txt = ''.join(f" → 途中选项选「{c['pick']}」" for c in pre)
                if lesson_new:
                    tail = '看到 BAD END → 授课邀请选「是」看完授课场景'
                else:
                    tail = '看到 BAD END（授课邀请选「否」即可）'
                out.append(f"   - 选 **{t['pick']}**{pre_txt} → {tail} → 📂 **{ln}**  （新剧情：{news}）")
            else:
                inner_txt = ''.join(f" → 途中选项选「{c['pick']}」" for c in inner)
                rsc = blocks[rej]['scene'] if rej else None
                rpv = scene_preview(rsc) if rsc else ''
                rej_txt = f"{rsc}「{rpv}」" if rpv else (f"{rsc}" if rsc else f"块 {rej}")
                out.append(f"   - 选 **{t['pick']}**{inner_txt} → 读到汇合场景 **{rej_txt}** 开头 → 📂 **{ln}**  （新剧情：{news}）")
        step += 1
        out.append(f"{step}. 选 **{s['pick']}**（主线继续）")
    out.append('')

out.append('---\n')
out.append('## 补课速通（全程选「跳过」，只有列出的场景是新剧情）\n')
rem_pool = set(st2['remaining'])
for k, r in enumerate(st3['runs'], 1):
    pv = scene_preview(r['target'])
    _, sels, _ = simulate_snaps(r['ctx'], r['choices'])
    newhere = [s for s in r['scenes'] if s in rem_pool]
    rem_pool -= set(r['scenes'])
    newdesc = '、'.join(f"{s}「{scene_preview(s)}」" for s in newhere)
    out.append(f"### 补课 {k}（新剧情：{newdesc}）\n")
    for j, s in enumerate(sels, 1):
        sc = blocks[s['at']]['scene']
        loc = f"{sc}「{scene_preview(sc)}」" if sc else f"选项点 {s['at']}"
        out.append(f"{j}. {loc} → 选 **{s['pick']}**")
    out.append('')

out.append('---\n')
out.append('## 最后')
out.append('以上完成后 9 个结局全齐 → 标题画面变为「月蝕」→ 选第二项进入 **Eclipse（月蚀）** 特别篇，无选项一路读完即可。')
out.append('\n至此 450/450 个可达场景全部覆盖。')

open(D + r'\plan2.md', 'w', encoding='utf-8').write('\n'.join(out))
print(f'plan2.md 已生成, {len(out)} 行')
