# -*- coding: utf-8 -*-
"""阶段3: 补课速通周目
对剩余场景, 取其在各 ctx 下的见证作为候选 run (完整模拟到结局),
贪心选覆盖最多剩余场景的 run. 成本 = 选项数 + 新场景数 (已读场景一键跳过).
"""
import json, re, sys, io
exec(open(r'C:\Users\ccxxx\Desktop\tsuki_parse\plan_cover.py', encoding='utf-8').read().split("# ---------- 1.")[0])

D = r'C:\Users\ccxxx\Desktop\tsuki_parse'
reach = json.load(open(D + r'\reachability.json', encoding='utf-8'))
W = json.load(open(D + r'\witnesses.json', encoding='utf-8'))
st1 = json.load(open(D + r'\plan_stage1.json', encoding='utf-8'))
st2 = json.load(open(D + r'\plan_stage2.json', encoding='utf-8'))

covered = set(st2['covered'])
universe = set(reach['union_scenes'])
rem = universe - covered
print(f'剩余待覆盖: {len(rem)}')

# 每个剩余场景找见证 (优先 ctx31=全开, 否则任意有的)
scene2f = {b['scene']: n for n, b in blocks.items() if b['scene']}
runs = {}  # key=(ctx, frozenset(choices.items())) -> run dict
for s in sorted(rem):
    f = scene2f[s]
    wl = W.get(f'31|{f}')
    ctx = 31
    if wl is None:
        for c in range(32):
            wl = W.get(f'{c}|{f}')
            if wl is not None: ctx = c; break
    if wl is None:
        print(f'!! {s} 无任何见证'); continue
    ch = {c['at']: c['pick'] for c in wl}
    key = (ctx, tuple(sorted(ch.items())))
    if key in runs: continue
    bseq, scenes, ending, sels, fin = simulate(ctx, ch)
    runs[key] = {'ctx': ctx, 'choices': ch, 'scenes': scenes, 'ending': ending,
                 'n_choices': len(sels), 'target': s}
print(f'候选补课 run: {len(runs)}')

chosen = []
rem2 = set(rem)
while True:
    best, bk = 0, None
    for k, r in runs.items():
        n = len(set(r['scenes']) & rem2)
        if n > best: best, bk = n, k
    if bk is None: break
    r = runs[bk]
    chosen.append(r)
    rem2 -= set(r['scenes'])
    print(f"补课{len(chosen)}: ctx={r['ctx']} target={r['target']} 结局={r['ending']} "
          f"新增 {best}, 路径选项数 {r['n_choices']}, 累计剩余 {len(rem2)}")

covered_final = covered | set().union(*[set(r['scenes']) for r in chosen]) if chosen else covered
print(f'\n最终覆盖: {len(covered_final)}/{len(universe)}, 未覆盖: {sorted(universe - covered_final)}')
json.dump({'runs': chosen, 'remaining': sorted(universe - covered_final)},
          open(D + r'\plan_stage3.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
