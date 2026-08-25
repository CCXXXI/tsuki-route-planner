# -*- coding: utf-8 -*-
"""全图可达性 v2: 状态饱和钳制
- GLOBALS 钳制到 {0,1} (条件只测 0/非0)
- regard 钳制到 [0,20] (最大测试常数 16)
- flg 钳制到 {0,1}
- 状态=元组本身, 不存 dict
"""
import json, re, sys, io
from collections import deque
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

g = json.load(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\flow_graph.json', encoding='utf-8'))
blocks = g['blocks']

GLOBALS = ['%cleared', '%clear_ark', '%clear_ciel', '%clear_akiha', '%clear_hisui', '%clear_kohaku',
           '%ark_normalcleared', '%clear_ark_true', '%clear_ark_good', '%clear_ciel_true',
           '%clear_ciel_good', '%clear_akiha_true', '%clear_akiha_good', '%clear_hisui_true',
           '%clear_hisui_good', '%clear_kohaku_true']
REGARDS = ['%ark_regard', '%ciel_regard', '%akiha_regard', '%hisui_regard', '%kohaku_regard']
FLGS = ['%flg1','%flg2','%flg3','%flg4','%flg5','%flg6','%flg7','%flg8','%flg9',
        '%flgA','%flgB','%flgC','%flgD','%flgE','%flgH','%flgI','%flgJ','%flgK','%flgL',
        '%flgM','%flgN','%flgO','%flgP','%flgR','%flgS']
VARS = GLOBALS + REGARDS + FLGS
IDX = {v: i for i, v in enumerate(VARS)}
CAP = {}
for v in GLOBALS: CAP[v] = 1
for v in REGARDS: CAP[v] = 40
for v in FLGS: CAP[v] = 1
NG = len(GLOBALS)  # 前缀是全局

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

def nexts(name, st):
    if name in ('END','title','title_tochu','title2','gamestart_menu','ending'): return []
    if name == 'endofplay':
        return [('f20', st[:NG] + (0,) * (len(VARS) - NG))]
    b = blocks[name]
    for e in b['pre']:
        if e['kind']=='if' and e['act']=='goto' and ev_c(e['cond'], st): return [(e['target'], st)]
        if e['kind']=='goto': return [(e['target'], st)]
    for e in b['effects']: st = apply(e, st)
    for e in b['branch']:
        if e['kind']=='select':
            return [(o['target'], st) for o in e['options']]
        if e['kind']=='if' and e['act']=='select':
            if ev_c(e['cond'], st): return [(o['target'], st) for o in e.get('options',[])]
            continue
        if e['kind']=='if' and e['act']=='goto':
            if ev_c(e['cond'], st): return [(e['target'], st)]
            continue
        if e['kind']=='goto': return [(e['target'], st)]
        if e['kind']=='end': return []
    return [(b['fallthrough'], st)] if b['fallthrough'] else []

import time
init = (0,) * len(VARS)
seen = set([('f20', init)])
q = deque([('f20', init)])
t0 = time.time()
while q:
    name, st = q.popleft()
    for nxt, st2 in nexts(name, st):
        k2 = (nxt, st2)
        if k2 not in seen:
            seen.add(k2)
            q.append(k2)
    if len(seen) % 200000 == 0:
        print(f'... {len(seen)} 状态, 队列 {len(q)}, {time.time()-t0:.0f}s', flush=True)

f_blocks = {n for n in blocks if re.match(r'^f\d', n)}
reach_f = {n for n, _ in seen if n in f_blocks}
reach_scenes = {blocks[n]['scene'] for n in reach_f if blocks[n]['scene']}
all_scenes = {blocks[n]['scene'] for n in f_blocks if blocks[n]['scene']}
print(f'可达状态数: {len(seen)}')
print(f'可达 f 块: {len(reach_f)}/{len(f_blocks)}')
print(f'可达场景: {len(reach_scenes)}/{len(all_scenes)}')
unreach_f = sorted(f_blocks - reach_f, key=lambda x: blocks[x]['line'])
print(f'不可达 f 块 ({len(unreach_f)}): {unreach_f}')
print(f'不可达场景: {sorted(all_scenes - reach_scenes)}')
json.dump({'reachable_blocks': sorted(reach_f), 'reachable_scenes': sorted(reach_scenes),
           'unreachable_blocks': unreach_f, 'unreachable_scenes': sorted(all_scenes - reach_scenes)},
          open(r'C:\Users\ccxxx\Desktop\tsuki_parse\reachability.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
