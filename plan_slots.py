# -*- coding: utf-8 -*-
"""栏位生命周期分析 (不改动计划): 每个存档的 [创建, 最后使用] 区间 + 最大并发"""
import json, sys, io
D = r'C:\Users\ccxxx\Desktop\tsuki_parse'
st2 = json.load(open(D + r'\plan_stage2_v2.json', encoding='utf-8'))
st4 = json.load(open(D + r'\plan_stage4.json', encoding='utf-8'))
runs = st4['runs']

# 事件流: (seq, 'save'|'load', (run,block))
events = []
trip_loads = {}
for t in st2['trips']:
    trip_loads.setdefault((t['pt'], t['at']), 0)
    trip_loads[(t['pt'], t['at'])] += 1

for i, r in enumerate(runs):
    if r['reuse']:
        k, j, B = r['reuse']
        events.append((f'run{i}-start', 'load', (j, B)))
    for at, pick in r['sels']:
        events.append((f'run{i}', 'point', (i, at)))

# 每个存档: 创建事件位置 + 最后 load 位置
# 创建: 需要 save 的 (i,at) = 所有支线锚点 + 所有复用锚点
need_save = set(trip_loads) | {(j, B) for r in runs if r['reuse'] for _, j, B in [r['reuse']]}
create_pos = {}
use_pos = {}
seq = 0
for i, r in enumerate(runs):
    if r['reuse']:
        k, j, B = r['reuse']
        use_pos[(j, B)] = seq
        seq += 1
    for at, pick in r['sels']:
        if (i, at) in need_save and (i, at) not in create_pos:
            create_pos[(i, at)] = seq
        # 支线 load 紧随其后
        if (i, at) in trip_loads:
            use_pos[(i, at)] = seq
        seq += 1

intervals = []
for key in need_save:
    c = create_pos.get(key)
    u = use_pos.get(key, c)
    if c is not None:
        intervals.append((c, u, key))
# 最大并发 (区间着色数; 闭区间, load 与后续 save 可同槽: 用 [c, u] 半开处理 u 点复用)
points = sorted(set([c for c, _, _ in intervals] + [u for _, u, _ in intervals]))
maxlive, argp = 0, None
for p in points:
    live = sum(1 for c, u, _ in intervals if c <= p <= u)
    if live > maxlive: maxlive, argp = live, p
print(f'存档总数: {len(intervals)}, 回收后最小栏位需求: {maxlive}')
# 长生区间 top
intervals.sort(key=lambda x: x[1]-x[0], reverse=True)
print('长生存档 top15:')
for c, u, key in intervals[:15]:
    print(f'  存于{key[0] and f"run{key[0]}"} {key[1]} 存活 {u-c} 步')
