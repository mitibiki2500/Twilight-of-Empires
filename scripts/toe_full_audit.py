from __future__ import annotations
import json, re, hashlib
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'common'
VANILLA = ROOT / 'gpt送信用' / 'common'
LOGROOT = ROOT / 'gpt送信用' / 'logs'
CRASHROOT = ROOT / 'gpt送信用' / 'crashes'
OUT = ROOT / '_audit'
OUT.mkdir(exist_ok=True)

TEXT_EXT = {'.txt','.yml','.yaml','.json','.md','.csv','.gui','.asset','.gfx','.settings'}

def sha(p: Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def read_text(p: Path):
    b=p.read_bytes()
    for enc in ('utf-8-sig','utf-8'):
        try: return b.decode(enc), enc
        except UnicodeDecodeError: pass
    return None, None

def strip_comments_and_strings(s: str):
    out=[]; in_str=False; esc=False
    for line in s.splitlines(True):
        i=0
        while i<len(line):
            ch=line[i]
            if in_str:
                if esc: esc=False
                elif ch=='\\': esc=True
                elif ch=='"': in_str=False
                out.append(' ')
                i+=1; continue
            if ch=='"': in_str=True; out.append(' '); i+=1; continue
            if ch=='#':
                out.append(' '*(len(line)-i)); break
            out.append(ch); i+=1
    return ''.join(out)

def brace_check(text: str):
    s=strip_comments_and_strings(text)
    depth=0
    for n,ch in enumerate(s):
        if ch=='{': depth+=1
        elif ch=='}':
            depth-=1
            if depth<0: return False, f'extra closing brace at char {n}'
    return (depth==0, None if depth==0 else f'unclosed brace depth {depth}')

def comment_only(text: str):
    meaningful=[]
    for line in text.splitlines():
        x=line.strip()
        if x and not x.startswith('#'): meaningful.append(x)
    return not meaningful

def top_defs(text: str):
    clean=strip_comments_and_strings(text)
    defs=[]; depth=0
    for line_no,line in enumerate(clean.splitlines(),1):
        if depth==0:
            m=re.match(r'^\s*([^\s={}]+)\s*=\s*\{', line)
            if m: defs.append((m.group(1),line_no))
        depth += line.count('{')-line.count('}')
    return defs

def iter_files(base: Path):
    if not base.exists(): return []
    return [p for p in base.rglob('*') if p.is_file()]

report={}
# metadata
meta=json.loads((ROOT/'.metadata/metadata.json').read_text(encoding='utf-8-sig'))
replace_paths=meta.get('game_custom_data',{}).get('replace_paths',[])
report['replace_paths']=replace_paths

# Whole repo text integrity
integrity=[]; comment_files=[]; tiny_files=[]; decode_fail=[]
for base_name in ('common','events','map_data','gfx'):
    base=ROOT/base_name
    for p in iter_files(base):
        rel=p.relative_to(ROOT).as_posix()
        if p.stat().st_size <= 4: tiny_files.append({'path':rel,'size':p.stat().st_size})
        if p.suffix.lower() not in TEXT_EXT: continue
        text,enc=read_text(p)
        if text is None:
            decode_fail.append(rel); continue
        if p.suffix.lower() in {'.txt','.gui','.asset','.gfx'}:
            ok,msg=brace_check(text)
            if not ok: integrity.append({'path':rel,'problem':msg})
        if comment_only(text): comment_files.append({'path':rel,'size':p.stat().st_size})
report['syntax_brace_errors']=integrity
report['decode_failures']=decode_fail
report['tiny_files']=tiny_files
report['comment_only_files']=comment_files

# Duplicate top-level database keys per first directory below common/events
by_domain=defaultdict(lambda: defaultdict(list))
for base_name in ('common','events'):
    base=ROOT/base_name
    for p in iter_files(base):
        if p.suffix.lower()!='.txt': continue
        text,_=read_text(p)
        if text is None: continue
        rel=p.relative_to(ROOT).as_posix()
        domain='/'.join(rel.split('/')[:2]) if base_name=='common' else 'events'
        for key,line in top_defs(text): by_domain[domain][key].append((rel,line))
dup=[]
for dom,keys in by_domain.items():
    for key,locs in keys.items():
        if len(locs)>1: dup.append({'domain':dom,'key':key,'locations':locs})
report['duplicate_top_level_defs']=dup

# Vanilla common manifest comparison
cur={p.relative_to(COMMON).as_posix():p for p in iter_files(COMMON)}
van={p.relative_to(VANILLA).as_posix():p for p in iter_files(VANILLA)}
shared=sorted(cur.keys() & van.keys())
identical=[]; modified=[]
for r in shared:
    if cur[r].stat().st_size==van[r].stat().st_size and sha(cur[r])==sha(van[r]): identical.append(r)
    else: modified.append({'path':r,'mod_size':cur[r].stat().st_size,'vanilla_size':van[r].stat().st_size})
report['vanilla_compare']={
    'mod_file_count':len(cur),'vanilla_file_count':len(van),'shared_count':len(shared),
    'identical_count':len(identical),'modified_same_path_count':len(modified),
    'only_mod_count':len(cur.keys()-van.keys()),'only_vanilla_count':len(van.keys()-cur.keys()),
    'identical':identical,'modified_same_path':modified,
    'only_mod':sorted(cur.keys()-van.keys()),'only_vanilla':sorted(van.keys()-cur.keys())
}

# replace_path coverage: vanilla files hidden by each replaced common path
coverage=[]
for rp in replace_paths:
    if not rp.startswith('common/'): continue
    sub=rp[len('common/'):].strip('/')
    vf=[r for r in van if r==sub or r.startswith(sub+'/')]
    mf=[r for r in cur if r==sub or r.startswith(sub+'/')]
    missing=sorted(set(vf)-set(mf))
    coverage.append({'replace_path':rp,'vanilla_files':len(vf),'mod_files':len(mf),'hidden_vanilla_missing_count':len(missing),'hidden_vanilla_missing':missing})
report['replace_path_coverage']=coverage

# Latest error log parsing
err=LOGROOT/'error.log'
errors=[]; counts=Counter(); unresolved=Counter(); event_missing=Counter(); modifier_warn=Counter(); loc=None; last_error=None
if err.exists():
    lines=err.read_text(encoding='utf-8-sig',errors='replace').splitlines()
    for i,line in enumerate(lines,1):
        if 'Script system error!' in line: last_error={'line':i,'error':'','location':''}; errors.append(last_error)
        if last_error is not None:
            m=re.search(r'^\s*Error:\s*(.*)',line)
            if m: last_error['error']=m.group(1); counts[m.group(1).split(' [',1)[0]]+=1
            m=re.search(r'^\s*Script location:\s*(.*)',line)
            if m: last_error['location']=m.group(1); last_error=None
        for obj in re.findall(r"Invalid database object '([^']+)'",line): unresolved[obj]+=1
        m=re.search(r'Event not found! EventID:\s*([^\s\]]+)',line)
        if m: event_missing[m.group(1)]+=1
        m=re.search(r"'([^']+)' does not have a valid namespace",line)
        if m: event_missing[m.group(1)]+=1
        m=re.search(r'Modifier type definition (\S+) is defined in script but not in code',line)
        if m: modifier_warn[m.group(1)]+=1
    report['latest_error_log']={
        'line_count':len(lines),'script_error_count':len(errors),'script_error_types':counts,
        'invalid_database_objects':unresolved,'missing_events':event_missing,
        'modifier_type_warnings':modifier_warn,
        'assertion_count':sum('Assertion failed' in x for x in lines),
        'missing_leader_count':sum('Could not get leader' in x for x in lines),
        'unset_scope_count':sum('unset scope' in x.lower() for x in lines),
        'unknown_trigger_count':sum('Unknown trigger type' in x for x in lines),
        'unexpected_token_count':sum('Unexpected token' in x for x in lines),
        'script_errors':errors,
        'tail':lines[-100:]
    }

# Known DB definition sets in current mod
sets={}
for name,path in {
    'character_templates':ROOT/'common/character_templates',
    'political_movements':ROOT/'common/political_movements',
    'journal_entries':ROOT/'common/journal_entries',
    'events':ROOT/'events',
    'government_types':ROOT/'common/government_types',
    'country_formations':ROOT/'common/country_formation',
}.items():
    vals=set()
    for p in iter_files(path):
        if p.suffix.lower()!='.txt': continue
        t,_=read_text(p)
        if t is None: continue
        if name=='events':
            vals.update(re.findall(r'(?m)^\s*id\s*=\s*([A-Za-z0-9_.-]+)\s*$',strip_comments_and_strings(t)))
        else:
            vals.update(k for k,_ in top_defs(t))
    sets[name]=sorted(vals)
report['defined_db_keys']={k:{'count':len(v),'keys':v} for k,v in sets.items()}

# Missing event ids definitively unresolved in current events
if 'latest_error_log' in report:
    defined_events=set(sets['events'])
    report['missing_events_not_defined_now']=sorted(k for k in report['latest_error_log']['missing_events'] if k not in defined_events)

# Crash dirs
if CRASHROOT.exists():
    dirs=sorted([p.name for p in CRASHROOT.iterdir() if p.is_dir()])
    report['crash_dirs']=dirs

# Markdown summary
vc=report['vanilla_compare']; le=report.get('latest_error_log',{})
md=[]
md.append('# ToE full audit')
md.append('')
md.append(f'- MOD common files: {vc["mod_file_count"]}')
md.append(f'- Vanilla 1.13.11 common files: {vc["vanilla_file_count"]}')
md.append(f'- Same path: {vc["shared_count"]} (identical {vc["identical_count"]}, modified {vc["modified_same_path_count"]})')
md.append(f'- MOD-only: {vc["only_mod_count"]}; vanilla-only: {vc["only_vanilla_count"]}')
md.append(f'- Brace/syntax structural errors: {len(report["syntax_brace_errors"])}')
md.append(f'- Decode failures: {len(report["decode_failures"])}')
md.append(f'- Tiny files <=4 bytes: {len(report["tiny_files"])}')
md.append(f'- Comment-only files: {len(report["comment_only_files"])}')
md.append(f'- Duplicate top-level keys: {len(report["duplicate_top_level_defs"])}')
if le:
    md.append(f'- Latest error.log lines: {le["line_count"]}')
    md.append(f'- Script errors: {le["script_error_count"]}')
    md.append(f'- Invalid DB object unique: {len(le["invalid_database_objects"])}')
    md.append(f'- Missing event unique: {len(le["missing_events"])}')
    md.append(f'- Modifier type warning unique: {len(le["modifier_type_warnings"])}')
    md.append(f'- Assertions: {le["assertion_count"]}; missing leaders: {le["missing_leader_count"]}; unset scopes: {le["unset_scope_count"]}')
md.append('')
md.append('## Brace/syntax errors')
for x in report['syntax_brace_errors'][:300]: md.append(f'- `{x["path"]}`: {x["problem"]}')
md.append('')
md.append('## Tiny/comment-only files')
for x in report['tiny_files'][:300]: md.append(f'- tiny `{x["path"]}` ({x["size"]} bytes)')
for x in report['comment_only_files'][:300]: md.append(f'- comment-only `{x["path"]}` ({x["size"]} bytes)')
md.append('')
md.append('## Latest invalid DB objects')
for k,v in sorted(le.get('invalid_database_objects',{}).items(), key=lambda kv:(-kv[1],kv[0])): md.append(f'- `{k}` x{v}')
md.append('')
md.append('## Latest missing events')
for k,v in sorted(le.get('missing_events',{}).items(), key=lambda kv:(-kv[1],kv[0])): md.append(f'- `{k}` x{v}')
md.append('')
md.append('## Modifier warnings')
for k,v in le.get('modifier_type_warnings',{}).items(): md.append(f'- `{k}` x{v}')
md.append('')
md.append('## Replace path coverage')
for c in coverage: md.append(f'- `{c["replace_path"]}`: vanilla {c["vanilla_files"]}, mod {c["mod_files"]}, hidden/missing {c["hidden_vanilla_missing_count"]}')
md.append('')
md.append('## Duplicate top-level definitions')
for d in dup[:500]: md.append(f'- `{d["domain"]}` `{d["key"]}`: {d["locations"]}')

(OUT/'toe_full_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=lambda x:dict(x)),encoding='utf-8')
(OUT/'toe_full_audit.md').write_text('\n'.join(md),encoding='utf-8')
print('\n'.join(md[:600]))
print(f'\nFULL_REPORT_JSON={OUT/"toe_full_audit.json"}')
