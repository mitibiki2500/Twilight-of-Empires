#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tools/rollback_audit_report.json'


def all_text_files():
    for p in ROOT.rglob('*'):
        if not p.is_file() or '.git' in p.parts:
            continue
        if p.suffix.lower() in {'.txt', '.yml', '.yaml', '.csv', '.md'}:
            yield p


def read(p: Path):
    try:
        return p.read_text(encoding='utf-8-sig', errors='ignore')
    except OSError:
        return ''


def find_any(pattern: str, files=None, flags=re.S):
    rx = re.compile(pattern, flags)
    hits = []
    for p in files or all_text_files():
        txt = read(p)
        if rx.search(txt):
            hits.append(str(p.relative_to(ROOT)))
    return sorted(set(hits))


def check(name, ok, detail):
    return {'name': name, 'ok': bool(ok), 'detail': detail}


def main():
    checks = []

    static = ROOT / 'common/static_modifiers/00_code_static_modifiers.txt'
    static_txt = read(static)
    checks.append(check('MAPI base 72', 'state_market_access_price_impact = 0.72' in static_txt or 'state_market_access_price_impact=0.72' in static_txt,
                        str(static.relative_to(ROOT))))

    station = ROOT / 'common/amendments/99_toe_alti_station_system.txt'
    stxt = read(station)
    station_expected = [
        'country_bureaucracy_mult = 0.10',
        'state_tax_capacity_add = 15',
        'state_tax_capacity_mult = 0.15',
    ]
    checks.append(check('Alti station system modifiers', all(x in stxt for x in station_expected), station_expected))

    pollution = ROOT / 'common/amendments/98_toe_ria_soil_pollution_fund.txt'
    ptxt = read(pollution)
    pollution_expected = [
        'state_harvest_condition_toe_great_war_compound_contamination_impact_mult = -0.15',
        'country_institution_cost_institution_health_system_mult = 0.15',
    ]
    checks.append(check('Ria pollution fund modifiers', all(x in ptxt for x in pollution_expected), pollution_expected))

    adjacency = ROOT / 'map_data/adjacencies.csv'
    atxt = read(adjacency)
    adj_expected = ['TOE temp tegar/newfoot market fix 01', 'TOE temp tegar/newfoot market fix 02']
    checks.append(check('New Foot temporary market links', all(x in atxt for x in adj_expected), adj_expected))

    # Tegar -> Gunma must be puppet.
    puppet_hits = find_any(r'country\s*=\s*c:XAZ[\s\S]{0,220}?type\s*=\s*puppet')
    vassal_xaz_hits = find_any(r'country\s*=\s*c:XAZ[\s\S]{0,220}?type\s*=\s*vassal')
    checks.append(check('Tegar -> Gunma puppet exists', bool(puppet_hits), puppet_hits))
    checks.append(check('No Tegar/Gunma vassal regression', not vassal_xaz_hits, vassal_xaz_hits))

    # Gunma -> MVA/KSO/KTO are vassals. Record presence anywhere because some versions
    # intentionally create them on_game_start rather than in country history.
    for tag in ('MVA', 'KSO', 'KTO'):
        hits = find_any(rf'country\s*=\s*c:{tag}[\s\S]{{0,220}}?type\s*=\s*vassal')
        checks.append(check(f'Gunma subject {tag} vassal relation present', bool(hits), hits))

    # Alti heir traits: all three expected traits must still exist together in a nearby block.
    heir_hits = find_any(r'experienced_offensive_planner[\s\S]{0,900}?direct[\s\S]{0,900}?pious|'
                         r'direct[\s\S]{0,900}?experienced_offensive_planner[\s\S]{0,900}?pious|'
                         r'pious[\s\S]{0,900}?direct[\s\S]{0,900}?experienced_offensive_planner')
    checks.append(check('Alti heir three traits present', bool(heir_hits), heir_hits))
    skeptical_hits = find_any(r'\bskeptical\b')
    checks.append(check('Invalid skeptical trait absent', not skeptical_hits, skeptical_hits))

    # Tier0 regression guard: the three individually-added techs must not reappear in the
    # same XAI country-history file. This does not guess the internal Tier0 implementation.
    country_files = list((ROOT / 'common/history/countries').glob('*.txt')) if (ROOT / 'common/history/countries').exists() else []
    tier_regress = []
    xai_files = []
    for p in country_files:
        txt = read(p)
        if 'XAI' in txt or 'c:XAI' in txt or p.name.upper().startswith('XAI'):
            xai_files.append(str(p.relative_to(ROOT)))
            if all(t in txt for t in ('railways', 'percussion_caps', 'intensive_agriculture')):
                tier_regress.append(str(p.relative_to(ROOT)))
    checks.append(check('Tegar no redundant three-tech regression', not tier_regress, {'XAI_files': xai_files, 'regressions': tier_regress}))

    # Prestige DDS assets that were explicitly restored.
    dds_names = [
        'saudi_aramco_oil_prestige.dds', 'gazprom_natural_gas_prestige.dds',
        'apple_iphones_prestige.dds', 'smartphones_prestige.dds',
        'olivetti_teleprinters_prestige.dds', 'asml_euv_lithography_machines_prestige.dds',
        'intel_processors_prestige.dds', 'gpu_prestige.dds', 'wafers_prestige.dds',
        'MB_holy_prestige.dds', 'MB_gold_prestige.dds', 'MR_bscopper.dds',
    ]
    dds_found = {}
    for name in dds_names:
        dds_found[name] = [str(p.relative_to(ROOT)) for p in ROOT.rglob(name)]
    checks.append(check('All 12 restored prestige DDS assets exist', all(dds_found[n] for n in dds_names), dds_found))

    # Fixed MR00 mappings should point to MSN paths, not the old nsm names.
    mapping_terms = ['premium cotton', 'machida tools', 'premium grain', 'premium sulfur', 'ikafry', 'premium ship']
    mapping_files = []
    bad_mapping_files = []
    for p in all_text_files():
        txt = read(p)
        low = txt.lower()
        if any(term in low for term in mapping_terms):
            mapping_files.append(str(p.relative_to(ROOT)))
            if 'nsm premium cotton' in low or 'nsm machida tools' in low or 'nsm premium grain' in low or 'nsm premium sulfur' in low or 'nsm ikafry' in low:
                bad_mapping_files.append(str(p.relative_to(ROOT)))
    checks.append(check('No known old nsm prestige mapping strings', not bad_mapping_files,
                        {'searched_files': sorted(set(mapping_files)), 'bad': sorted(set(bad_mapping_files))}))

    report = {
        'summary': {
            'passed': sum(1 for c in checks if c['ok']),
            'failed': sum(1 for c in checks if not c['ok']),
            'total': len(checks),
        },
        'checks': checks,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False))
    for c in checks:
        print(('PASS' if c['ok'] else 'FAIL'), c['name'], c['detail'])


if __name__ == '__main__':
    main()
