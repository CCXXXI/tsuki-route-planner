# -*- coding: utf-8 -*-
"""重建 v2 计划: 合并 arc TE#2 + ark GE -> 单个低好感 GE 周目; 删除冗余周目
然后重跑支线发现 + 补课, 输出 plan_stage1/2/3_v2.json
"""
import json, re, sys, io
exec(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\plan_cover.py', encoding='utf-8').read().split("# ---------- 1.")[0])

D = r'C:\Users\ccxxx\Desktop\tsuki_parse'
st1 = json.load(open(D + r'\plan_stage1.json', encoding='utf-8'))
reach = json.load(open(D + r'\reachability.json', encoding='utf-8'))
W = json.load(open(D + r'\witnesses.json', encoding='utf-8'))
plan = st1['plan']
universe = set(reach['union_scenes'])

# ---- 新周目表 ----
merged_ch = dict(plan[10]['choices'])
merged_ch['f503'] = '２、不能忘了爱尔奎特。'
newplan = []
for i in [0, 1, 2, 3, 4, None, 6, 7, 8, 9]:
    if i is not None:
        newplan.append(dict(plan[i]))
    else:
        bseq, scenes, ending, sels, fin = simulate(31, merged_ch)
        assert ending == 'ark_good', ending
        newplan.append({'ctx': 31, 'ending': 'ark_good', 'choices': merged_ch,
                        'scenes': scenes, 'sels': sels})
print('新周目数:', len(newplan), [p['ending'] for p in newplan])

# ---- 支线发现 (同 side_trips.py, 基于新周目) ----
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

def detrip(start, st, main_pos, min_pos, max_steps=80):
    name, cur = start, st
    scenes = []
    for _ in range(max_steps):
        if name in ('endofplay','END','title','title2','title_tochu','gamestart_menu','ending') or name not in blocks:
            return scenes, 'terminate'
        if name in main_pos and main_pos[name] > min_pos:
            return scenes, 'rejoin'
        b = blocks[name]
        hit = None
        for e in b['pre']:
            if e['kind']=='if' and e['act']=='goto' and ev_c(e['cond'], cur): hit = e['target']; break
            if e['kind']=='goto': hit = e['target']; break
        if hit is not None: name = hit; continue
        for e in b['effects']: cur = apply(e, cur)
        if b['scene']: scenes.append(b['scene'])
        nxt = None
        for e in b['branch']:
            if e['kind']=='select' or (e['kind']=='if' and e['act']=='select' and ev_c(e['cond'], cur)):
                opts = e.get('options', [])
                if not opts: break
                nxt = opts[0]['target']; break
            if e['kind']=='if' and e['act']=='select': continue
            if e['kind']=='if' and e['act']=='goto':
                if ev_c(e['cond'], cur): nxt = e['target']; break
                continue
            if e['kind']=='goto': nxt = e['target']; break
            if e['kind']=='end': return scenes, 'terminate'
        if nxt is None: nxt = b['fallthrough'] or 'END'
        name = nxt
    return scenes, 'overflow'

covered = set()
for P in newplan: covered |= set(P['scenes'])
remaining = universe - covered
print('主线覆盖:', len(covered), '剩余:', len(remaining))

trips = []
for pi, P in enumerate(newplan):
    bseq, sels, snaps = simulate_snaps(P['ctx'], P['choices'])
    main_pos = {}
    for idx, bn in enumerate(bseq): main_pos.setdefault(bn, idx)
    for s in sels:
        c = s['at']
        st_snap = snaps[c]
        for txt, tgt in s['options']:
            if txt == s['pick']: continue
            sc, how = detrip(tgt, st_snap, main_pos, main_pos.get(c, 0))
            newsc = [x for x in sc if x in remaining]
            if newsc:
                trips.append({'pt': pi, 'at': c, 'pick': txt, 'instead_of': s['pick'],
                              'scenes': sc, 'new': sorted(set(newsc)), 'how': how})
print('候选支线:', len(trips))
chosen = []
rem = set(remaining)
while True:
    best, bi = 0, None
    for i, t in enumerate(trips):
        n = len([s for s in t['new'] if s in rem])
        if n > best: best, bi = n, i
    if bi is None: break
    chosen.append(trips[bi]); rem -= set(trips[bi]['new'])
print('选出支线:', len(chosen), '覆盖后剩余:', len(rem), sorted(rem))

# ---- 补课 ----
scene2f = {b['scene']: n for n, b in blocks.items() if b['scene']}
runs = {}
for s in sorted(rem):
    f = scene2f[s]
    wl = W.get(f'31|{f}'); ctx = 31
    if wl is None:
        for c in range(32):
            wl = W.get(f'{c}|{f}')
            if wl is not None: ctx = c; break
    if wl is None: print('!! 无见证', s); continue
    ch = {c['at']: c['pick'] for c in wl}
    key = (ctx, tuple(sorted(ch.items())))
    if key in runs: continue
    bseq, scenes, ending, sels, fin = simulate(ctx, ch)
    runs[key] = {'ctx': ctx, 'choices': ch, 'scenes': scenes, 'ending': ending, 'target': s}
chosen_runs = []
rem2 = set(rem)
while True:
    best, bk = 0, None
    for k, r in runs.items():
        n = len(set(r['scenes']) & rem2)
        if n > best: best, bk = n, k
    if bk is None: break
    chosen_runs.append(runs[bk]); rem2 -= set(runs[bk]['scenes'])
print('补课 run:', len(chosen_runs), '最终剩余:', sorted(rem2))

json.dump({'plan': newplan}, open(D + r'\plan_stage1_v2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({'trips': chosen, 'remaining': sorted(rem)},
          open(D + r'\plan_stage2_v2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({'runs': chosen_runs, 'remaining': sorted(rem2)},
          open(D + r'\plan_stage3_v2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('已保存 v2 三件套')
