from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'_audit/toe_full_audit.json').read_text(encoding='utf-8'))
vc=r['vanilla_compare']; le=r.get('latest_error_log',{})
replace=[x.rstrip('/') for x in r['replace_paths']]

def under_replace(rel):
    p='common/'+rel
    return any(p==rp or p.startswith(rp+'/') for rp in replace)

print('=== DUPLICATE TOP LEVEL DEFINITIONS ===')
for d in r['duplicate_top_level_defs']:
    print(d['domain'], d['key'], d['locations'])

print('\n=== ALL REPLACE PATH COVERAGE ===')
for c in r['replace_path_coverage']:
    print(c['replace_path'], 'vanilla=',c['vanilla_files'],'mod=',c['mod_files'],'hidden_missing=',c['hidden_vanilla_missing_count'])

print('\n=== SUSPICIOUS SAME-PATH SIZE DIFFERENCES ===')
for x in vc['modified_same_path']:
    vs=x['vanilla_size']; ms=x['mod_size']
    ratio=(ms/vs) if vs else 999
    if ratio < 0.15 or ratio > 6 or ms <= 200:
        print(f"{x['path']} mod={ms} vanilla={vs} ratio={ratio:.4f} replace={under_replace(x['path'])}")

print('\n=== COMMENT-ONLY SAME-PATH FILES OUTSIDE REPLACE_PATH ===')
comment={x['path'] for x in r['comment_only_files']}
shared=set(vc['identical']) | {x['path'] for x in vc['modified_same_path']}
for p in sorted(comment):
    if not p.startswith('common/'): continue
    rel=p[len('common/'):]
    if rel in shared and not under_replace(rel):
        print(p)

print('\n=== MISSING EVENT CALLERS ===')
for e in le.get('script_errors',[]):
    err=e.get('error','')
    if 'Event not found!' in err or 'does not have a valid namespace' in err:
        print(err, '<<<', e.get('location',''))

print('\n=== NON-EVENT SCRIPT ERRORS ===')
for e in le.get('script_errors',[]):
    err=e.get('error','')
    if 'Event not found!' not in err and 'does not have a valid namespace' not in err:
        print(err, '<<<', e.get('location',''))

print('\n=== LAND REFORM MODIFIER SEARCH ===')
for base in [ROOT/'common', ROOT/'gpt送信用'/'common']:
    print('BASE',base.relative_to(ROOT))
    for p in base.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in {'.txt','.yml','.yaml','.gui'}: continue
        try: txt=p.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError: continue
        if 'state_pop_support_movement_land_reform' in txt:
            print(p.relative_to(ROOT))
            for i,line in enumerate(txt.splitlines(),1):
                if 'state_pop_support_movement_land_reform' in line:
                    lo=max(1,i-3); hi=min(len(txt.splitlines()),i+8)
                    lines=txt.splitlines()
                    print(f'  line {i}:')
                    for n in range(lo,hi+1): print(f'    {n}: {lines[n-1]}')

print('\n=== ALL SCRIPT ERROR TYPE COUNTS ===')
for k,v in sorted(le.get('script_error_types',{}).items(), key=lambda x:(-x[1],x[0])):
    print(v,k)

print('\n=== MODIFIER WARNINGS ===')
for k,v in le.get('modifier_type_warnings',{}).items(): print(k,v)

print('\n=== ERROR LOG TAIL ===')
for x in le.get('tail',[]): print(x)
