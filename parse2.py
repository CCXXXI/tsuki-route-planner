# -*- coding: utf-8 -*-
"""月姬 0.txt 路线分支图 — 最终解析器
修正: 内部标签 ^skip[0-9a-z]+$; 场景旗标 ^%1\d{3,}$; 无分支块=按文件顺序落到下一标签
输出:
  flow_graph.json  节点+边 (机器可读)
  校验打印
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
label_order = sorted(label_at)          # 0-based 行号升序
next_label = {}                          # 块名 -> 文件中下一非内部标签名
def is_internal(n): return re.match(r'^skip[0-9a-z]+$', n) is not None
pub_labels = [(i, n) for i, n in label_at.items() if not is_internal(n)]
pub_labels.sort()
for (i, n), (j, m) in zip(pub_labels, pub_labels[1:]):
    next_label[n] = m

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

def parse_block(start):
    events, anomalies = [], []
    i = start + 1
    while i < N:
        if i in label_at and not is_internal(label_at[i]):
            break
        raw = lines[i]; st = raw.strip()
        if not st or st.startswith(';'): i += 1; continue
        extra = 0
        for cmd in split_colons(st):
            tok_m = re.match(r'^([A-Za-z]+)', cmd)
            tok = tok_m.group(1).lower() if tok_m else ''
            if tok == 'if':
                rest = cmd[2:].strip()
                m = re.match(r'^(.*?)\s+(goto|gosub|skip|mov|inc|dec|add|sub|select|return|end)\b(.*)$', rest)
                if not m:
                    anomalies.append(f'L{i+1}: if 无法解析: {cmd}'); continue
                cond, act, arg = parse_cond(m.group(1)), m.group(2), m.group(3).strip()
                ev = {'kind': 'if', 'cond': cond, 'act': act, 'line': i+1}
                if act in ('goto', 'gosub'): ev['target'] = arg.lstrip('*')
                elif act == 'select':
                    ev['options'] = [{'text': mm.group(1), 'target': mm.group(2)} for mm in SEL_RE.finditer(arg)]
                elif act == 'skip': ev['skip'] = int(arg)
                else: ev['arg'] = arg
                events.append(ev)
            elif tok == 'goto':
                events.append({'kind': 'goto', 'target': cmd[4:].strip().lstrip('*'), 'line': i+1})
            elif tok == 'gosub':
                events.append({'kind': 'gosub', 'target': cmd[5:].strip().lstrip('*'), 'line': i+1})
            elif tok == 'return':
                events.append({'kind': 'return', 'line': i+1})
            elif tok == 'skip':
                events.append({'kind': 'skip', 'skip': int(cmd.split()[1]), 'line': i+1})
            elif tok in ('select', 'selgosub'):
                txt = cmd; j = i
                while txt.count('"') % 2 == 1 or txt.rstrip().endswith(','):
                    j += 1
                    if j >= N: break
                    if lines[j].startswith('\t') or lines[j].strip().startswith('"'):
                        txt += ' ' + lines[j].strip()
                    else: j -= 1; break
                extra = max(extra, j - i)
                events.append({'kind': tok, 'options': [
                    {'text': mm.group(1), 'target': mm.group(2)} for mm in SEL_RE.finditer(txt)], 'line': i+1})
            elif tok in ('mov', 'inc', 'dec', 'add', 'sub'):
                m = re.match(r'^(\w+)\s+([%$][\w]+)\s*,?\s*(.*)$', cmd)
                if m: events.append({'kind': 'flag', 'op': m.group(1), 'var': m.group(2), 'val': m.group(3), 'line': i+1})
            elif tok == 'end':
                events.append({'kind': 'end', 'line': i+1})
        i += 1 + extra
    return events, anomalies

SCENE_FLAG = re.compile(r'^%1\d{3,}$')

def is_sceneskip_guard(e):
    return e['kind'] == 'if' and e['act'] == 'skip' and \
        any(t['var'] == '%sceneskip' for t in e['cond']['terms'])

def build(name):
    ev, an = parse_block(labels[name])
    scene, pre, effects, branch = None, [], [], []
    guard = next((k for k, e in enumerate(ev) if is_sceneskip_guard(e)), None)
    if guard is not None:
        for e in ev[:guard]:
            if e['kind'] == 'gosub' and e['target'] == 'regard_update': continue
            pre.append(e)
        rest = ev[guard+1:]
        for e in rest:
            if e['kind'] == 'gosub' and re.match(r'^s\d', e.get('target', '')):
                scene = e['target']; break
        seen = False
        for e in rest:
            if not seen:
                if e['kind'] == 'gosub' and e.get('target') == scene: seen = True
                continue
            if e['kind'] == 'flag' and (SCENE_FLAG.match(e['var']) or e['var'] in ('%4020','%4021','%4022','%4023','%4024')): continue
            if e['kind'] in ('skip', 'return', 'selgosub'): continue
            if e['kind'] == 'flag' and not branch: effects.append(e)
            else: branch.append(e)
    else:
        for e in ev:
            if e['kind'] == 'gosub' and e['target'] == 'regard_update': continue
            if e['kind'] == 'flag' and not branch: effects.append(e)
            else: branch.append(e)
    return {'line': labels[name]+1, 'scene': scene, 'pre': pre,
            'effects': [{'op': e['op'], 'var': e['var'], 'val': e['val']} for e in effects],
            'branch': branch, 'fallthrough': next_label.get(name)}, an

f_names = sorted([n for n in labels if re.match(r'^f[0-9]', n)], key=lambda x: labels[x])
specials = ['start', 'title', 'title_tochu', 'title2', 'gamestart_menu',
            'endinglist', 'eclipse', 'ending', 'endofplay']
blocks, all_an = {}, []
for name in f_names + [s for s in specials if s in labels]:
    blk, an = build(name)
    blocks[name] = blk
    all_an += an

# ---------- 汇总成边 ----------
def cond_str(c): return c['raw']
edges = []
for name, b in blocks.items():
    # 前置条件: if-goto 链, 每条是 cond 边, 全部不成立则进入场景
    for e in b['pre']:
        if e['kind'] == 'if' and e['act'] == 'goto':
            edges.append({'src': name, 'dst': e['target'], 'type': 'cond', 'cond': cond_str(e['cond']), 'where': 'pre'})
        elif e['kind'] == 'if' and e['act'] == 'gosub':
            edges.append({'src': name, 'dst': e['target'], 'type': 'cond_call', 'cond': cond_str(e['cond']), 'where': 'pre'})
        elif e['kind'] == 'goto':
            edges.append({'src': name, 'dst': e['target'], 'type': 'goto', 'where': 'pre'})
    for e in b['branch']:
        if e['kind'] == 'select':
            for o in e['options']:
                edges.append({'src': name, 'dst': o['target'], 'type': 'choice', 'text': o['text']})
        elif e['kind'] == 'if' and e['act'] == 'select':
            for o in e.get('options', []):
                edges.append({'src': name, 'dst': o['target'], 'type': 'choice', 'text': o['text'], 'cond': cond_str(e['cond'])})
        elif e['kind'] == 'if' and e['act'] == 'goto':
            edges.append({'src': name, 'dst': e['target'], 'type': 'cond', 'cond': cond_str(e['cond'])})
        elif e['kind'] == 'goto':
            edges.append({'src': name, 'dst': e['target'], 'type': 'goto'})
        elif e['kind'] == 'end':
            edges.append({'src': name, 'dst': 'END', 'type': 'end'})
        else:
            edges.append({'src': name, 'dst': '?', 'type': 'UNHANDLED:' + json.dumps(e, ensure_ascii=False)})
    has_terminal = any(e['kind'] in ('select', 'goto', 'end') or (e['kind'] == 'if' and e['act'] in ('goto', 'select')) for e in b['branch'])
    has_uncond = any(e['kind'] in ('select', 'goto', 'end') for e in b['branch'])
    if not has_uncond and b['fallthrough']:
        edges.append({'src': name, 'dst': b['fallthrough'], 'type': 'fallthrough'})

out = {'blocks': blocks, 'edges': edges}
json.dump(out, open(r'C:\Users\ccxxx\Desktop\tsuki_parse\flow_graph.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ---------- 校验 ----------
rep = []
rep.append(f'块: {len(blocks)}, 边: {len(edges)}, 解析异常: {len(all_an)}')
bad = [e for e in edges if e['type'].startswith('UNHANDLED')]
rep.append(f'未处理分支类型: {len(bad)}')
for e in bad[:20]: rep.append('  ' + e['type'][:200])
missing = sorted({e['dst'] for e in edges if e['dst'] not in blocks and e['dst'] not in labels and e['dst'] != 'END'})
rep.append(f'缺失目标: {missing if missing else "无"}')
# 既无出边又非结束的块
srcs = {e['src'] for e in edges}
sinks = [n for n in blocks if n not in srcs]
rep.append(f'无出边块: {sinks}')
# 入度为 0 的 f 块 (除 f20 入口)
dsts = {e['dst'] for e in edges}
orphans = [n for n in f_names if n not in dsts]
rep.append(f'入度为0的f块 ({len(orphans)}): {orphans}')
print('\n'.join(rep))
open(r'C:\Users\ccxxx\Desktop\tsuki_parse\verify_report.txt', 'w', encoding='utf-8').write('\n'.join(rep))
