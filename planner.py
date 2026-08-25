# -*- coding: utf-8 -*-
"""规划器: 最少周目全覆盖流程
1. 从 witnesses 构建候选周目 = (上下文, 结局块) 的选择列表
2. 模拟器精确回放, 得到每周目覆盖的场景
3. 贪心集合覆盖 (尊重全局旗标单调性: ctx 的 1 位必须已被前面的周目达成;
   ctx 的 0 位若与当前 G 冲突则该见证路径可能失效 -> 用模拟验证)
4. 未覆盖场景 -> 支线段 (从已选周目的分歧选项点存档绕路)
"""
import json, re, sys, io
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

ENDING_BLOCKS = {  # 块 -> (结局名, 该块设置的全局旗标)
    'f52a': ('ark_true', ['%cleared', '%clear_ark', '%ark_normalcleared']),
    'f53a': ('ark_good', ['%cleared', '%clear_ark']),
    'f310': ('ciel_true', ['%cleared', '%clear_ciel']),
    'f308': ('ciel_good', ['%cleared', '%clear_ciel']),
    'f385': ('akiha_true', ['%cleared']),
    'f384': ('akiha_good', ['%cleared']),
    'f412': ('hisui_true', ['%cleared', '%clear_hisui']),
    'f413': ('hisui_good', ['%cleared', '%clear_hisui']),
    'f429': ('kohaku_true', ['%cleared']),
}

def simulate(ctx_bits, choices):
    """回放: ctx_bits=int, choices={block: pick_text}
    返回 (blocks_seq, scenes, ending_or_None, selects_seen)"""
    st = tuple((ctx_bits >> i) & 1 for i in range(NG)) + (0,) * (len(VARS) - NG)
    name = 'f20'
    bseq, scenes, sels = [], [], []
    ending = None
    for _ in range(2000):
        if name in ('endofplay', 'END', 'title', 'title2', 'title_tochu', 'gamestart_menu', 'ending'):
            break
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
        if name in ENDING_BLOCKS:
            ending = ENDING_BLOCKS[name][0]
        br = b['branch']
        nxt = None
        for e in br:
            if e['kind'] == 'select':
                pick = choices.get(name)
                opts = e['options']
                chosen = None
                if pick is not None:
                    for o in opts:
                        if o['text'].strip() == pick: chosen = o; break
                if chosen is None: chosen = opts[0]
                sels.append({'at': name, 'pick': chosen['text'].strip(),
                             'options': [o['text'].strip() for o in opts]})
                nxt = chosen['target']; break
            if e['kind'] == 'if' and e['act'] == 'select':
                if ev_c(e['cond'], st):
                    pick = choices.get(name)
                    opts = e.get('options', [])
                    chosen = None
                    if pick is not None:
                        for o in opts:
                            if o['text'].strip() == pick: chosen = o; break
                    if chosen is None: chosen = opts[0]
                    sels.append({'at': name, 'pick': chosen['text'].strip(),
                                 'options': [o['text'].strip() for o in opts], 'cond': e['cond']['raw']})
                    nxt = chosen['target']; break
                continue
            if e['kind'] == 'if' and e['act'] == 'goto':
                if ev_c(e['cond'], st): nxt = e['target']; break
                continue
            if e['kind'] == 'goto': nxt = e['target']; break
            if e['kind'] == 'end': nxt = 'END'; break
        if nxt is None:
            nxt = b['fallthrough'] or 'END'
        name = nxt
    return bseq, scenes, ending, sels

if __name__ == '__main__':
    # 测试: ctx0 空选择 -> 默认全选第一项, 应该走到某个结局
    for ctx in (0, 1, 3, 9, 15):
        bseq, scenes, ending, sels = simulate(ctx, {})
        print(f'ctx={ctx:02d}: {len(bseq)} 块, {len(scenes)} 场景, 结局={ending}, 选项数={len(sels)}')
