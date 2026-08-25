# -*- coding: utf-8 -*-
"""阶段2: 支线绕路覆盖剩余场景
支线定义: 已选周目 P 在选项点 c 选了 X; 存档改选 Y, 从 Y 出发按默认第一选择前进,
直到 (a) 汇合到 P 的后续块 (b) 到 endofplay/结局 (c) 超步数.
支线成本 = 新场景数 (玩家要读的量), 收益 = 覆盖的未覆盖场景.
"""
import json, re, sys, io
exec(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\plan_cover.py', encoding='utf-8').read().split("# ---------- 1.")[0])

D = r'C:\Users\ccxxx\Desktop\tsuki_parse'
reach = json.load(open(D + r'\reachability.json', encoding='utf-8'))
st1 = json.load(open(D + r'\plan_stage1.json', encoding='utf-8'))
plan = st1['plan']
covered = set(st1['covered'])
universe = set(reach['union_scenes'])
remaining = universe - covered

def simulate_snaps(ctx_bits, choices):
    """同 simulate, 但记录每个选项点的状态快照与 bseq 位置"""
    st = tuple((ctx_bits >> i) & 1 for i in range(NG)) + (0,) * (len(VARS) - NG)
    name = 'f20'
    bseq, scenes, sels, snaps = [], [], [], {}
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
        nxt = None
        for e in b['branch']:
            if e['kind']=='select' or (e['kind']=='if' and e['act']=='select' and ev_c(e['cond'], st)):
                opts = e.get('options', [])
                pick = choices.get(name)
                chosen = next((o for o in opts if o['text'].strip()==pick), opts[0] if opts else None)
                if chosen is None: break
                snaps[name] = (st, len(bseq)-1)
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
    return bseq, scenes, sels, snaps

def detrip(start, st, main_set, main_min_pos, bseq_ref, max_steps=80, prefer=None):
    """从 (start, st) 按默认选择前进. main_set: {块: 最小位置}; 汇合=到达 pos>main_min_pos 的块"""
    name, cur = start, st
    scenes, path = [], []
    for _ in range(max_steps):
        if name in ('endofplay','END','title','title2','title_tochu','gamestart_menu','ending') or name not in blocks:
            return scenes, path, 'terminate'
        if name in main_set and bseq_ref.index(name) > main_min_pos if name in bseq_ref else False:
            return scenes, path, 'rejoin'
        b = blocks[name]
        hit = None
        for e in b['pre']:
            if e['kind']=='if' and e['act']=='goto' and ev_c(e['cond'], cur): hit = e['target']; break
            if e['kind']=='goto': hit = e['target']; break
        if hit is not None:
            if hit in main_set: return scenes, path, 'rejoin'
            name = hit; continue
        for e in b['effects']: cur = apply(e, cur)
        path.append(name)
        if b['scene']: scenes.append(b['scene'])
        nxt = None
        for e in b['branch']:
            if e['kind']=='select' or (e['kind']=='if' and e['act']=='select' and ev_c(e['cond'], cur)):
                opts = e.get('options', [])
                if not opts: break
                chosen = opts[0]
                if prefer and name in prefer:
                    chosen = next((o for o in opts if o['text'].strip()==prefer[name]), opts[0])
                nxt = chosen['target']; break
            if e['kind']=='if' and e['act']=='select': continue
            if e['kind']=='if' and e['act']=='goto':
                if ev_c(e['cond'], cur): nxt = e['target']; break
                continue
            if e['kind']=='goto': nxt = e['target']; break
            if e['kind']=='end': return scenes, path, 'terminate'
        if nxt is None: nxt = b['fallthrough'] or 'END'
        if nxt in main_set and nxt in bseq_ref and bseq_ref.index(nxt) > main_min_pos:
            return scenes, path, 'rejoin'
        name = nxt
    return scenes, path, 'overflow'

# ---------- 收集所有候选支线 ----------
trips = []
for pi, P in enumerate(plan):
    bseq, scenes, sels, snaps = simulate_snaps(P['ctx'], P['choices'])
    pos = {n: i for i, n in enumerate(bseq)}
    main_set = set(bseq)
    for s in sels:
        c = s['at']
        st_snap, ppos = snaps[c]
        for txt, tgt in s['options']:
            if txt == s['pick']: continue
            sc, path, how = detrip(tgt, st_snap, main_set, ppos, bseq)
            newsc = [x for x in sc if x in remaining]
            if newsc:
                trips.append({'pt': pi, 'at': c, 'pick': txt, 'instead_of': s['pick'],
                              'scenes': sc, 'new': sorted(set(newsc)), 'how': how, 'len': len(path)})
print(f'候选支线: {len(trips)}')

# ---------- 贪心选支线 ----------
covered2 = set(covered)
chosen_trips = []
rem = set(remaining)
while True:
    best, bi = 0, None
    for i, t in enumerate(trips):
        n = len([s for s in t['new'] if s in rem])
        if n > best: best, bi = n, i
    if bi is None: break
    t = trips[bi]
    chosen_trips.append(t)
    rem -= set(t['new'])
    covered2 |= set(t['new'])
print(f'选出支线: {len(chosen_trips)}, 覆盖后剩余 {len(rem)}')
print('剩余场景:', sorted(rem))

# 支线明细
for t in chosen_trips:
    print(f"周目{t['pt']+1}({plan[t['pt']]['ending']}) @{t['at']}: 改选「{t['new'] and t['pick']}」(原:{t['instead_of']}) -> {t['how']}, 新场景 {sorted(set(t['new']))}")

json.dump({'trips': chosen_trips, 'remaining': sorted(rem), 'covered': sorted(covered2)},
          open(D + r'\plan_stage2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
