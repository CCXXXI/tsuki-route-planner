# -*- coding: utf-8 -*-
"""把补课 run 改写为正常周目的多步支线
对每个补课 run r:
  在其选项序列的每个后缀起点 B (从晚到早), 尝试所有正常周目 j 在 B 的快照状态,
  以周目 j 的全局 ctx 模拟 r 的剩余选项 -> 完全复现且覆盖目标场景 => 可作为 j 的支线
输出 attach.json
"""
import json, re, sys, io
exec(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\plan_cover.py', encoding='utf-8').read().split("# ---------- 1.")[0])

D = r'C:\Users\ccxxx\Desktop\tsuki_parse'
plan = json.load(open(D + r'\plan_stage1_v2.json', encoding='utf-8'))['plan']
st2 = json.load(open(D + r'\plan_stage2_v2.json', encoding='utf-8'))
st3 = json.load(open(D + r'\plan_stage3_v2.json', encoding='utf-8'))

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

# 正常周目快照池: block -> [(j, state, sel_idx_in_j)]  (只含最终执行段内的块)
st4 = json.load(open(D + r'\plan_stage4.json', encoding='utf-8'))
exec_from = {}
for i, r in enumerate(st4['runs']):
    exec_from[i] = r['reuse'][0] if r['reuse'] else 0
pt_snaps = {}
pt_sels = {}
pt_mainpos = {}
for j, P in enumerate(plan):
    bseq, sels, snaps, scenes, ending = simulate_full(P['ctx'], P['choices'])
    pt_sels[j] = sels
    pt_mainpos[j] = {}
    for idx, bn in enumerate(bseq): pt_mainpos[j].setdefault(bn, idx)
    exec_blocks = {at for at, _ in sels[exec_from[j]:]}
    for B, st in snaps.items():
        if B not in exec_blocks: continue
        k = next(k for k, (a, _) in enumerate(sels) if a == B)
        pt_snaps.setdefault(B, []).append((j, st, k))

# 每个补课 run 的"目标新场景" (按 stage3 顺序计算)
rem_pool = set(st2['remaining'])
bukou_targets = []
for r in st3['runs']:
    newhere = sorted(s for s in r['scenes'] if s in rem_pool)
    rem_pool -= set(r['scenes'])
    bukou_targets.append(set(newhere))

result = []
for ri, r in enumerate(st3['runs']):
    targets = bukou_targets[ri]
    bseq, sels, snaps, scenes, ending = simulate_full(r['ctx'], r['choices'])
    best = None
    for k in range(len(sels) - 1, -1, -1):
        B, _ = sels[k]
        if B not in pt_snaps: continue
        rem_choices = {}
        for at, pick in sels[k:]: rem_choices[at] = pick
        for j, st_pt, kj in pt_snaps[B]:
            st2l = list(st_pt)
            for gi in range(NG): st2l[gi] = (plan[j]['ctx'] >> gi) & 1
            b2, s2, sn2, sc2, e2 = simulate_full(plan[j]['ctx'], rem_choices, B, tuple(st2l))
            if s2 != sels[k:]: continue
            if not targets <= set(sc2): continue
            # 支线终点: 最后一个新场景之后的下一个场景 / 或终止
            last_new_idx = max(i2 for i2, bn in enumerate(b2) if blocks[bn]['scene'] in targets)
            stop_block = b2[last_new_idx + 1] if last_new_idx + 1 < len(b2) else None
            hit_ending = e2
            cand = (k, j, B, stop_block, hit_ending, len(sels) - k)
            if best is None or (cand[0], -cand[5]) > (best[0], -best[5]):
                best = cand
        # 找到最深可行层就停 (k 从大到小)
        if best and best[0] == k: break
    if best:
        k, j, B, stop_block, hit_ending, nsteps = best
        detour_sels = [{'at': a, 'pick': p} for a, p in sels[k:]]
        result.append({'bukou': ri, 'target': r['target'], 'targets': sorted(targets),
                       'pt': j, 'at': B, 'steps': nsteps, 'sels': detour_sels,
                       'stop_block': stop_block, 'hit_ending': hit_ending})
        print(f"补课-{r['target']}: 挂到周目{j+1} [{plan[j]['ending']}] @{B}, {nsteps} 步, "
              f"stop={stop_block}, 结局={hit_ending}")
    else:
        # 退路1: 宽松挂载 — 允许中间路径不同, 只要从锚点出发能覆盖目标场景
        # (指令 = 该周目 ctx 下实际的选项序列)
        best3 = None
        for B, cands in pt_snaps.items():
            for j, st_pt, kj in cands:
                st2l = list(st_pt)
                for gi in range(NG): st2l[gi] = (plan[j]['ctx'] >> gi) & 1
                b2, s2, sn2, sc2, e2 = simulate_full(plan[j]['ctx'], r['choices'], B, tuple(st2l))
                if not targets <= set(sc2): continue
                if e2 is not None: continue  # 不能撞进别的结局
                last_idx = max(i2 for i2, bn in enumerate(b2) if blocks[bn]['scene'] in targets)
                stop_block = b2[last_idx + 1] if last_idx + 1 < len(b2) else None
                cand = (len(s2), j, B, stop_block, s2)
                if best3 is None or cand[0] < best3[0]:
                    best3 = cand
        if best3:
            nsteps, j, B, stop_block, s2 = best3
            detour_sels = [{'at': a, 'pick': p} for a, p in s2]
            result.append({'bukou': ri, 'target': r['target'], 'targets': sorted(targets),
                           'pt': j, 'at': B, 'steps': nsteps, 'sels': detour_sels,
                           'stop_block': stop_block, 'hit_ending': None})
            print(f"补课-{r['target']}: (宽松)挂到周目{j+1} [{plan[j]['ending']}] @{B}, {nsteps} 步")
            continue
        # 退路2: 作为独立速通 run, 找最深 load 锚点 (用补课自身 ctx, 要求目标场景在续段)
        best2 = None
        for k in range(len(sels) - 1, -1, -1):
            B, _ = sels[k]
            if B not in pt_snaps: continue
            rem_choices = {}
            for at, pick in sels[k:]: rem_choices[at] = pick
            for j, st_pt, kj in pt_snaps[B]:
                st2l = list(st_pt)
                for gi in range(NG): st2l[gi] = (r['ctx'] >> gi) & 1
                b2, s2, sn2, sc2, e2 = simulate_full(r['ctx'], rem_choices, B, tuple(st2l))
                if s2 != sels[k:]: continue
                if not targets <= set(sc2): continue
                cand = (k, j, B)
                if best2 is None or (k, j) > (best2[0], best2[1]):
                    best2 = cand
            if best2 and best2[0] == k: break
        result.append({'bukou': ri, 'target': r['target'], 'targets': sorted(targets),
                       'pt': None, 'load_from': best2 and [best2[1], best2[2]],
                       'skip_to': best2 and best2[0], 'ctx': r['ctx'],
                       'choices': r['choices'], 'scenes': scenes})
        print(f"补课-{r['target']}: 保留为速通 run"
              + (f", load 周目{best2[1]+1} @{best2[2]} 从第 {best2[0]+1}/{len(sels)} 选项点" if best2 else ", 从头"))

json.dump(result, open(D + r'\attach.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
ok = sum(1 for x in result if x['pt'] is not None)
print(f'\n可挂载: {ok}/{len(result)}')
