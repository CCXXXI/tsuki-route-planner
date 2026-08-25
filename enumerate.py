# -*- coding: utf-8 -*-
"""路径枚举 v2: 状态记忆化 + Pareto 剪枝
solve(block, state) -> 该状态出发的所有 Pareto 最优结局完成式:
  [(ending, frozenset(suffix_scenes), tuple(suffix_choices))]
支配规则: 同 ending 下 scenes 为超集者占优.
"""
import json, re, sys, io
sys.setrecursionlimit(100000)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

g = json.load(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\flow_graph.json', encoding='utf-8'))
blocks = g['blocks']

# 只保留影响分支的变量 (sceneskip/1NNN 与路线无关)
KEY_VARS = ['%ark_regard', '%ciel_regard', '%akiha_regard', '%hisui_regard', '%kohaku_regard',
            '%flg5', '%flg7', '%flg8', '%flgE', '%flgK', '%flgL', '%flgM', '%flgN', '%flgP', '%flgS',
            '%cleared', '%clear_hisui', '%ark_normalcleared']

def skey(st): return tuple(st.get(v, 0) for v in KEY_VARS)

def eval_term(t, st):
    a = st.get(t['var'], 0)
    b = st.get(t['val'], 0) if t['val'].startswith('%') else int(t['val'])
    return {'==': a == b, '!=': a != b, '>=': a >= b, '<=': a <= b,
            '>': a > b, '<': a < b, 'truthy': a != 0}[t['op']]

def eval_cond(c, st):
    vals = [eval_term(t, st) for t in c['terms']]
    return all(vals) if c['logic'] == '&&' else (any(vals) if c['logic'] == '||' else vals[0])

def apply_effect(e, st):
    v = e['var']
    if not v.startswith('%'): return
    val = e['val']
    if val.startswith('%'): n = st.get(val, 0)
    elif re.match(r'^-?\d+$', val or ''): n = int(val)
    else: n = 0
    if e['op'] == 'inc': st[v] = st.get(v, 0) + 1
    elif e['op'] == 'dec': st[v] = st.get(v, 0) - 1
    elif e['op'] == 'add': st[v] = st.get(v, 0) + n
    elif e['op'] == 'sub': st[v] = st.get(v, 0) - n
    elif e['op'] == 'mov': st[v] = n

memo = {}
ENDING_CLEARS = ['%clear_ark_true', '%clear_ark_good', '%clear_ciel_true', '%clear_ciel_good',
                 '%clear_akiha_true', '%clear_akiha_good', '%clear_hisui_true', '%clear_hisui_good',
                 '%clear_kohaku_true']

def prune(comps):
    """Pareto: (ending, scenes) 去重 + 支配剪枝"""
    best = {}
    for ending, scenes, choices in comps:
        k = (ending, scenes)
        if k not in best:
            best[k] = (ending, scenes, choices)
    out = list(best.values())
    res = []
    for i, (e1, s1, c1) in enumerate(out):
        dominated = False
        for j, (e2, s2, c2) in enumerate(out):
            if i != j and e1 == e2 and s1 < s2:
                dominated = True; break
        if not dominated: res.append((e1, s1, c1))
    return res

def solve(name, st):
    if name in ('endofplay', 'END'):
        ending = None
        for f in ENDING_CLEARS:
            if st.get(f, 0) > 0: ending = f.replace('%clear_', ''); break
        return [(ending or 'BAD_END', frozenset(), ())]
    if name in ('title', 'title_tochu', 'title2', 'gamestart_menu', 'ending'):
        return [('BAD_END', frozenset(), ())]
    if name not in blocks:
        return [('MISSING:' + name, frozenset(), ())]
    key = (name, skey(st))
    if key in memo: return memo[key]
    memo[key] = []  # 防环占位
    b = blocks[name]
    # pre 链
    hit = None
    for e in b['pre']:
        if e['kind'] == 'if' and e['act'] == 'goto' and eval_cond(e['cond'], st): hit = e['target']; break
        if e['kind'] == 'goto': hit = e['target']; break
    if hit is not None:
        res = [(e_, s_, c_) for e_, s_, c_ in solve(hit, st)]
        memo[key] = res; return res
    # 场景 + 效果
    st2 = dict(st)
    for e in b['effects']: apply_effect(e, st2)
    scene = b['scene']
    # branch
    out = []
    br = b['branch']
    handled = False
    for e in br:
        if e['kind'] == 'select':
            for o in e['options']:
                for e_, s_, c_ in solve(o['target'], st2):
                    out.append((e_, s_, ((name, o['text'].strip(), None),) + c_))
            handled = True; break
        if e['kind'] == 'if' and e['act'] == 'select':
            if eval_cond(e['cond'], st2):
                for o in e.get('options', []):
                    for e_, s_, c_ in solve(o['target'], st2):
                        out.append((e_, s_, ((name, o['text'].strip(), e['cond']['raw']),) + c_))
                handled = True; break
            continue
        if e['kind'] == 'if' and e['act'] == 'goto':
            if eval_cond(e['cond'], st2):
                for e_, s_, c_ in solve(e['target'], st2):
                    out.append((e_, s_, ((name, '→' + e['target'], e['cond']['raw']),) + c_))
                handled = True; break
            continue
        if e['kind'] == 'goto':
            for e_, s_, c_ in solve(e['target'], st2): out.append((e_, s_, c_))
            handled = True; break
        if e['kind'] == 'end':
            out.append(('END', frozenset(), ())); handled = True; break
    if not handled:
        nxt = b['fallthrough'] or 'END'
        for e_, s_, c_ in solve(nxt, st2): out.append((e_, s_, c_))
    if scene:
        out = [(e_, s_ | {scene}, c_) for e_, s_, c_ in out]
    res = prune(out)
    memo[key] = res
    return res

roots = solve('f20', {})
print(f'f20 出发的 Pareto 完成式: {len(roots)}')
from collections import Counter
c = Counter(e for e, s, ch in roots)
for k, v in c.most_common():
    sc = max(len(s) for e, s, ch in roots if e == k)
    print(f'  {k}: {v} 种, 最多场景 {sc}')
print(f'memo 状态数: {len(memo)}')

json.dump([{'ending': e, 'scenes': sorted(s), 'choices': [
    {'at': a, 'pick': p, 'cond': cd} for a, p, cd in ch]}
    for e, s, ch in roots],
    open(r'C:\Users\ccxxx\Desktop\tsuki_parse\paths.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('已写出 paths.json')
