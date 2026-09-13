# -*- coding: utf-8 -*-
"""生成 plan3.md: save/load 复用树版本
- 每个 run: 全新开局 或 从之前的存档 load 继续
- 存档栏位全局编号 (创建顺序); 支线锚点与复用锚点统一分配
- 支线 inline: save → 支线(读档) → 主线选项
"""
import json, re, sys, io
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(_HERE, 'plan_cover.py'), encoding='utf-8').read().split("# ---------- 1.")[0])

D = _HERE
lines = open(os.path.join(D, '0.txt'), encoding='utf-8').read().split('\n')
st2 = json.load(open(D + r'\plan_stage2_v4.json', encoding='utf-8'))
st4 = json.load(open(D + r'\plan_stage4_v4.json', encoding='utf-8'))
attach = json.load(open(D + r'\attach_v4.json', encoding='utf-8'))
endtrips = json.load(open(D + r'\endtrips_v4.json', encoding='utf-8'))
drop_main = {(int(i2), at2) for i2, at2 in (x.split('|') for x in json.load(open(D + r'\dropmain_v4.json', encoding='utf-8'))['drop_main'])}
runs = st4['runs']

# 挂载的补课 -> 多步支线, 按 (周目, 锚点块) 分组
attached = {}
for a in attach:
    if a['pt'] is not None:
        attached.setdefault((a['pt'], a['at']), []).append(a)
# 结局支线: 周目中 (post=False) 挂到选项点; 通关后 (post=True) 挂到周目末尾
endtrip_mid = {}
endtrip_post = {}
for et in endtrips:
    (endtrip_post if et['post'] else endtrip_mid).setdefault(et['pt'], []).append(et)

label_line = {}
for i, ln in enumerate(lines):
    m = re.match(r'^\*([A-Za-z0-9_]+)', ln)
    if m: label_line[m.group(1)] = i

def scene_preview(sname, maxlen=30):
    if not sname or sname not in label_line: return ''
    for ln in lines[label_line[sname]+1: label_line[sname]+40]:
        s = ln.strip()
        if not s or s.startswith(';') or s.startswith('*'): continue
        if re.match(r'^[a-z!#%$@\\]', s): continue
        s = s.rstrip('\\').strip()
        if len(s) >= 4:
            return s[:maxlen] + ('…' if len(s) > maxlen else '')
    return ''

def loc_of(at):
    sc = blocks[at]['scene']
    pv = scene_preview(sc)
    return f"{sc}「{pv}」" if pv else (f"{sc}" if sc else f"选项点 {at}")

def detrip_full(start, st, main_pos, min_pos, max_steps=80):
    name, cur = start, st
    scenes, inner = [], []
    rejoin_pending = False
    for _ in range(max_steps):
        if name in ('endofplay','END','title','title2','title_tochu','gamestart_menu','ending') or name not in blocks:
            return scenes, inner, 'terminate', None
        if name in main_pos and main_pos[name] > min_pos:
            if blocks[name]['scene']: return scenes, inner, 'rejoin', name
            rejoin_pending = True
        b = blocks[name]
        hit = None
        for e in b['pre']:
            if e['kind']=='if' and e['act']=='goto' and ev_c(e['cond'], cur): hit = e['target']; break
            if e['kind']=='goto': hit = e['target']; break
        if hit is not None: name = hit; continue
        for e in b['effects']: cur = apply(e, cur)
        if b['scene']:
            if rejoin_pending: return scenes, inner, 'rejoin', name
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
             'arc_true': '爱尔奎特 TRUE END', 'ciel_true': '希耶尔 TRUE END',
             'ciel_good': '希耶尔 GOOD END', 'akiha_true': '秋叶 TRUE END',
             'akiha_good': '秋叶 GOOD END', 'hisui_true': '翡翠 TRUE END',
             'hisui_good': '翡翠 GOOD END', 'kohaku_true': '琥珀 TRUE END'}

# ---- 支线按 (run, at) 分组 (pt 索引 == runs 0..9) ----
trips_by = {}
for t in st2['trips']:
    trips_by.setdefault((t['pt'], t['at']), []).append(t)

# ---- 需要创建的存档: (run_idx, block) ----
endtrip_anchor_set = {(et['pt'], et['at']) for et in endtrips}

def group_needs_save(i, at):
    """该选项点是否需要存档: 有要读档的支线/结局支线则存档; drop_main 纯终点组不存档"""
    if (i, at) in endtrip_anchor_set: return True
    items = trips_by.get((i, at), []) + attached.get((i, at), [])
    if not items: return False
    if (i, at) not in drop_main: return True
    return any(not x.get('terminal') for x in items)

need_save = set()
for (pi, at) in trips_by:
    if group_needs_save(pi, at): need_save.add((pi, at))
for key in attached:
    if group_needs_save(*key): need_save.add(key)
residuals = [a for a in attach if a['pt'] is None]
for a in residuals:
    if a.get('load_from'):
        need_save.add(tuple(a['load_from']))
for et in endtrips:
    need_save.add((et['pt'], et['at']))

# ---- 栏位回收: 区间着色 ----
# 事件序号: 每个 run 的开头 load 占一拍, 每个选项点占一拍 (支线 load 与 save 同拍)
create_seq, last_use = {}, {}
seq = 0
for i, r in enumerate(runs):
    for at, _ in r['sels']:
        if (i, at) in need_save and (i, at) not in create_seq:
            create_seq[(i, at)] = seq
        if (i, at) in trips_by and group_needs_save(i, at):
            last_use[(i, at)] = seq
        seq += 1
    for et in endtrip_post.get(i, []):   # 通关后结局支线: 紧随该周目末尾
        last_use[(et['pt'], et['at'])] = seq
        seq += 1
for a in residuals:  # 残余补课在所有周目之后
    if a.get('load_from'):
        last_use[tuple(a['load_from'])] = seq
    seq += 1
for key in need_save:
    last_use.setdefault(key, create_seq[key])
# 着色: 按创建顺序分配最小空闲栏位 (last_use < create 即已释放)
import heapq
slot_of = {}
free = []
inuse = []  # (last_use, slot)
for key in sorted(need_save, key=lambda x: create_seq[x]):
    c = create_seq[key]
    while inuse and inuse[0][0] < c:
        heapq.heappush(free, heapq.heappop(inuse)[1])
    if free:
        sn = heapq.heappop(free)
    else:
        sn = max(slot_of.values(), default=0) + 1
    slot_of[key] = sn
    heapq.heappush(inuse, (last_use[key], sn))
NSLOTS = max(slot_of.values())
# 栏位为 1 时存档不编号
tag = (lambda sn: '') if NSLOTS == 1 else (lambda sn: str(sn))

# ---- 每个 run 的快照 (重放) ----
def snaps_of2(ctx_bits, choices):
    """完整重放, 返回 (snaps, sels, bseq)"""
    st = tuple((ctx_bits >> gi) & 1 for gi in range(NG)) + (0,) * (len(VARS) - NG)
    name = 'f20'
    snaps, bseq, sels = {}, [], []
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
                snaps[name] = (st, [(o['text'].strip(), o['target']) for o in opts])
                sels.append((name, chosen['text'].strip()))
                nxt = chosen['target']; break
            if e['kind']=='if' and e['act']=='select': continue
            if e['kind']=='if' and e['act']=='goto':
                if ev_c(e['cond'], st): nxt = e['target']; break
                continue
            if e['kind']=='goto': nxt = e['target']; break
            if e['kind']=='end': nxt = 'END'; break
        if nxt is None: nxt = b['fallthrough'] or 'END'
        name = nxt
    return snaps, sels, bseq

def snaps_of(r):
    s, _, b = snaps_of2(r['ctx'], r['choices'])
    return s, b

# 栏位是否复用旧档 (该编号此前被用过)
slot_recycled = {}
seen_slot = set()
for key in sorted(need_save, key=lambda x: create_seq[x]):
    sn = slot_of[key]
    slot_recycled[key] = sn in seen_slot
    seen_slot.add(sn)

out = []
out.append('# 《月姬》全剧情收集流程\n')
out.append('## 使用说明\n')
out.append('- **开始前：标题 → 选项 → 设置，把第 2 项「场景跳过」打开**；已读场景会弹「跳过吗？」选「跳过」即可速推。')
out.append('- `save` = 存档；`load` = 读取（读的是最近一次 `save` 存的档）。**全程只用 1 个栏位**，'
           '看到提示 `save（旧档已用完，可覆盖）` 时放心覆盖。')
out.append('- 每个周目都**从新游戏开始**；路线解锁进度存在系统存档里，不受新游戏影响。')
out.append('- 有支线的选项点：先 save → 逐条支线（做完 load 回来）→ 最后选主线项。')
out.append('- 支线终点：标注**汇合场景**的，读到该场景开头就 load 回来；标注 **BAD END** 的看到结局再 load。')
out.append('- `s123` 是场景编号，`「…」` 是该场景第一句台词，用于对照位置。\n')
out.append('---\n')

pt_num = 0
for i, r in enumerate(runs):
    sels = [tuple(s) for s in r['sels']]
    snaps, bseq = snaps_of(r)
    main_pos = {}
    for idx, bn in enumerate(bseq): main_pos.setdefault(bn, idx)
    pt_num += 1
    out.append(f"## 周目 {pt_num}：{ENDING_CN[r['name']]}")
    out.append('从**新游戏**开始：\n')
    step = 0
    for at, pick in sels:
        step += 1
        my_trips = trips_by.get((i, at), [])
        my_detours = attached.get((i, at), [])
        my_endtrips = [et for et in endtrip_mid.get(i, []) if et['at'] == at]
        need = (i, at) in need_save
        dm = (i, at) in drop_main
        if my_trips or my_detours or my_endtrips:
            # drop_main 组的终点支线实质即主线; 其余支线读档回来
            term_trips = [t for t in my_trips if t.get('terminal') and dm]
            term_dets = [a for a in my_detours if a.get('terminal') and dm]
            norm_trips = [t for t in my_trips if t not in term_trips]
            norm_dets = [a for a in my_detours if a not in term_dets]
            has_load = bool(norm_trips or norm_dets or my_endtrips or (i, at) in endtrip_anchor_set)
            if has_load:
                sn = slot_of[(i, at)]
                ov = '（旧档已用完，可覆盖）' if slot_recycled[(i, at)] else ''
                out.append(f"{step}. {loc_of(at)} 出现选项 → 💾 **save{tag(sn)}**{ov}")
                for t in norm_trips:
                    st_snap, opts = snaps[at]
                    tgt = next(tg for txt, tg in opts if txt == t['pick'])
                    dsc, inner, how, rej = detrip_full(tgt, st_snap, main_pos, main_pos.get(at, 0))
                    news = '、'.join(t.get('disp', t['new']))
                    ln = f'load{tag(sn)}'
                    if t['how'] == 'terminate':
                        lesson_new = [x for x in t['new'] if re.match(r'^s5\d\d$', x)]
                        pre = [c for c in inner if c['pick'] != '１、是。']
                        pre_txt = ''.join(f" → 途中选项选「{c['pick']}」" for c in pre)
                        tail = ('看到 BAD END → 授课邀请选「是」看完授课场景' if lesson_new
                                else '看到 BAD END（授课邀请选「否」即可）')
                        out.append(f"   - 支线：选 **{t['pick']}**{pre_txt} → {tail} → 📂 **{ln}**  （新剧情：{news}）")
                    else:
                        inner_txt = ''.join(f" → 途中选项选「{c['pick']}」" for c in inner)
                        rsc = blocks[rej]['scene'] if rej else None
                        rpv = scene_preview(rsc)
                        rej_txt = f"{rsc}「{rpv}」" if rpv else f"{rsc}"
                        out.append(f"   - 支线：选 **{t['pick']}**{inner_txt} → 读到汇合场景 **{rej_txt}** 开头 → 📂 **{ln}**  （新剧情：{news}）")
                for a in norm_dets:
                    news = '、'.join(a.get('disp', a['targets']))
                    ln = f'load{tag(sn)}'
                    steps_txt = ' → '.join(f"选「{s['pick']}」" for s in a['sels'])
                    if a.get('stop_menu_at'):
                        tail = f"读完 **{loc_of(a['stop_menu_at'])}**（出现选项时不用选）"
                    elif a.get('stop_block'):
                        tail = f"读到 **{loc_of(a['stop_block'])}** 开头（后面的内容主线/其他支线已覆盖）"
                    else:
                        tail = '一路看到回到标题画面'
                    out.append(f"   - 支线（{a['steps']} 个选项）：{steps_txt} → {tail} → 📂 **{ln}**  （新剧情：{news}）")
                for et in my_endtrips:
                    news = '、'.join(et['disp'])
                    steps_txt = ' → '.join(f"选「{s['pick']}」" for s in et['sels'])
                    out.append(f"   - 结局支线：{steps_txt} → 看到 **{ENDING_CN[et['ending']]}** 回标题 → 📂 **load{tag(sn)}**  （新剧情：{news}）")
                step += 1
            if dm:
                # 终点支线 = 主线本身: 写成普通主线步骤
                if term_trips:
                    t = term_trips[0]
                    news = '、'.join(t.get('disp', t['new']))
                    out.append(f"{step}. {loc_of(at)} → 选 **{t['pick']}**（新剧情：{news}）")
                else:
                    a = term_dets[0]
                    news = '、'.join(a.get('disp', a['targets']))
                    chain = ' → '.join(f"（{loc_of(s['at'])}）选 **{s['pick']}**" for s in a['sels'][1:])
                    chain = f" → {chain}" if chain else ''
                    out.append(f"{step}. {loc_of(at)} → 选 **{a['sels'][0]['pick']}**{chain}（新剧情：{news}）")
            else:
                out.append(f"{step}. {loc_of(at)} → 选 **{pick}**")
        elif need:
            sn = slot_of[(i, at)]
            ov = '（旧档已用完，可覆盖）' if slot_recycled[(i, at)] else ''
            out.append(f"{step}. {loc_of(at)} 出现选项 → 💾 **save{tag(sn)}**{ov} → 选 **{pick}**")
        else:
            out.append(f"{step}. {loc_of(at)} → 选 **{pick}**")
    for et in endtrip_post.get(i, []):
        sn = slot_of[(et['pt'], et['at'])]
        news = '、'.join(et['disp'])
        steps_txt = ' → '.join(f"选「{s['pick']}」" for s in et['sels'])
        out.append(f"\n**通关后收 GE**：📂 **load{tag(sn)}**（上面在 {loc_of(et['at'])} 存的档）→ {steps_txt} "
                   f"→ 看到 **{ENDING_CN[et['ending']]}** 回标题  （新剧情：{news}）")
    out.append('')

out.append('---\n')
if residuals:
    out.append('## 收尾速通（最后做：需要全部结局通关后的进度才能走通）\n')
    for a in residuals:
        tgt = a['target']
        out.append(f"### {tgt}「{scene_preview(tgt)}」（新剧情：{'、'.join(a['targets'])}）")
        if a.get('load_from'):
            j, B = a['load_from']
            out.append(f"📂 **load{tag(slot_of[(j, B)])}**（周目{j+1}里在 {loc_of(B)} 存的档），然后：\n")
        else:
            out.append('从**新游戏**开始：\n')
        # 重放取选项序列 (从锚点开始的部分)
        _, sels_r, _ = snaps_of2(a['ctx'], a['choices'])
        if a.get('load_from'):
            sels_r = sels_r[a['skip_to']:]
        for n, (at, pick) in enumerate(sels_r, 1):
            out.append(f"{n}. {loc_of(at)} → 选 **{pick}**")
        out.append('')
out.append('---\n')
out.append('## 最后')
out.append('9 个结局全部达成后，标题画面变为「月蝕」→ 选第二项进入 **Eclipse（月蚀）** 特别篇，无选项读完即可。')
out.append('至此 450/450 个可达场景全部覆盖。')

# ---- 栏位正确性验证: 模拟事件流, 每次 load 时栏位内容必须是期望的存档 ----
content = {}
ok = True
for i, r in enumerate(runs):
    for at, _ in r['sels']:
        if (i, at) in need_save:
            content[slot_of[(i, at)]] = (i, at)
        if group_needs_save(i, at):
            sn = slot_of[(i, at)]
            if content.get(sn) != (i, at):
                print(f'!! run{i} 支线 load{sn} 内容错误'); ok = False
        for et in endtrip_mid.get(i, []):
            if et['at'] == at:
                sn = slot_of[(i, at)]
                if content.get(sn) != (i, at):
                    print(f'!! run{i} 结局支线 load{sn} 内容错误'); ok = False
    for et in endtrip_post.get(i, []):
        sn = slot_of[(et['pt'], et['at'])]
        if content.get(sn) != (et['pt'], et['at']):
            print(f'!! 通关后支线 load{sn} 内容错误'); ok = False
for a in residuals:
    if a.get('load_from'):
        key = tuple(a['load_from'])
        sn = slot_of[key]
        if content.get(sn) != key:
            print(f'!! 残余补课 {a["target"]} load{sn} 内容错误'); ok = False
print('栏位事件流验证:', '通过' if ok else '失败')

# ---- 文本级验证: 文中每个 load 出现前必须有对应的 save ----
seen_save = set()
for ln in out:
    for m in re.finditer(r'💾 \*\*save(\d*)\*\*', ln): seen_save.add(m.group(1))
    for m in re.finditer(r'📂 \*\*load(\d*)\*\*', ln):
        if m.group(1) not in seen_save:
            print(f'!! 文本中 load{m.group(1)} 之前没有对应 save: {ln[:60]}'); ok = False
print('文本 save/load 配对验证:', '通过' if ok else '失败')

open(D + r'\plan3.md', 'w', encoding='utf-8').write('\n'.join(out))
print(f'plan3.md 生成, {len(out)} 行, 回收后栏位共 {NSLOTS} 个')

# ---- 最终覆盖验证: 只算实际执行的段落; 支线按完整途经场景计 ----
allcov = set()
for i, r in enumerate(runs):
    _, _, bseq2 = snaps_of2(r['ctx'], r['choices'])
    for bn in bseq2:
        if blocks[bn]['scene']: allcov.add(blocks[bn]['scene'])
for t in st2['trips']: allcov |= set(t['scenes'])
for a in attach:
    allcov |= set(a.get('cov', a['targets']))
for et in endtrips: allcov |= set(et['cov'])
reach = json.load(open(D + r'\reachability.json', encoding='utf-8'))
missing = set(reach['union_scenes']) - allcov
print('最终覆盖验证 (按实际执行段): 缺失', sorted(missing) if missing else '无 (450/450)')
