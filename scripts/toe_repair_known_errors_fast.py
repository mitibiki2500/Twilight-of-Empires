from __future__ import annotations

import re
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERROR_LOG = ROOT / "gpt送信用" / "logs" / "error.log"
VANILLA_COMMON = ROOT / "gpt送信用" / "common"
LIVE_COMMON = ROOT / "common"
MARKER = "# ToE 1.13 compatibility: disabled dangling reference: "
SEPOY_BARS = {"sepoy_mutiny_progress_bar_bengal","sepoy_mutiny_progress_bar_bombay","sepoy_mutiny_progress_bar_madras"}
MISSING_JES = {"je_cement_the_rightful_dynasty"}


def clean_line(line:str)->str:
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


def balanced(text:str):
    d=0
    for n,line in enumerate(text.splitlines(),1):
        c=clean_line(line); d+=c.count('{')-c.count('}')
        if d<0: return False,f'extra closing brace line {n}'
    return (d==0,'' if d==0 else f'unclosed depth {d}')


def parse_errors(text:str):
    out=[]; cur=None
    for line in text.splitlines():
        if 'Script system error!' in line:
            cur={'error':'','location':''}; continue
        if cur is None: continue
        m=re.match(r'^\s*Error:\s*(.*)',line)
        if m: cur['error']=m.group(1); continue
        m=re.match(r'^\s*Script location:\s*(.*?):\d+\s*$',line)
        if m:
            cur['location']=m.group(1).replace('\\','/')
            if cur['error']: out.append(cur)
            cur=None
    return out


def exact_pat(t:str):
    return rf'(?<![A-Za-z0-9_.-]){re.escape(t)}(?![A-Za-z0-9_.-])'


def find_block(lines,hit,assignment):
    startpat=re.compile(rf'^\s*{re.escape(assignment)}\s*=\s*\{{')
    for s in range(hit,max(-1,hit-160),-1):
        if lines[s].lstrip().startswith('#'): continue
        if not startpat.search(clean_line(lines[s])): continue
        d=0; opened=False
        for e in range(s,len(lines)):
            c=clean_line(lines[e]); opened |= '{' in c; d+=c.count('{')-c.count('}')
            if opened and d==0:
                return (s,e) if s<=hit<=e else None
    return None


def comment_block(lines,s,e,reason):
    indent=re.match(r'^\s*',lines[s]).group(0)
    lines.insert(s,f'{indent}{MARKER}{reason}'); e+=1
    for i in range(s+1,e+1):
        if lines[i].strip() and not lines[i].lstrip().startswith('#'):
            lines[i]=indent+'# '+lines[i][len(indent):]


def disable_direct(lines,assignment,targets,kind):
    n=0; i=0
    p=re.compile(rf'^(\s*){re.escape(assignment)}\s*=\s*([A-Za-z0-9_.-]+)\s*(?:#.*)?$')
    while i<len(lines):
        if lines[i].lstrip().startswith('#'): i+=1; continue
        m=p.match(lines[i])
        if m and m.group(2) in targets:
            ind,t=m.group(1),m.group(2); lines.insert(i,f'{ind}{MARKER}{kind} {t}'); i+=1
            lines[i]=ind+'# '+lines[i][len(ind):]; n+=1
        i+=1
    return n


def disable_inline_events(lines,targets):
    n=0
    p=re.compile(r'trigger_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.-]+)(?:\s+[^{}]*)?\}')
    for i,line in enumerate(lines):
        if line.lstrip().startswith('#'): continue
        c=clean_line(line); matches=list(p.finditer(c))
        if not matches: continue
        repl=line; hits=[]
        for m in reversed(matches):
            if m.group(1) not in targets: continue
            repl=repl[:m.start()]+repl[m.end():]; hits.append(m.group(1))
        if hits:
            if repl.strip(): repl=repl.rstrip()+f'  {MARKER}'+','.join(reversed(hits))
            else: repl=re.match(r'^\s*',line).group(0)+MARKER+','.join(reversed(hits))
            lines[i]=repl; n+=len(hits)
    return n


def disable_blocks(lines,assignment,targets,kind):
    n=0; i=0
    union=re.compile('|'.join(f'(?:{exact_pat(t)})' for t in sorted(targets,key=len,reverse=True))) if targets else None
    while i<len(lines):
        if lines[i].lstrip().startswith('#') or not union: i+=1; continue
        c=clean_line(lines[i]); m=union.search(c)
        if not m: i+=1; continue
        target=next((t for t in targets if re.search(exact_pat(t),c)),None)
        if not target: i+=1; continue
        b=find_block(lines,i,assignment)
        if not b: i+=1; continue
        s,e=b; comment_block(lines,s,e,f'{kind} {target}'); n+=1; i=e+2
    return n


def has_assignment_ref(lines,assignment,target):
    tp=re.compile(exact_pat(target))
    for i,line in enumerate(lines):
        if line.lstrip().startswith('#'): continue
        c=clean_line(line)
        if not tp.search(c): continue
        if re.search(rf'\b{re.escape(assignment)}\s*=',c): return True
        if find_block(lines,i,assignment): return True
    return False


def main():
    log=ERROR_LOG.read_text(encoding='utf-8-sig',errors='replace')
    entries=parse_errors(log)
    jobs=defaultdict(lambda:{'events':set(),'progress':set(),'jes':set()})
    for e in entries:
        loc=e['location']
        if not loc.startswith('common/'): continue
        err=e['error']
        if err.startswith('trigger_event effect'):
            m=re.search(r'EventID:\s*([^\s\]]+)',err)
            if m: jobs[loc]['events'].add(m.group(1))
        elif err.startswith('add_progress effect'):
            jobs[loc]['progress'].update(SEPOY_BARS)
        elif err.startswith('add_journal_entry effect'):
            jobs[loc]['jes'].update(MISSING_JES)

    print('LOGGED_ERRORS',len(entries),'CALLER_FILES',len(jobs))
    copied=[]; changed=[]; ef=pf=jf=0
    for loc,targets in sorted(jobs.items()):
        rel=loc[len('common/'):]; dst=LIVE_COMMON/rel
        if not dst.exists():
            src=VANILLA_COMMON/rel
            if not src.exists(): raise RuntimeError(f'No exact vanilla 1.13.11 mirror for {loc}')
            dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst); copied.append(loc)
        original=dst.read_text(encoding='utf-8-sig',errors='strict'); bom=dst.read_bytes().startswith(b'\xef\xbb\xbf'); lines=original.splitlines()
        a=disable_direct(lines,'trigger_event',targets['events'],'missing event')
        a+=disable_inline_events(lines,targets['events'])
        a+=disable_blocks(lines,'trigger_event',targets['events'],'missing event')
        b=disable_blocks(lines,'add_progress',targets['progress'],'missing progress bar')
        c=disable_direct(lines,'add_journal_entry',targets['jes'],'missing journal entry')
        c+=disable_blocks(lines,'add_journal_entry',targets['jes'],'missing journal entry')
        if not (a or b or c): raise RuntimeError(f'Logged errors found but no matching live call sanitized in {loc}: {targets}')
        new='\n'.join(lines)+('\n' if original.endswith('\n') else '')
        ok,msg=balanced(new)
        if not ok: raise RuntimeError(f'Brace failure {loc}: {msg}')
        dst.write_text(new,encoding='utf-8-sig' if bom else 'utf-8')
        changed.append(loc); ef+=a; pf+=b; jf+=c

    # Validate all changed files and all exact logged targets in their own caller files.
    leftovers=[]
    for loc,targets in sorted(jobs.items()):
        dst=ROOT/loc; lines=dst.read_text(encoding='utf-8-sig',errors='strict').splitlines()
        ok,msg=balanced('\n'.join(lines))
        if not ok: raise RuntimeError(f'Postcheck brace failure {loc}: {msg}')
        for t in targets['events']:
            if has_assignment_ref(lines,'trigger_event',t): leftovers.append((loc,'trigger_event',t))
        for t in targets['progress']:
            if has_assignment_ref(lines,'add_progress',t): leftovers.append((loc,'add_progress',t))
        for t in targets['jes']:
            if has_assignment_ref(lines,'add_journal_entry',t): leftovers.append((loc,'add_journal_entry',t))
    if leftovers: raise RuntimeError(f'Known refs remain: {leftovers[:50]}')

    # Full common brace/decode check after copied overrides are added.
    for p in LIVE_COMMON.rglob('*.txt'):
        text=p.read_text(encoding='utf-8-sig',errors='strict'); ok,msg=balanced(text)
        if not ok: raise RuntimeError(f'Whole-common brace failure {p.relative_to(ROOT)}: {msg}')

    print('COPIED_VANILLA_CALLERS',len(copied)); [print('COPIED',x) for x in copied]
    print('CHANGED_FILES',len(changed)); [print('CHANGED',x) for x in changed]
    print('DISABLED_EVENTS',ef,'DISABLED_PROGRESS',pf,'DISABLED_JE',jf)
    if pf != 12: raise RuntimeError(f'Expected 12 progress errors, repaired {pf}')
    if jf != 3: raise RuntimeError(f'Expected 3 JE errors, repaired {jf}')
    if ef < 260: raise RuntimeError(f'Expected about 268 event errors, repaired only {ef}')
    print('KNOWN_LOG_ERRORS_REPAIRED_AND_VERIFIED')

if __name__=='__main__': main()
