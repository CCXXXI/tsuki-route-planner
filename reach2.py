# -*- coding: utf-8 -*-
"""分上下文可达性 + 见证路径
门控相关的全局变量只有: cleared, clear_ark, clear_ciel, clear_hisui, ark_normalcleared
=> 枚举 2^5 = 32 种上下文, 每种做带见证的 BFS (块, 局部状态)
输出:
  reachability.json   每上下文可达块/场景 + 全集
  witnesses.json      每 (上下文, 块) 一条到达路径 (前驱链压缩为选择列表)
"""
import json, re, sys, io, time
from collections import deque
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

g = json.load(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\flow_graph.json', encoding='utf-8'))
blocks = g['blocks']

GATE_GLOBALS = ['%cleared', '%clear_ark', '%clear_ciel', '%clear_hisui', '%ark_normalcleared']
REGARDS = ['%ark_regard', '%ciel_regard', '%akiha_regard', '%hisui_regard', '%kohaku_regard']
FLGS = ['%flg1','%flg2','%flg3','%flg4','%flg5','%flg6','%flg7','%flg8','%flg9',
        '%flgA','%flgB','%flgC','%flgD','%flgE','%flgH','%flgI','%flgJ','%flgK','%flgL',
        '%flgM','%flgN','%flgO','%flgP','%flgR','%flgS']
VARS = GATE_GLOBALS + REGARDS + FLGS
IDX = {v: i for i, v in enumerate(VARS)}
CAP = {v: 1 for v in GATE_GLOBALS} | {v: 40 for v in REGARDS} | {v: 1 for v in FLGS}
NG = len(GATE_GLOBALS)

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

# 预编译每块的转移: [(cond_or_None, effects, [(target, choice_text)])]
# 语义: 依序找第一个 cond 成立的条目; 效果在进入分支前应用
def compile_block(name):
    b = blocks[name]
    # pre 链 => [(cond, target)] + 可能的无条件 goto
    pre = []
    for e in b['pre']:
        if e['kind']=='if' and e['act']=='goto': pre.append((e['cond'], e['target']))
        elif e['kind']=='goto': pre.append((None, e['target']))
    # branch => 结构: select | if-goto 链 + 兜底 goto/fallthrough
    br = []
    for e in b['branch']:
        if e['kind']=='select':
            br.append(('select', None, [(o['target'], o['text'].strip()) for o in e['options']])); break
        if e['kind']=='if' and e['act']=='select':
            br.append(('select', e['cond'], [(o['target'], o['text'].strip()) for o in e.get('options',[])]))
            # 不 break: 条件不成立继续看后续
            continue
        if e['kind']=='if' and e['act']=='goto':
            br.append(('goto', e['cond'], [(e['target'], None)])); continue
        if e['kind']=='goto':
            br.append(('goto', None, [(e['target'], None)])); break
        if e['kind']=='end':
            br.append(('end', None, [])); break
    if br and br[-1][1] is not None and b['fallthrough']:
        # 末尾是条件跳转 -> 条件全不成立时落到下一标签
        br.append(('goto', None, [(b['fallthrough'], None)]))
    if not br and b['fallthrough']:
        br = [('goto', None, [(b['fallthrough'], None)])]
    return pre, b['effects'], br, b['scene']

COMPILED = {n: compile_block(n) for n in blocks}

def nexts(name, st):
    """[(target, st', choice_text_or_None)]"""
    if name in ('END','title','title_tochu','title2','gamestart_menu','ending'): return []
    if name == 'endofplay': return []
    pre, effects, br, scene = COMPILED[name]
    for cond, tgt in pre:
        if cond is None or ev_c(cond, st):
            return [(tgt, st, None)]
    for e in effects: st = apply(e, st)
    for typ, cond, opts in br:
        if cond is not None and not ev_c(cond, st): continue
        return [(t, st, txt) for t, txt in opts]
    return []

f_blocks = {n for n in blocks if re.match(r'^f\d', n)}
all_scenes = {blocks[n]['scene'] for n in f_blocks if blocks[n]['scene']}

result = {}
witness = {}   # (ctx, block) -> choice list
t_all = time.time()
for ctx_bits in range(32):
    ctx = tuple((ctx_bits >> i) & 1 for i in range(NG))
    init = ctx + (0,) * (len(VARS) - NG)
    seen = {('f20', init)}
    pred = {('f20', init): None}
    q = deque([('f20', init)])
    while q:
        name, st = q.popleft()
        for nxt, st2, txt in nexts(name, st):
            k2 = (nxt, st2)
            if k2 not in seen:
                seen.add(k2)
                pred[k2] = ((name, st), txt)
                q.append(k2)
    rb = {n for n, _ in seen if n in f_blocks}
    rs = {blocks[n]['scene'] for n in rb if blocks[n]['scene']}
    result[ctx_bits] = {'blocks': sorted(rb), 'scenes': sorted(rs), 'states': len(seen)}
    # 见证: 每个块第一次到达的路径
    for k in seen:
        n, _ = k
        if n not in f_blocks: continue
        wkey = (ctx_bits, n)
        if wkey in witness: continue
        # 回溯选择列表
        ch = []
        cur = k
        while pred[cur] is not None:
            (pn, pst), txt = pred[cur]
            if txt: ch.append({'at': pn, 'pick': txt})
            cur = (pn, pst)
        ch.reverse()
        witness[wkey] = ch
    print(f'ctx {ctx_bits:02d} {ctx}: 状态 {len(seen)}, 块 {len(rb)}, 场景 {len(rs)}, {time.time()-t_all:.0f}s', flush=True)

union_blocks = set()
union_scenes = set()
for r in result.values():
    union_blocks |= set(r['blocks']); union_scenes |= set(r['scenes'])
print(f'\n总可达块: {len(union_blocks)}/{len(f_blocks)}, 总可达场景: {len(union_scenes)}/{len(all_scenes)}')
print(f'不可达块: {sorted(f_blocks - union_blocks, key=lambda x: blocks[x]["line"])}')
print(f'不可达场景: {sorted(all_scenes - union_scenes)}')

json.dump({'contexts': {str(k): v for k, v in result.items()},
           'union_blocks': sorted(union_blocks), 'union_scenes': sorted(union_scenes),
           'gate_global_order': GATE_GLOBALS},
          open(r'C:\Users\ccxxx\Desktop\tsuki_parse\reachability.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump({f'{c}|{b}': w for (c, b), w in witness.items()},
          open(r'C:\Users\ccxxx\Desktop\tsuki_parse\witnesses.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('已保存 reachability.json / witnesses.json')
