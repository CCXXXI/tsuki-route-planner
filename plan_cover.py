# -*- coding: utf-8 -*-
"""规划器 v2: 最少周目 + 支线绕路 的全覆盖流程
输入: reachability.json (32 ctx 可达集), witnesses.json (每 ctx+块 的见证选择列表)
做法:
 1. 候选周目 = (ctx, 结局块): 用见证选择列表模拟, 得场景集
 2. 贪心: 在当前全局 G 下可行的候选中, 选新增场景最多者; 执行后更新 G
 3. 剩余场景 -> 支线: 找见证路径与已选周目路径的公共前缀, 从分歧选项点存档绕路
 4. 输出 plan.json + 人类可读 plan.md
"""
import json, re, sys, io
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

D = r'C:\Users\ccxxx\Desktop\tsuki_parse'
g = json.load(open(D + r'\flow_graph.json', encoding='utf-8'))
blocks = g['blocks']
reach = json.load(open(D + r'\reachability.json', encoding='utf-8'))
W = json.load(open(D + r'\witnesses.json', encoding='utf-8'))

GATE = ['%cleared', '%clear_ark', '%clear_ciel', '%clear_hisui', '%ark_normalcleared']
REGARDS = ['%ark_regard', '%ciel_regard', '%akiha_regard', '%hisui_regard', '%kohaku_regard']
FLGS = ['%flg1','%flg2','%flg3','%flg4','%flg5','%flg6','%flg7','%flg8','%flg9',
        '%flgA','%flgB','%flgC','%flgD','%flgE','%flgH','%flgI','%flgJ','%flgK','%flgL',
        '%flgM','%flgN','%flgO','%flgP','%flgR','%flgS']
VARS = GATE + REGARDS + FLGS
IDX = {v: i for i, v in enumerate(VARS)}
CAP = {v: 1 for v in GATE} | {v: 40 for v in REGARDS} | {v: 1 for v in FLGS}
NG = len(GATE)

def ev_t(t, st):
    a = st[IDX[t['var']]] if t['var'] in IDX else 0
    v = t['val']
    b = st[IDX[v]] if v in IDX else (0 if v.startswith('%') else int(v))
    return {'==': a==b, '!=': a!=b, '>=': a>=b, '<=': a<=b, '>': a>b, '<': a<b, 'truthy': a!=0}[t['op']]
def ev_c(c, st):
    vals = [ev_t(t, st) for t in c['terms']]
    return all(vals) if c['logic']=='&&' else (any(vals) if c['logic']=='||' else vals[0])
def apply(e, st):
    v = e['var']
    if v not in IDX: return st
    i = IDX[v]
    val = e['val']
    if val in IDX: n = st[IDX[val]]
    elif re.match(r'^-?\d+$', val or ''): n = int(val)
    else: n = 0
    cur = st[i]
    if e['op']=='inc': cur += 1
    elif e['op']=='dec': cur -= 1
    elif e['op']=='add': cur += n
    elif e['op']=='sub': cur -= n
    elif e['op']=='mov': cur = n
    cur = max(0, min(CAP[v], cur))
    if cur == st[i]: return st
    st = list(st); st[i] = cur; return tuple(st)

ENDING_BLOCKS = {
    'f52a': ('arc_true',   ['%cleared', '%clear_ark', '%ark_normalcleared']),
    'f53a': ('ark_good',   ['%cleared', '%clear_ark']),
    'f310': ('ciel_true',  ['%cleared', '%clear_ciel']),
    'f308': ('ciel_good',  ['%cleared', '%clear_ciel']),
    'f385': ('akiha_true', ['%cleared']),
    'f384': ('akiha_good', ['%cleared']),
    'f412': ('hisui_true', ['%cleared', '%clear_hisui']),
    'f413': ('hisui_good', ['%cleared', '%clear_hisui']),
    'f429': ('kohaku_true',['%cleared']),
}

def simulate(ctx_bits, choices):
    """choices: {block: pick_text}. 返回 (bseq, scenes, ending, sels, final_gate_state)"""
    st = tuple((ctx_bits >> i) & 1 for i in range(NG)) + (0,) * (len(VARS) - NG)
    name = 'f20'
    bseq, scenes, sels = [], [], []
    ending = None
    for _ in range(3000):
        if name in ('endofplay', 'END', 'title', 'title2', 'title_tochu', 'gamestart_menu', 'ending'):
            break
        if name not in blocks: break
        b = blocks[name]
        hit = None
        for e in b['pre']:
            if e['kind'] == 'if' and e['act'] == 'goto' and ev_c(e['cond'], st): hit = e['target']; break
            if e['kind'] == 'goto': hit = e['target']; break
        if hit is not None:
            name = hit; continue
        for e in b['effects']: st = apply(e, st)
        bseq.append(name)
        if b['scene']: scenes.append(b['scene'])
        if name in ENDING_BLOCKS: ending = ENDING_BLOCKS[name][0]
        nxt = None
        for e in b['branch']:
            if e['kind'] == 'select' or (e['kind'] == 'if' and e['act'] == 'select' and ev_c(e['cond'], st)):
                opts = e.get('options', [])
                pick = choices.get(name)
                chosen = next((o for o in opts if o['text'].strip() == pick), opts[0] if opts else None)
                if chosen is None: break
                sels.append({'at': name, 'pick': chosen['text'].strip(),
                             'options': [o['text'].strip() for o in opts]})
                nxt = chosen['target']; break
            if e['kind'] == 'if' and e['act'] == 'select':
                continue
            if e['kind'] == 'if' and e['act'] == 'goto':
                if ev_c(e['cond'], st): nxt = e['target']; break
                continue
            if e['kind'] == 'goto': nxt = e['target']; break
            if e['kind'] == 'end': nxt = 'END'; break
        if nxt is None: nxt = b['fallthrough'] or 'END'
        name = nxt
    return bseq, scenes, ending, sels, st[:NG]

# ---------- 1. 构建候选周目 ----------
# 候选: (ctx, 结局块). 见证里存的是选择列表 [{at, pick}]
def witness_choices(ctx, blk):
    wl = W.get(f'{ctx}|{blk}')
    if wl is None: return None
    return {c['at']: c['pick'] for c in wl}

cands = []
for ctx_s, r in reach['contexts'].items():
    ctx = int(ctx_s)
    for eb, (ename, gset) in ENDING_BLOCKS.items():
        ch = witness_choices(ctx, eb)
        if ch is None: continue
        bseq, scenes, ending, sels, fin = simulate(ctx, ch)
        if ending != ename:
            continue  # 见证路径在该结局块之前路过就算数; 校验结局一致
        cands.append({'ctx': ctx, 'ending': ename, 'block': eb,
                      'choices': ch, 'scenes': scenes, 'bseq': bseq, 'sels': sels,
                      'gset': gset})
print(f'候选周目: {len(cands)}')
from collections import Counter
print(Counter(c['ending'] for c in cands))

# ---------- 2. 贪心集合覆盖 (尊重旗标单调) ----------
universe = set(reach['union_scenes'])
covered = set()
G = [0] * NG     # 当前全局 (gate 位)
plan = []

def ctx_feasible(ctx):
    """ctx 的 1 位必须在 G 中已达成 (0 位不限制: 1 只会变多, 见证路径可能失效,
    但我们在选择后重新模拟验证; 这里只要求 1 位子集)"""
    return all((ctx >> i) & 1 <= G[i] for i in range(NG))

def ctx_exact_current(ctx):
    return all(((ctx >> i) & 1) == G[i] for i in range(NG))

while True:
    best = None
    for c in cands:
        if not ctx_exact_current(c['ctx']):
            continue
        new = len(set(c['scenes']) - covered)
        if best is None or new > best[0]:
            best = (new, c)
    if best is None or best[0] == 0:
        break
    new, c = best
    plan.append(c)
    covered |= set(c['scenes'])
    for gv in c['gset']:
        if gv in IDX and IDX[gv] < NG: G[IDX[gv]] = 1
    print(f"周目{len(plan)}: {c['ending']} (ctx={c['ctx']:02d}) 新增 {new}, 累计 {len(covered)}/{len(universe)}")

remaining = universe - covered
print(f'未覆盖: {len(remaining)}: {sorted(remaining)[:30]}')

json.dump({'plan': [{'ctx': c['ctx'], 'ending': c['ending'], 'scenes': c['scenes'],
                     'choices': c['choices'], 'sels': c['sels']} for c in plan],
           'covered': sorted(covered), 'remaining': sorted(remaining),
           'G': G},
          open(D + r'\plan_stage1.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('已保存 plan_stage1.json')
