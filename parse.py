# -*- coding: utf-8 -*-
"""月姬 NScripter 0.txt 流程图解析器
产出:
  flow_graph.json   - f-block 级别的机器可读分支图
  parse_report.txt  - 解析覆盖情况与异常
"""
import json, re, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SRC = r'C:\Users\ccxxx\Desktop\0.txt'

with open(SRC, encoding='utf-8') as f:
    lines = f.read().split('\n')
N = len(lines)

# ---------- 基础索引 ----------
label_at = {}          # 0-based line idx -> label name
for i, ln in enumerate(lines):
    m = re.match(r'^\*([A-Za-z0-9_]+)', ln)
    if m:
        label_at[i] = m.group(1)
labels = {v: k for k, v in label_at.items()}

def split_colons(s):
    """按半角冒号切分多指令行, 忽略引号内的冒号"""
    out, cur, q = [], [], False
    for ch in s:
        if ch == '"':
            q = not q; cur.append(ch)
        elif ch == ':' and not q:
            out.append(''.join(cur)); cur = []
        else:
            cur.append(ch)
    out.append(''.join(cur))
    return [x.strip() for x in out if x.strip()]

COND_OPS = ['>=', '<=', '!=', '==', '>', '<']

def parse_cond(s):
    """解析条件表达式 -> {'raw':..., 'terms':[{var,op,val}], 'logic':'&&'/'||'/None}"""
    s = s.strip()
    logic = None
    if '&&' in s: logic, parts = '&&', s.split('&&')
    elif '||' in s: logic, parts = '||', s.split('||')
    else: parts = [s]
    terms = []
    for p in parts:
        p = p.strip()
        for op in COND_OPS:
            if op in p:
                a, b = p.split(op, 1)
                terms.append({'var': a.strip(), 'op': op, 'val': b.strip()})
                break
        else:
            terms.append({'var': p, 'op': 'truthy', 'val': ''})
    return {'raw': s, 'logic': logic, 'terms': terms}

def parse_select(ln, i):
    """解析 select/selgosub, 处理制表符续行; 返回 (options, consumed_lines)"""
    txt = ln
    consumed = 0
    while txt.count('"') % 2 == 1 or txt.rstrip().endswith(','):
        consumed += 1
        if i + consumed >= N: break
        nxt = lines[i + consumed]
        if nxt.startswith('\t') or nxt.strip().startswith('"'):
            txt += ' ' + nxt.strip()
        else:
            break
    opts = []
    # 成对提取 "文本", *标签
    for m in re.finditer(r'"([^"]*)"\s*,\s*\*([A-Za-z0-9_]+)', txt):
        opts.append({'text': m.group(1), 'target': m.group(2)})
    return opts, consumed

# ---------- 逐标签块解析 ----------
CONTROL = ('goto', 'gosub', 'return', 'skip', 'if', 'select', 'selgosub',
           'mov', 'inc', 'dec', 'add', 'sub', 'end')

def parse_block(start):
    """从标签行之后解析到块终止. 返回 (events, anomalies)"""
    events = []      # 有序事件: {'kind':...}
    anomalies = []
    i = start + 1
    while i < N:
        if i in label_at:
            break  # 落入下一标签
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith(';'):
            i += 1; continue
        consumed_extra = 0
        for cmd in split_colons(stripped):
            tok = cmd.split(None, 1)[0].lower() if cmd.split(None, 1) else ''
            if tok == 'if':
                rest = cmd[3:].strip()
                # 找条件与动作的分界: 动作以已知动词开头
                m = re.match(r'^(.*?)\s+(goto|gosub|skip|mov|inc|dec|add|sub|select|return|end)\b(.*)$', rest)
                if not m:
                    anomalies.append(f'line {i+1}: 无法解析 if: {cmd}')
                    continue
                cond, act, arg = parse_cond(m.group(1)), m.group(2), m.group(3).strip()
                ev = {'kind': 'if', 'cond': cond, 'act': act, 'line': i+1}
                if act == 'goto' or act == 'gosub':
                    ev['target'] = arg.lstrip('*')
                elif act == 'skip':
                    ev['skip'] = int(arg)
                    ev['target_line'] = i + int(arg) + 1  # 1-based 落点
                else:
                    ev['arg'] = arg
                events.append(ev)
            elif tok == 'goto':
                events.append({'kind': 'goto', 'target': cmd[5:].strip().lstrip('*'), 'line': i+1})
            elif tok == 'gosub':
                events.append({'kind': 'gosub', 'target': cmd[6:].strip().lstrip('*'), 'line': i+1})
            elif tok == 'return':
                events.append({'kind': 'return', 'line': i+1})
            elif tok == 'skip':
                n = int(cmd.split()[1])
                events.append({'kind': 'skip', 'skip': n, 'target_line': i + n + 1, 'line': i+1})
            elif tok in ('select', 'selgosub'):
                opts, ce = parse_select(cmd, i)
                consumed_extra = max(consumed_extra, ce)
                events.append({'kind': tok, 'options': opts, 'line': i+1})
            elif tok in ('mov', 'inc', 'dec', 'add', 'sub'):
                m = re.match(r'^(\w+)\s+([%$][\w]+)\s*,?\s*(.*)$', cmd)
                if m:
                    events.append({'kind': 'flag', 'op': m.group(1), 'var': m.group(2),
                                   'val': m.group(3), 'line': i+1})
                else:
                    anomalies.append(f'line {i+1}: 无法解析赋值: {cmd}')
            elif tok == 'end':
                events.append({'kind': 'end', 'line': i+1})
            # 其余都是演出/文本, 忽略
        i += 1 + consumed_extra
    return events, anomalies

# ---------- 只解析流程相关标签 ----------
report = []
flow = {}
all_anomalies = []
interesting = [n for n in labels if re.match(r'^f[0-9]', n) or n in
               ('start', 'title', 'title_tochu', 'title2', 'gamestart_menu',
                'ending', 'endofplay', 'eclipse')]
for name in sorted(interesting, key=lambda x: labels[x]):
    ev, an = parse_block(labels[name])
    flow[name] = {'line': labels[name] + 1, 'events': ev}
    all_anomalies += an

report.append(f'标签总数: {len(labels)}, f-block 数: {sum(1 for n in labels if re.match(chr(94)+"f[0-9]", n))}')
report.append(f'已解析流程块: {len(flow)}')
report.append(f'异常数: {len(all_anomalies)}')
for a in all_anomalies[:50]:
    report.append('  ' + a)

# 统计条件里出现的变量 & 赋值变量
cond_vars, set_vars = {}, {}
for name, blk in flow.items():
    for ev in blk['events']:
        if ev['kind'] == 'if':
            for t in ev['cond']['terms']:
                cond_vars[t['var']] = cond_vars.get(t['var'], 0) + 1
        if ev['kind'] == 'flag':
            set_vars[ev['var']] = set_vars.get(ev['var'], 0) + 1
report.append('条件变量: ' + json.dumps(cond_vars, ensure_ascii=False, sort_keys=True))
report.append('赋值变量: ' + json.dumps(set_vars, ensure_ascii=False, sort_keys=True))

with open(r'C:\Users\ccxxx\Desktop\tsuki_flow_raw.json', 'w', encoding='utf-8') as f:
    json.dump(flow, f, ensure_ascii=False, indent=1)
with open(r'C:\Users\ccxxx\Desktop\parse_report.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))
print('\n'.join(report))
