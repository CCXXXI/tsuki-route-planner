# -*- coding: utf-8 -*-
"""v3 管线: 9 周目 (去掉重复的 ciel_true#2)
trips -> merge (含覆盖/可执行约束) -> 宽松 attach (所有剩余场景)
输出 plan_stage1_v3 / plan_stage2_v3 / plan_stage4_v3 / attach_v3.json
"""
import json, re, sys, io
exec(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\plan_cover.py', encoding='utf-8').read().split("# ---------- 1.")[0])

D = r'C:\Users\ccxxx\Desktop\tsuki_parse'
plan10 = json.load(open(D + r'\plan_stage1_v2.json', encoding='utf-8'))['plan']
reach = json.load(open(D + r'\reachability.json', encoding='utf-8'))
W = json.load(open(D + r'\witnesses.json', encoding='utf-8'))
universe = set(reach['union_scenes'])

DROP = 6  # ciel_true #2
plan = [p for i, p in enumerate(plan10) if i != DROP]
print(f'周目数: {len(plan)}', [p['ending'] for p in plan])

def simulate_full(ctx_bits, choices, start_block='f20', start_state=None):
    st = start_state if start_state is not None else \
        tuple((ctx_bits >> i) & 1 for i in range(NG)) + (0,) * (len(VARS) - NG)
    name = start_block
    bseq, sels, snaps, scenes = [], [], {}, []
    ending = None
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
        if b['scene']: scenes.append(b['scene'])
        if name in ENDING_BLOCKS: ending = ENDING_BLOCKS[name][0]
        nxt = None
        for e in b['branch']:
            if e['kind']=='select' or (e['kind']=='if' and e['act']=='select' and ev_c(e['cond'], st)):
                opts = e.get('options', [])
                pick = choices.get(name)
                chosen = next((o for o in opts if o['text'].strip()==pick), opts[0] if opts else None)
                if chosen is None: break
                snaps[name] = st
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
    return bseq, sels, snaps, scenes, ending

runs = []
for P in plan:
    bseq, sels, snaps, scenes, ending = simulate_full(P['ctx'], P['choices'])
    assert ending == P['ending'], (P['ending'], ending)
    runs.append({'ctx': P['ctx'], 'choices': P['choices'], 'ending': P['ending'],
                 'bseq': bseq, 'sels': sels, 'snaps': snaps, 'scenes': scenes})

# ---------- 1. 支线发现 (单选项绕道, 默认后续) ----------
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
for r in runs: covered |= set(r['scenes'])
remaining = universe - covered
trips = []
for pi, r in enumerate(runs):
    main_pos = {}
    for idx, bn in enumerate(r['bseq']): main_pos.setdefault(bn, idx)
    for k, (at, pick) in enumerate(r['sels']):
        st_snap = r['snaps'][at]
        # 该块的所有选项
        for e in blocks[at]['branch']:
            opts = None
            if e['kind'] == 'select': opts = e['options']
            elif e['kind'] == 'if' and e['act'] == 'select' and ev_c(e['cond'], st_snap): opts = e.get('options')
            if opts is None: continue
            for o in opts:
                if o['text'].strip() == pick: continue
                sc, how = detrip(o['target'], st_snap, main_pos, main_pos.get(at, 0))
                newsc = [x for x in sc if x in remaining]
                if newsc:
                    trips.append({'pt': pi, 'at': at, 'pick': o['text'].strip(), 'instead_of': pick,
                                  'scenes': sc, 'new': sorted(set(newsc)), 'how': how})
            break
chosen_trips = []
rem = set(remaining)
while True:
    best, bi = 0, None
    for i, t in enumerate(trips):
        n = len([s for s in t['new'] if s in rem])
        if n > best: best, bi = n, i
    if bi is None: break
    chosen_trips.append(trips[bi]); rem -= set(trips[bi]['new'])
print(f'支线: {len(chosen_trips)}, 剩余 {len(rem)}: {sorted(rem)}')

# ---------- 2. merge (含覆盖/可执行约束) ----------
trip_anchor = {}
for t in chosen_trips:
    trip_anchor.setdefault(t['pt'], set()).add(t['at'])
snap_pool = {}
covered_exec = set()
for i, r in enumerate(runs):
    full_scenes = set(r['scenes'])
    my_new = full_scenes - covered_exec
    best = None
    for k in range(len(r['sels']) - 1, -1, -1):
        B, _ = r['sels'][k]
        if B not in snap_pool: continue
        bpos = r['bseq'].index(B)
        pre_scenes = {blocks[bn]['scene'] for bn in r['bseq'][:bpos] if blocks[bn]['scene']}
        if not pre_scenes <= covered_exec: continue
        for j, snap in snap_pool[B]:
            st2 = list(snap)
            for gi in range(NG): st2[gi] = (r['ctx'] >> gi) & 1
            rem_choices = {at: p for at, p in r['sels'][k:]}
            b2, s2, sn2, sc2, e2 = simulate_full(r['ctx'], rem_choices, B, tuple(st2))
            if s2 != r['sels'][k:]: continue
            if e2 != r['ending']: continue
            if not my_new <= set(sc2): continue
            if i in trip_anchor:
                kept = {at for at, _ in r['sels'][k:]}
                if not trip_anchor[i] <= kept: continue
            cand = (k, j, B, set(sc2))
            if best is None or (k, j) > (best[0], best[1]): best = cand
    r['reuse'] = best[:3] if best else None
    k_exec = best[0] if best else 0
    exec_blocks = {at for at, _ in r['sels'][k_exec:]}
    for B, snap in r['snaps'].items():
        if B in exec_blocks: snap_pool.setdefault(B, []).append((i, snap))
    covered_exec |= best[3] if best else full_scenes
    for t in chosen_trips:
        if t['pt'] == i: covered_exec |= set(t['new'])
    if best:
        kk, jj, BB = best[0], best[1], best[2]
        print(f"run{i} [{r['ending']}]: load run{jj} [{runs[jj]['ending']}] @{BB}, 第 {kk+1}/{len(r['sels'])} 选项点起")
    else:
        print(f"run{i} [{r['ending']}]: 全新开局")

# ---------- 3. 宽松 attach: 所有剩余场景 ----------
scene2f = {b['scene']: n for n, b in blocks.items() if b['scene']}
attach = []
for s in sorted(rem):
    f = scene2f[s]
    wl = None; wctx = 31
    for c in range(32):
        wl = W.get(f'{c}|{f}')
        if wl is not None: wctx = c; break
    if wl is None:
        print(f'!! {s} 无见证'); continue
    guide = {c['at']: c['pick'] for c in wl}
    best3 = None
    for B, cands in snap_pool.items():
        for j, st_pt in cands:
            st2 = list(st_pt)
            for gi in range(NG): st2[gi] = (runs[j]['ctx'] >> gi) & 1
            b2, s2, sn2, sc2, e2 = simulate_full(runs[j]['ctx'], guide, B, tuple(st2))
            if s not in sc2: continue
            if e2 is not None: continue
            last_idx = max(i2 for i2, bn in enumerate(b2) if blocks[bn]['scene'] == s)
            stop_block = b2[last_idx + 1] if last_idx + 1 < len(b2) else None
            cand = (len(s2), j, B, stop_block, s2, sc2)
            if best3 is None or cand[0] < best3[0]: best3 = cand
    if best3:
        nsteps, j, B, stop_block, s2, sc2 = best3
        attach.append({'target': s, 'targets': [s], 'pt': j, 'at': B, 'steps': nsteps,
                       'sels': [{'at': a, 'pick': p} for a, p in s2], 'stop_block': stop_block,
                       'hit_ending': None})
        print(f'{s}: 挂到 run{j} [{runs[j]["ending"]}] @{B}, {nsteps} 步')
    else:
        print(f'{s}: 无法挂载!')

# 合并同锚点同路径的支线 (目标场景取并集, 停止点取路径上最后一个目标之后)
grouped = {}
for a in attach:
    key = (a['pt'], a['at'], json.dumps(a['sels'], ensure_ascii=False))
    if key in grouped:
        grouped[key]['targets'] = sorted(set(grouped[key]['targets']) | set(a['targets']))
    else:
        grouped[key] = dict(a)
attach = []
for a in grouped.values():
    # 重放该路径求合并后的停止点
    B = a['at']
    j = a['pt']
    snap = None
    for jj, st_pt in snap_pool.get(B, []):
        if jj == j: snap = st_pt; break
    guide = {s2['at']: s2['pick'] for s2 in a['sels']}
    b2, s2x, sn2, sc2, e2 = simulate_full(runs[j]['ctx'], guide, B, snap)
    tset = set(a['targets'])
    last_idx = max(i2 for i2, bn in enumerate(b2) if blocks[bn]['scene'] in tset)
    a['stop_block'] = b2[last_idx + 1] if last_idx + 1 < len(b2) else None
    attach.append(a)
print(f'合并后支线组数: {len(attach)}')

# 合并同锚点同前缀的支线目标 (展示优化): 同 (pt, at) 且步骤完全相同的归为一组
json.dump({'plan': plan}, open(D + r'\plan_stage1_v3.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({'trips': chosen_trips, 'remaining': sorted(rem)},
          open(D + r'\plan_stage2_v3.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({'runs': [{'kind': 'pt', 'name': r['ending'], 'ctx': r['ctx'], 'choices': r['choices'],
                     'sels': [list(x) for x in r['sels']], 'reuse': r['reuse']} for r in runs]},
          open(D + r'\plan_stage4_v3.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(attach, open(D + r'\attach_v3.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 覆盖验证
allcov = set()
for r in runs: allcov |= set(r['scenes'])
for t in chosen_trips: allcov |= set(t['new'])
for a in attach: allcov |= set(a['targets'])
print('覆盖验证:', len(allcov), '/', len(universe), '缺失', sorted(universe - allcov))
