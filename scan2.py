# -*- coding: utf-8 -*-
"""第二遍: 在 raw parse 基础上构建简化流程图
- 剥离 sceneskip 样板, 得到每块的: 前置条件/场景/效果/分支
- 覆盖整个文件 (f块也可能出现在 s 区, 如 f2xx)
- 解析 select 内部条件选择 (if cond select ...)
- 校验: 每个 f 块是否恰好一个场景、分支目标是否都存在
"""
import json, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SRC = r'C:\Users\ccxxx\Desktop\0.txt'
lines = open(SRC, encoding='utf-8').read().split('\n')
N = len(lines)

label_at = {}
for i, ln in enumerate(lines):
    m = re.match(r'^\*([A-Za-z0-9_]+)', ln)
    if m: label_at[i] = m.group(1)
labels = {v: k for k, v in label_at.items()}

def split_colons(s):
    out, cur, q = [], [], False
    for ch in s:
        if ch == '"': q = not q; cur.append(ch)
        elif ch == ':' and not q: out.append(''.join(cur)); cur = []
        else: cur.append(ch)
    out.append(''.join(cur))
    return [x.strip() for x in out if x.strip()]

def parse_cond(s):
    s = s.strip()
    logic = '&&' if '&&' in s else ('||' if '||' in s else None)
    parts = s.split('&&') if '&&' in s else (s.split('||') if '||' in s else [s])
    terms = []
    for p in parts:
        p = p.strip()
        for op in ('>=', '<=', '!=', '==', '>', '<'):
            if op in p:
                a, b = p.split(op, 1)
                terms.append({'var': a.strip(), 'op': op, 'val': b.strip()})
                break
        else:
            terms.append({'var': p, 'op': 'truthy', 'val': ''})
    return {'raw': s, 'logic': logic, 'terms': terms}

SEL_RE = re.compile(r'"([^"]*)"\s*,\s*\*([A-Za-z0-9_]+)')

def parse_select_text(txt):
    return [{'text': m.group(1), 'target': m.group(2)} for m in SEL_RE.finditer(txt)]

# ---- 收集 select 行的续行 (通用, 供 f 块和 s 块用) ----
def gather_select(i):
    """i 是含 select 关键字的行(0-based). 返回 (options, end_i)"""
    txt = lines[i]
    j = i
    while txt.count('"') % 2 == 1 or txt.rstrip().endswith(','):
        j += 1
        if j >= N: break
        if lines[j].startswith('\t') or lines[j].strip().startswith('"'):
            txt += ' ' + lines[j].strip()
        else:
            j -= 1; break
    return parse_select_text(txt), j

# ---- 扫描 s 块: 找 flag 写入 / select / 嵌套块 ----
scene_writes = {}   # s名 -> [(line, op, var, val)]
scene_selects = {}  # s名 -> [...]
nested_blocks = []  # 在 s 区出现的 f 块
s_names = sorted([n for n in labels if re.match(r'^s[0-9]', n)], key=lambda x: labels[x])
for idx, name in enumerate(s_names):
    start = labels[name]
    end = labels[s_names[idx+1]] if idx+1 < len(s_names) else N
    # 注意: s 区里可能夹着 f 块 (f2xx) —— 实际边界应为"下一个任意标签"
    nxt = min([k for k in label_at if k > start], default=N)
    end = nxt
    ws, ss = [], []
    i = start + 1
    while i < end:
        raw = lines[i]; st = raw.strip()
        if not st or st.startswith(';'): i += 1; continue
        for cmd in split_colons(st):
            m = re.match(r'^(inc|dec|add|sub|mov)\s+([%$][\w]+)\s*,?\s*(.*)$', cmd)
            if m and re.match(r'^%(flg|ark_|ciel_|akiha_|hisui_|kohaku_|clear|sceneskip)', m.group(2)):
                ws.append((i+1, m.group(1), m.group(2), m.group(3)))
            if re.match(r'^(select|selgosub)\b', cmd):
                opts, j2 = gather_select(i)
                ss.append({'line': i+1, 'options': opts})
                i = j2
                break
        i += 1
    if ws: scene_writes[name] = ws
    if ss: scene_selects[name] = ss

# f 块出现在 s 区的检测
f_all = sorted([n for n in labels if re.match(r'^f[0-9]', n)], key=lambda x: labels[x])
f_zone = [(n, labels[n]+1) for n in f_all]
report = []
report.append(f'f 块总数: {len(f_all)}, 其中行号>9905 (散布在后部文件区): {sum(1 for _,l in f_zone if l>9905)}')
report.append(f's 块总数: {len(s_names)}')
report.append(f's 块内含 select 的: {len(scene_selects)} -> {sorted(scene_selects)[:20]}')
report.append(f's 块内有 flag 写入的: {len(scene_writes)}')
for k in sorted(scene_writes, key=lambda x: int(x[1:]) if x[1:].isdigit() else 0):
    report.append(f'  {k}: ' + '; '.join(f'L{l} {op} {v} {val}' for l, op, v, val in scene_writes[k]))

open(r'C:\Users\ccxxx\Desktop\tsuki_parse\scan2_report.txt', 'w', encoding='utf-8').write('\n'.join(report))
print('\n'.join(report[:60]))
print('...' if len(report) > 60 else '')
