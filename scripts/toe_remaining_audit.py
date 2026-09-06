from __future__ import annotations
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def clean(line):
    out=[]; ins=False; esc=False
    for ch in line:
        if ins:
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch=='"': ins=False
            out.append(' '); continue
        if ch=='"': ins=True; out.append(' '); continue
        if ch=='#': break
        out.append(ch)
    return ''.join(out)


def blocks(text):
    lines=text.splitlines(); depth=0; start=None; name=None
    for i,line in enumerate(lines):
        c=clean(line)
        if depth==0:
            m=re.match(r'^\s*([^\s={}]+)\s*=\s*\{',c)
            if m: start=i; name=m.group(1)
        depth+=c.count('{')-c.count('}')
        if start is not None and depth==0:
            yield name,lines[start:i+1]; start=None; name=None

print('=== PRESTIGE GOODS COUNTS ===')
by_good=defaultdict(list)
for p in sorted((ROOT/'common/prestige_goods').glob('*.txt')):
    text=p.read_text(encoding='utf-8-sig')
    for name,bl in blocks(text):
        g=None; possible_disabled=False
        for line in bl:
            c=clean(line)
            m=re.search(r'\bbase_good\s*=\s*([A-Za-z0-9_]+)',c)
            if m: g=m.group(1)
            if 'always = no' in c: possible_disabled=True
        if g: by_good[g].append((name,p.name,possible_disabled))
for g,defs in sorted(by_good.items(),key=lambda kv:(-len(kv[1]),kv[0])):
    print(g,len(defs),defs)

print('\n=== ERROR.1 ASSERTIONS / UNKNOWN / INVALID DB ===')
p=ROOT/'gpt送信用/logs/error.1.log'
text=p.read_text(encoding='utf-8-sig',errors='replace') if p.exists() else ''
for line in text.splitlines():
    if ('Assertion failed:' in line or 'Unknown effect ' in line or 'Unknown trigger ' in line or
        'Invalid database object' in line or 'Invalid country formation' in line or
        'Unexpected token' in line or 'Error: ' in line and 'Script system error' not in line):
        print(line)

print('\n=== ERROR.1 CATEGORY COUNTS ===')
patterns={
'assertion':r'Assertion failed:',
'unknown_effect':r'Unknown effect ',
'unknown_trigger':r'Unknown trigger ',
'invalid_db':r'Invalid database object',
'invalid_formation':r'Invalid country formation',
'event_not_found':r'Event not found',
'missing_leader':r'Could not get leader',
'unset_scope':r'unset scope',
}
for k,pat in patterns.items(): print(k,len(re.findall(pat,text,re.I)))

print('\n=== INVALID DB OBJECT + CALLER ===')
lines=text.splitlines()
for i,line in enumerate(lines):
    if 'Invalid database object' in line or 'Invalid country formation' in line:
        print(line)
        for j in range(i+1,min(i+4,len(lines))):
            if 'Script location:' in lines[j]: print(' ',lines[j]); break

print('\n=== UNKNOWN EFFECT CALLERS AND CURRENT FILE STATUS ===')
for line in lines:
    m=re.search(r'Unknown effect ([^ ]+) at ([^:]+):(\d+)',line)
    if not m: continue
    eff,path,ln=m.groups(); live=ROOT/path; van=ROOT/'gpt送信用'/path
    print(eff,path,ln,'live=',live.exists(),'vanilla_mirror=',van.exists())

print('\n=== CURRENT KNOWN-ERROR MARKERS ===')
count=0; files=[]
for p in (ROOT/'common').rglob('*.txt'):
    t=p.read_text(encoding='utf-8-sig',errors='strict')
    n=t.count('ToE 1.13 compatibility: disabled dangling reference:')
    if n: count+=n; files.append((p.relative_to(ROOT).as_posix(),n))
print('markers',count,'files',len(files)); [print(x) for x in files]
