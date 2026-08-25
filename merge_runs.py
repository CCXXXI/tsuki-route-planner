# -*- coding: utf-8 -*-
"""合并 v2: 状态兼容的深度存档复用
对每个 run 的每个选项点 B (从晚到早), 尝试所有更早 run 在 B 的快照状态,
把全局位替换成当前 run 的 ctx 后模拟, 若能完整复现当前 run 的后续选项序列和结局
=> 可从该存档 load 继续. 约束: 不能丢掉该 run 上已挂支线的锚点.
"""
import json, re, sys, io
exec(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\plan_cover.py', encoding='utf-8').read().split("# ---------- 1.")[0])

D = r'C:\Users\ccxxx\Desktop\tsuki_parse'
plan = json.load(open(D + r'\plan_stage1_v2.json', encoding='utf-8'))['plan']
st2 = json.load(open(D + r'\plan_stage2_v2.json', encoding='utf-8'))
st3 = json.load(open(D + r'\plan_stage3_v2.json', encoding='utf-8'))
TRIPS = st2['trips']

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
    runs.append({'kind': 'pt', 'name': P['ending'], 'ctx': P['ctx'], 'choices': P['choices']})
# 补课不再作为独立 run (由 attach_bukou 挂为支线)

for r in runs:
    bseq, sels, snaps, scenes, ending = simulate_full(r['ctx'], r['choices'])
    r['bseq'], r['sels'], r['snaps'], r['scenes'], r['ending_sim'] = bseq, sels, snaps, scenes, ending

# 支线锚点约束: run i 的支线锚点块集合 (trips 的 pt 索引对应 plan 索引 = run 索引 0..9)
trip_anchor = {}
for t in st2['trips']:
    trip_anchor.setdefault(t['pt'], set()).add(t['at'])

# 每块 -> 先前 run 的快照列表 [(j, state)]
snap_pool = {}
covered_exec = set()   # 已执行段落实际覆盖的场景 (归纳不变式)
for i, r in enumerate(runs):
    full_scenes = set(r['scenes'])
    my_new = full_scenes - covered_exec          # 本 run 的增量场景, 必须在续段里
    best = None  # (k desc 优先=少点选项, 再 j desc=短存活)
    for k in range(len(r['sels']) - 1, -1, -1):
        B, _ = r['sels'][k]
        if B not in snap_pool: continue
        # 虚拟前缀场景 (bseq 中 B 之前的部分)
        bpos = r['bseq'].index(B)
        pre_scenes = {blocks[bn]['scene'] for bn in r['bseq'][:bpos] if blocks[bn]['scene']}
        if not pre_scenes <= covered_exec: continue  # 前缀场景必须已被实际覆盖
        for j, snap in snap_pool[B]:
            st2 = list(snap)
            for gi in range(NG): st2[gi] = (r['ctx'] >> gi) & 1
            rem_choices = {}
            for at, pick in r['sels'][k:]:
                rem_choices[at] = pick
            b2, s2, sn2, sc2, e2 = simulate_full(r['ctx'], rem_choices, B, tuple(st2))
            if s2 != r['sels'][k:]: continue
            if e2 != r['ending_sim']: continue
            if not my_new <= set(sc2): continue  # 增量场景必须在续段里
            if i in trip_anchor:
                kept = {at for at, _ in r['sels'][k:]}
                if not trip_anchor[i] <= kept: continue
            cand = (k, j, B, set(sc2))
            if best is None or (k, j) > (best[0], best[1]):
                best = cand
    r['reuse'] = best[:3] if best else None
    r['executed'] = best[3] if best else full_scenes
    # 只有"实际执行段"(复用点之后)的快照才能作为后续 run 的锚点
    k_exec = best[0] if best else 0
    exec_blocks = {at for at, _ in r['sels'][k_exec:]}
    for B, snap in r['snaps'].items():
        if B in exec_blocks:
            snap_pool.setdefault(B, []).append((i, snap))
    covered_exec |= r['executed']
    # 该 run 的支线也是已执行内容
    for t in TRIPS:
        if t['pt'] == i:
            covered_exec |= set(t['new'])
    if best:
        k, j, B, _ = best
        print(f"run{i:2d} [{r['name']:12s}]: load run{j} [{runs[j]['name']}] @{B}, 从第 {k+1}/{len(r['sels'])} 个选项点继续")
    else:
        print(f"run{i:2d} [{r['name']:12s}]: 全新开局 ({len(r['sels'])} 选项点)")

json.dump({'runs': [{'kind': r['kind'], 'name': r['name'], 'ctx': r['ctx'], 'choices': r['choices'],
                     'sels': [list(s) for s in r['sels']], 'reuse': r['reuse']} for r in runs]},
          open(D + r'\plan_stage4.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved plan_stage4.json')
