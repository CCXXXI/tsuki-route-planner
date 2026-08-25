# -*- coding: utf-8 -*-
"""状态空间规模测量: 只做 (block, 关键状态) BFS, 不展开路径"""
import json, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
g = json.load(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\flow_graph.json', encoding='utf-8'))
blocks = g['blocks']
KEY_VARS = ['%ark_regard', '%ciel_regard', '%akiha_regard', '%hisui_regard', '%kohaku_regard',
            '%flg5', '%flg7', '%flg8', '%flgE', '%flgK', '%flgL', '%flgM', '%flgN', '%flgP', '%flgS',
            '%cleared', '%clear_hisui', '%ark_normalcleared']
def skey(st): return tuple(st.get(v, 0) for v in KEY_VARS)
def ev_t(t, st):
    a = st.get(t['var'], 0)
    b = st.get(t['val'], 0) if t['val'].startswith('%') else int(t['val'])
    return {'==': a==b, '!=': a!=b, '>=': a>=b, '<=': a<=b, '>': a>b, '<': a<b, 'truthy': a!=0}[t['op']]
def ev_c(c, st):
    vals = [ev_t(t, st) for t in c['terms']]
    return all(vals) if c['logic']=='&&' else (any(vals) if c['logic']=='||' else vals[0])
def apply(e, st):
    v = e['var']
    if not v.startswith('%'): return
    val = e['val']
    n = st.get(val,0) if val.startswith('%') else (int(val) if re.match(r'^-?\d+$', val or '') else 0)
    if e['op']=='inc': st[v]=st.get(v,0)+1
    elif e['op']=='dec': st[v]=st.get(v,0)-1
    elif e['op']=='add': st[v]=st.get(v,0)+n
    elif e['op']=='sub': st[v]=st.get(v,0)-n
    elif e['op']=='mov': st[v]=n

def nexts(name, st):
    """返回 [(next, st_after_effects_or_same)]"""
    if name in ('endofplay','END','title','title_tochu','title2','gamestart_menu','ending'): return []
    b = blocks[name]
    for e in b['pre']:
        if e['kind']=='if' and e['act']=='goto' and ev_c(e['cond'], st): return [(e['target'], st)]
        if e['kind']=='goto': return [(e['target'], st)]
    st2 = dict(st)
    for e in b['effects']: apply(e, st2)
    out = []
    for e in b['branch']:
        if e['kind']=='select':
            return [(o['target'], st2) for o in e['options']]
        if e['kind']=='if' and e['act']=='select':
            if ev_c(e['cond'], st2): return [(o['target'], st2) for o in e.get('options',[])]
            continue
        if e['kind']=='if' and e['act']=='goto':
            if ev_c(e['cond'], st2): return [(e['target'], st2)]
            continue
        if e['kind']=='goto': return [(e['target'], st2)]
        if e['kind']=='end': return []
    return [(b['fallthrough'], st2)] if b['fallthrough'] else []

from collections import deque
seen = set()
q = deque([('f20', ())])
q = deque([('f20', tuple())])
init = {}
q = deque([('f20', skey(init))])
statemap = {('f20', skey(init)): dict(init)}
while q:
    name, sk = q.popleft()
    if (name, sk) in seen: continue
    seen.add((name, sk))
    st = statemap[(name, sk)]
    for nxt, st2 in nexts(name, st):
        k2 = (nxt, skey(st2))
        if k2 not in statemap:
            statemap[k2] = dict(st2)
        if k2 not in seen:
            q.append(k2)
print(f'可达 (块,状态) 数: {len(seen)}')
print(f'涉及块数: {len({n for n,_ in seen})}')
ends = {}
for (n, sk), st in statemap.items():
    if n == 'f20': continue
print('各好感度最大值:', {v: max((s.get(v,0) for s in statemap.values()), default=0) for v in KEY_VARS[:5]})
