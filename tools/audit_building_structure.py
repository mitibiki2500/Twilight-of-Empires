#!/usr/bin/env python3
from __future__ import annotations
import json
import re
from pathlib import Path
import audit_buildings as a

ROOT = Path(__file__).resolve().parents[1]
BDIR = ROOT / 'common/history/buildings'
OUT = ROOT / 'tools/building_structure_report.json'

STATE = re.compile(r'(?m)^[ \t]*s:(STATE_[A-Za-z0-9_]+)[ \t]*=[ \t]*\{')
REGION = re.compile(r'(?m)^[ \t]*region_state:([A-Za-z0-9_]+)[ \t]*=[ \t]*\{')
BUILD = re.compile(r'(?m)^[ \t]*create_building[ \t]*=[ \t]*\{')


def count_nested(text: str):
    state_list = list(a.blocks(text, STATE))
    region_count = 0
    building_count = 0
    for _, so, sc in state_list:
        for _, ro, rc in a.blocks(text, REGION, so + 1, sc):
            region_count += 1
            for _ in a.blocks(text, BUILD, ro + 1, rc):
                building_count += 1
    return len(state_list), region_count, building_count


def main():
    files = {}
    totals = {'state_tokens':0,'nested_states':0,'region_tokens':0,'nested_regions':0,'building_tokens':0,'nested_buildings':0}
    bad_layout=[]
    for p in sorted(BDIR.glob('*.txt')):
        text=p.read_text(encoding='utf-8-sig')
        st=len(STATE.findall(text)); rg=len(REGION.findall(text)); bg=len(BUILD.findall(text))
        ns,nr,nb=count_nested(text)
        row={'state_tokens':st,'nested_states':ns,'region_tokens':rg,'nested_regions':nr,'building_tokens':bg,'nested_buildings':nb}
        files[p.name]=row
        for k,v in row.items(): totals[k]+=v
        if re.search(r's:STATE_[A-Za-z0-9_]+\s*=\s*\{[^\n]*#\s*(?:Country:|.+\([A-Z0-9]{3}\))', text):
            bad_layout.append({'file':p.name,'issue':'country comment attached to STATE line'})
        if re.search(r'(?m)^[ \t]*#\s*(?:Country:.*|.*\([A-Z0-9]{3}\))[ \t]*\n[ \t]*#\s*(?:Country:.*|.*\([A-Z0-9]{3}\))[ \t]*$', text):
            bad_layout.append({'file':p.name,'issue':'consecutive country comments'})
    ok=(totals['state_tokens']==totals['nested_states'] and totals['region_tokens']==totals['nested_regions'] and totals['building_tokens']==totals['nested_buildings'] and not bad_layout)
    report={'ok':ok,'totals':totals,'bad_layout':bad_layout,'files':files}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
