# -*- coding: utf-8 -*-
"""v4 管线: 5 主周目 (TE/单结局) + 结局支线 (GE 全部支线化)
- ciel_good/akiha_good: 周目中在分歧选项处存档改选 (无门控)
- hisui_good/ark_good: TE 通关后 load 该周目存档 (有通关门控)
- 其余场景: 单选项支线 + 多步支线 (宽松挂载)
输出 plan_stage1_v4 / plan_stage2_v4 / plan_stage4_v4 / attach_v4 / endtrips_v4.json
"""
import os, json, re, sys, io
_HERE = os.path.dirname(os.path.abspath(__file__))
exec(open(os.path.join(_HERE, 'plan_cover.py'), encoding='utf-8').read().split("# ---------- 1.")[0])

D = _HERE
plan10 = json.load(open(D + r'\plan_stage1_v2.json', encoding='utf-8'))['plan']
reach = json.load(open(D + r'\reachability.json', encoding='utf-8'))
W = json.load(open(D + r'\witnesses.json', encoding='utf-8'))
universe = set(reach['union_scenes'])

# 主周目: 5 条 (每线 TE / 琥珀单结局)
MAIN = [0, 1, 2, 3, 4]  # ciel_true, akiha_true, arc_true, hisui_true, kohaku_true
plan = [plan10[i] for i in MAIN]

# 结局支线: (锚周目 idx in plan, 分歧块, GE 选项, 结局名, 是否需 TE 通关后做)
ENDTRIP_DEF = [
    (0, 'f307', {'f307': '１、顺从　爱尔奎特。'}, 'ciel_good', False),
    (1, 'f383', {'f383': '２、……这种事，我做不到。'}, 'akiha_good', False),
    (3, 'f405', {'f411': '２、叫琥珀的名字。'}, 'hisui_good', True),
    (2, 'f194', {'f503': '２、不能忘了爱尔奎特。'}, 'ark_good', True),
]
# 门控通关后全局: hisui +clear_hisui; ark +clear_ark+ark_normalcleared
POST_CTX = {'hisui_good': 31, 'ark_good': 23}

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

# ---------- 结局支线 ----------
endtrips = []
for ri, blk, opt, ge, post in ENDTRIP_DEF:
    r = runs[ri]
    assert blk in r['snaps'], (ge, blk)
    ctx = POST_CTX[ge] if post else r['ctx']
    st0 = list(r['snaps'][blk])
    for gi in range(NG): st0[gi] = (ctx >> gi) & 1   # 存档不带全局旗标, 用当前进度
    ch = dict(opt)
    b2, s2, sn2, sc2, e2 = simulate_full(ctx, ch, blk, tuple(st0))
    assert e2 == ge, (ge, e2, s2)
    cov = sorted({blocks[bn]['scene'] for bn in b2 if blocks[bn]['scene']})
    endtrips.append({'pt': ri, 'at': blk, 'ending': ge, 'post': post,
                     'sels': [{'at': a, 'pick': p} for a, p in s2], 'cov': cov})
    print(f"结局支线 {ge}: 周目{ri+1}@{blk}, {len(s2)} 个选项, 场景 {cov}, post={post}")

# ---------- 单选项支线 ----------
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
for et in endtrips: covered |= set(et['cov'])
remaining = universe - covered
trips = []
for pi, r in enumerate(runs):
    main_pos = {}
    for idx, bn in enumerate(r['bseq']): main_pos.setdefault(bn, idx)
    for k, (at, pick) in enumerate(r['sels']):
        st_snap = r['snaps'][at]
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
print(f'单选项支线: {len(chosen_trips)}, 剩余 {len(rem)}: {sorted(rem)}')

# ---------- merge ----------
trip_anchor = {}
for t in chosen_trips:
    trip_anchor.setdefault(t['pt'], set()).add(t['at'])
for et in endtrips:
    if not et['post']:  # 周目中做的结局支线也要锚点在执行段
        trip_anchor.setdefault(et['pt'], set()).add(et['at'])
snap_pool = {}
covered_exec = set()
for i, r in enumerate(runs):
    full_scenes = set(r['scenes'])
    r['reuse'] = None  # 全部从新游戏开始: 每个存档只在同一场景组内存活, 栏位需求降为 1
    for B, snap in r['snaps'].items():
        snap_pool.setdefault(B, []).append((i, snap))
    covered_exec |= full_scenes
    for t in chosen_trips:
        if t['pt'] == i: covered_exec |= set(t['scenes'])
    for et in endtrips:
        if et['pt'] == i: covered_exec |= set(et['cov'])
    print(f"run{i} [{r['ending']}]: 全新开局")

# ---------- 多步支线 (宽松挂载) ----------
scene2f = {b['scene']: n for n, b in blocks.items() if b['scene']}
attach = []
for s in sorted(rem):
    f = scene2f[s]
    wl = None
    for c in range(32):
        wl = W.get(f'{c}|{f}')
        if wl is not None: break
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
            last_t = max(i2 for i2, bn in enumerate(b2) if blocks[bn]['scene'] == s)
            cov = sorted({blocks[bn]['scene'] for bn in b2[:last_t+1] if blocks[bn]['scene']})
            idx_of = {}
            for i2, bn in enumerate(b2): idx_of.setdefault(bn, i2)
            kept = [x for x in s2 if idx_of.get(x[0], 10**9) < last_t]
            cand = (len(kept), j, B, b2, last_t, kept, cov)
            if best3 is None or cand[0] < best3[0]: best3 = cand
    if best3 is None:
        print(f'!! {s} 无法挂载'); continue
    nsteps, j, B, b2, last_t, kept, cov = best3
    last_blk = blocks[b2[last_t]]
    has_menu = any(e['kind'] == 'select' or (e['kind'] == 'if' and e['act'] == 'select')
                   for e in last_blk['branch'])
    if has_menu:
        stop_block, stop_menu_at = None, b2[last_t]
    elif last_t + 1 < len(b2) and blocks[b2[last_t + 1]]['scene']:
        stop_block, stop_menu_at = b2[last_t + 1], None
    else:
        stop_block, stop_menu_at = None, None
    attach.append({'target': s, 'targets': [s], 'pt': j, 'at': B, 'steps': nsteps,
                   'sels': [{'at': a, 'pick': p} for a, p in kept],
                   'stop_block': stop_block, 'stop_menu_at': stop_menu_at, 'cov': cov})
    print(f'{s}: 挂到 run{j} [{runs[j]["ending"]}] @{B}, {nsteps} 步')

# 合并同路径
grouped = {}
for a in attach:
    key = (a['pt'], a['at'], json.dumps(a['sels'], ensure_ascii=False))
    if key in grouped:
        grouped[key]['targets'] = sorted(set(grouped[key]['targets']) | set(a['targets']))
        grouped[key]['cov'] = sorted(set(grouped[key]['cov']) | set(a['cov']))
    else:
        grouped[key] = dict(a)
attach = list(grouped.values())
print(f'多步支线组数: {len(attach)}')

# ---------- 去重 ----------
base = set()
for i, r in enumerate(runs):
    if r['reuse']:
        k, j, B = r['reuse']
        seg = r['bseq'][r['bseq'].index(B):]
    else:
        seg = r['bseq']
    base |= {blocks[bn]['scene'] for bn in seg if blocks[bn]['scene']}
for et in endtrips: base |= set(et['cov'])

items = []
for ti, t in enumerate(chosen_trips):
    items.append(('trip', ti, set(t['scenes'])))
for ai, a in enumerate(attach):
    items.append(('detour', ai, set(a['cov'])))
def total_without(di):
    tot = set(base)
    for ii, it in enumerate(items):
        if ii != di and it is not None: tot |= it[2]
    return tot
dropped = []
changed = True
while changed:
    changed = False
    for ii in sorted((i for i in range(len(items)) if items[i] is not None),
                     key=lambda i: len(items[i][2])):
        if universe <= total_without(ii):
            dropped.append(items[ii][:2]); items[ii] = None; changed = True
chosen_trips = [t for ti, t in enumerate(chosen_trips) if ('trip', ti) not in dropped]
attach = [a for ai, a in enumerate(attach) if ('detour', ai) not in dropped]
print(f'去重: 删 {len(dropped)} -> 支线 {len(chosen_trips)} + 多步 {len(attach)}')

# ---------- 免读档优化: 汇合后状态等价 => 最后一条支线不读档, 主线侧场景另有覆盖则省略主线选项 ----------
# 全量状态模拟: 记录每个块(应用效果前)的状态
def simulate_states(ctx_bits, choices, start_block, start_state):
    st = start_state
    name = start_block
    bseq, sels, stmap = [], [], {}
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
        stmap.setdefault(name, st)
        for e in b['effects']: st = apply(e, st)
        bseq.append(name)
        if name in ENDING_BLOCKS: ending = ENDING_BLOCKS[name][0]
        nxt = None
        for e in b['branch']:
            if e['kind']=='select' or (e['kind']=='if' and e['act']=='select' and ev_c(e['cond'], st)):
                opts = e.get('options', [])
                pick = choices.get(name)
                chosen = next((o for o in opts if o['text'].strip()==pick), opts[0] if opts else None)
                if chosen is None: break
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
    return bseq, sels, stmap, ending

def detrip_state(start, st, main_pos, min_pos, max_steps=80):
    """同 detrip, 但返回 (scenes, how, stop_block, state_at_stop_entry)"""
    name, cur = start, st
    scenes = []
    rejoin_pending = False
    for _ in range(max_steps):
        if name in ('endofplay','END','title','title2','title_tochu','gamestart_menu','ending') or name not in blocks:
            return scenes, 'terminate', None, cur
        if name in main_pos and main_pos[name] > min_pos:
            if blocks[name]['scene']: return scenes, 'rejoin', name, cur
            rejoin_pending = True
        b = blocks[name]
        hit = None
        for e in b['pre']:
            if e['kind']=='if' and e['act']=='goto' and ev_c(e['cond'], cur): hit = e['target']; break
            if e['kind']=='goto': hit = e['target']; break
        if hit is not None: name = hit; continue
        if b['scene'] and rejoin_pending:
            return scenes, 'rejoin', name, cur
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
            if e['kind']=='end': return scenes, 'terminate', None, cur
        if nxt is None: nxt = b['fallthrough'] or 'END'
        name = nxt
    return scenes, 'overflow', None, cur

def verify_terminal(r, stop_block, st_entry):
    """从 (stop_block 入口处状态) 用 run 剩余选项模拟, 须逐块复现 run 后半并到达同结局"""
    pos = r['bseq'].index(stop_block)
    rem = {a2: p for a2, p in r['sels'] if r['bseq'].index(a2) >= pos}
    b3, s3, sm3, e3 = simulate_states(r['ctx'], rem, stop_block, st_entry)
    expected = [(a2, p) for a2, p in r['sels'] if r['bseq'].index(a2) >= pos]
    return s3 == expected and e3 == r['ending']

# 覆盖池 (判断主线侧场景是否有他处覆盖)
run_exec = []
for j, r2 in enumerate(runs):
    seg = r2['bseq'][r2['bseq'].index(r2['reuse'][2]):] if r2['reuse'] else r2['bseq']
    run_exec.append({blocks[bn]['scene'] for bn in seg if blocks[bn]['scene']})
items_pool = set()
for t in chosen_trips: items_pool |= set(t['scenes'])
for a in attach: items_pool |= set(a['cov'])
for et in endtrips: items_pool |= set(et['cov'])

groups = {}
for t in chosen_trips: groups.setdefault((t['pt'], t['at']), []).append(('trip', t))
for a in attach: groups.setdefault((a['pt'], a['at']), []).append(('detour', a))

drop_main = {}
for (i, at), items_g in groups.items():
    r = runs[i]
    main_pos = {}
    for idx, bn in enumerate(r['bseq']): main_pos.setdefault(bn, idx)
    min_pos = main_pos.get(at, 0)
    best_term = None
    for kind, it in items_g:
        if kind == 'trip':
            if it['how'] != 'rejoin': continue
            sc, how, stop_blk, st_stop = detrip_state(
                next(o['target'] for e in blocks[at]['branch'] if e['kind']=='select'
                     for o in e['options'] if o['text'].strip() == it['pick']),
                r['snaps'][at], main_pos, min_pos)
            if stop_blk is None: continue
            if stop_blk not in r['bseq']: continue
            if verify_terminal(r, stop_blk, st_stop):
                cand = (len(it['scenes']), 'trip', it, stop_blk)
                if best_term is None or cand[0] > best_term[0]: best_term = cand
        else:
            if not it.get('stop_block'): continue  # menu/title 停止的不做终点
            blk = it['stop_block']
            if blk not in r['bseq']: continue
            guide = {s['at']: s['pick'] for s in it['sels']}
            b2, s2, sm2, e2 = simulate_states(r['ctx'], guide, at, r['snaps'][at])
            st_stop = sm2.get(blk)
            if st_stop is None: continue
            if verify_terminal(r, blk, st_stop):
                cand = (len(it['cov']), 'detour', it, blk)
                if best_term is None or cand[0] > best_term[0]: best_term = cand
    if best_term is None: continue
    _, kind, it, stop_blk = best_term
    it['terminal'] = True
    it['terminal_stop'] = stop_blk
    # 主线侧场景 = run 主路径上 at 之后、stop_blk 之前的场景
    pos_a = r['bseq'].index(at)
    pos_s = r['bseq'].index(stop_blk)
    main_side = {blocks[bn]['scene'] for bn in r['bseq'][pos_a+1:pos_s] if blocks[bn]['scene']}
    # 他处覆盖 = 其他周目执行段 ∪ 本周目执行段去掉本段 ∪ 所有支线/结局支线
    cov_else = items_pool | set().union(*[run_exec[j] for j in range(len(runs)) if j != i]) \
        | (run_exec[i] - main_side)
    if main_side <= cov_else:
        drop_main[(i, at)] = True
    print(f"组 ({i},{at}): 终点支线={kind} 目标={it.get('new', it.get('targets'))} 免读档✓ 省略主线选项={drop_main.get((i,at), False)} (主线侧 {sorted(main_side)})")

json.dump({'drop_main': [f'{i}|{at}' for i, at in drop_main]},
          open(D + r'\dropmain_v4.json', 'w', encoding='utf-8'), ensure_ascii=False)

others_trips = [set(t['new']) for t in chosen_trips]
others_det = [set(a['targets']) for a in attach]
for ti, t in enumerate(chosen_trips):
    o = set().union(*(others_trips[:ti] + others_trips[ti+1:] + others_det)) if items else set()
    t['disp'] = sorted(set(t['scenes']) - base - o)
for ai, a in enumerate(attach):
    o = set().union(*(others_det[:ai] + others_det[ai+1:] + others_trips)) if items else set()
    a['disp'] = sorted(set(a['cov']) - base - o)
for et in endtrips:
    et['disp'] = sorted(set(et['cov']) - set(runs[et['pt']]['scenes']))

# ---------- 覆盖验证 ----------
allcov = set(base)
for t in chosen_trips: allcov |= set(t['scenes'])
for a in attach: allcov |= set(a['cov'])
print('覆盖验证:', len(allcov), '/', len(universe), '缺失', sorted(universe - allcov))

json.dump({'plan': plan}, open(D + r'\plan_stage1_v4.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({'trips': chosen_trips}, open(D + r'\plan_stage2_v4.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({'runs': [{'kind': 'pt', 'name': r['ending'], 'ctx': r['ctx'], 'choices': r['choices'],
                     'sels': [list(x) for x in r['sels']], 'reuse': r['reuse']} for r in runs]},
          open(D + r'\plan_stage4_v4.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(attach, open(D + r'\attach_v4.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(endtrips, open(D + r'\endtrips_v4.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('v4 已保存')
