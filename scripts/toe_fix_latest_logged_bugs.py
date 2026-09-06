from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

COUNTRIES = ['AFS','ALB','FIN','IQU','IRE','LUX','TEX','TIS']
JES = ['je_austrian_neo_absolutism','je_positivist_movement','je_the_two_spains']

COUNTRY_FILE = ROOT/'common/country_definitions/99_toe_latest_log_country_compat.txt'
JE_FILE = ROOT/'common/journal_entries/99_toe_missing_vanilla_je_compat.txt'
MON_FILE = ROOT/'common/journal_entries/05_montenegro_je.txt'

COUNTRY_BLOCK = '''# ToE compatibility definitions for vanilla script references found in the latest crash log.
# These tags receive no country history; they only make c:TAG references resolvable.

{blocks}'''


def existing_top_defs(base: Path) -> set[str]:
    out=set()
    if not base.exists(): return out
    for p in base.rglob('*.txt'):
        text=p.read_text(encoding='utf-8-sig',errors='strict')
        clean=re.sub(r'"(?:\\.|[^"\\])*"','""',text)
        clean=re.sub(r'#.*','',clean)
        out.update(re.findall(r'(?m)^\s*([A-Za-z0-9_]+)\s*=\s*\{',clean))
    return out


def make_country_block(tag: str) -> str:
    return f'''{tag} = {{
    color = {{ 120 120 120 }}
    country_type = unrecognized
    tier = principality
    cultures = {{ nsm_map_pai }}
    religion = orthodox
    capital = STATE_NSM_001
}}
'''


def patch_montenegro() -> int:
    text=MON_FILE.read_text(encoding='utf-8-sig')
    old1='''\t\t\t\t\trandom = {\n\t\t\t\t\t\tchance = {\n\t\t\t\t\t\t\tadd = 2\n\t\t\t\t\t\t\tmultiply = raiding_level\n\t\t\t\t\t\t\tsubtract = 3\n\t\t\t\t\t\t\tmultiply = 0.15 #more likely\n\t\t\t\t\t\t}\n\t\t\t\t\t\t# ToE 1.13 compatibility: disabled dangling reference: missing event montenegrin_raiding.1\n\t\t\t\t\t\t# trigger_event = {\n\t\t\t\t\t\t# \tid = montenegrin_raiding.1\n\t\t\t\t\t\t# \tpopup = yes\n\t\t\t\t\t\t# }\n\t\t\t\t\t}\n'''
    old2='''\t\t\t\t\trandom = {\n\t\t\t\t\t\tchance = {\n\t\t\t\t\t\t\tadd = 2\n\t\t\t\t\t\t\tmultiply = raiding_level\n\t\t\t\t\t\t\tsubtract = 3\n\t\t\t\t\t\t\tmultiply = 0.1\n\t\t\t\t\t\t}\n\t\t\t\t\t\t# ToE 1.13 compatibility: disabled dangling reference: missing event montenegrin_raiding.2\n\t\t\t\t\t\t# trigger_event = {\n\t\t\t\t\t\t# \tid = montenegrin_raiding.2\n\t\t\t\t\t\t# \tpopup = yes\n\t\t\t\t\t\t# }\n\t\t\t\t\t}\n'''
    new1='''\t\t\t\t\t# ToE 1.13 compatibility: removed empty random effect after dangling event removal (montenegrin_raiding.1)\n'''
    new2='''\t\t\t\t\t# ToE 1.13 compatibility: removed empty random effect after dangling event removal (montenegrin_raiding.2)\n'''
    if text.count(old1)!=1 or text.count(old2)!=1:
        raise RuntimeError(f'Montenegro exact-match check failed: old1={text.count(old1)} old2={text.count(old2)}')
    text=text.replace(old1,new1).replace(old2,new2)
    MON_FILE.write_text(text,encoding='utf-8-sig')
    return 2


def check_balanced(text: str) -> bool:
    clean=re.sub(r'"(?:\\.|[^"\\])*"','""',text)
    clean=re.sub(r'#.*','',clean)
    d=0
    for ch in clean:
        if ch=='{': d+=1
        elif ch=='}':
            d-=1
            if d<0: return False
    return d==0


def main():
    defs=existing_top_defs(ROOT/'common/country_definitions')
    missing=[t for t in COUNTRIES if t not in defs]
    if missing:
        blocks=''.join(make_country_block(t) for t in missing)
        COUNTRY_FILE.write_text(COUNTRY_BLOCK.format(blocks=blocks),encoding='utf-8')
    elif not COUNTRY_FILE.exists():
        COUNTRY_FILE.write_text('# All latest-log country tags were already defined.\n',encoding='utf-8')

    je_defs=existing_top_defs(ROOT/'common/journal_entries')
    missing_jes=[t for t in JES if t not in je_defs]
    if missing_jes:
        lines=['# ToE compatibility stubs for vanilla script references whose real JEs are intentionally removed by the total conversion.','']
        for je in missing_jes:
            lines += [f'{je} = {{','\tgroup = je_group_historical_content','\tpossible = {','\t\talways = no','\t}','\tcomplete = {','\t\talways = no','\t}','\tinvalid = {','\t\talways = yes','\t}','\tweight = 0','\ttransferable = no','}','']
        JE_FILE.write_text('\n'.join(lines),encoding='utf-8')
    elif not JE_FILE.exists():
        JE_FILE.write_text('# All latest-log JE types were already defined.\n',encoding='utf-8')

    random_removed=patch_montenegro()

    # Structural validation of all files touched by this repair.
    touched=[COUNTRY_FILE,JE_FILE,MON_FILE]
    for p in touched:
        if not check_balanced(p.read_text(encoding='utf-8-sig')):
            raise RuntimeError(f'Brace validation failed: {p}')

    print('MISSING_COUNTRY_COMPAT_ADDED',missing)
    print('MISSING_JE_COMPAT_ADDED',missing_jes)
    print('EMPTY_RANDOM_EFFECTS_REMOVED',random_removed)
    print('LATEST_LOG_BUG_REPAIR_OK')

if __name__=='__main__': main()
