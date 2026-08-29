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
BTYPE = re.compile(r'\bbuilding\s*=\s*"([^"]+)"')
COUNTRY = re.compile(r'\bcountry\s*=\s*"?c:([A-Za-z0-9_]+)"?')


def spans(text, pattern, start=0, end=None):
    return [(m, o, c) for m,o,c in a.blocks(text, pattern, start, len(text) if end is None else end)]


def main():
    files = {}
    totals = {'state_tokens':0,'nested_states':0,'region_tokens':0,'nested_regions':0,'building_tokens':0,'buildings_inside_region':0}
    bad_layout=[]
    orphan_buildings=[]
    for p in sorted(BDIR.glob('*.txt')):
        text=p.read_text(encoding='utf-8-sig')
        state_spans=spans(text,STATE)
        region_spans=[]
        for sm,so,sc in state_spans:
            for rm,ro,rc in spans(text,REGION,so+1,sc):
                region_spans.append((rm,ro,rc,sm.group(1)))

        build_matches=list(BUILD.finditer(text))
        inside_count=0
        for bm in build_matches:
            containing_region=None
            for rm,ro,rc,state_name in region_spans:
                if rm.start() <= bm.start() <= rc:
                    containing_region=(rm,ro,rc,state_name)
                    break
            if containing_region:
                inside_count += 1
                continue
            state_name=None
            for sm,so,sc in state_spans:
                if sm.start() <= bm.start() <= sc:
                    state_name=sm.group(1); break
            try:
                bo=text.find('{',bm.start(),bm.end()+2)
                bc=a.match_brace(text,bo)
                raw=text[bm.start():bc+1]
            except Exception:
                raw=text[bm.start():text.find('\n',bm.start())]
            bt=BTYPE.search(raw)
            co=COUNTRY.search(raw)
            line=text.count('\n',0,bm.start())+1
            orphan_buildings.append({'file':p.name,'line':line,'state':state_name,'building':bt.group(1) if bt else None,'country_hint':co.group(1) if co else None,'snippet':' '.join(raw.strip().split())[:500]})

        row={'state_tokens':len(STATE.findall(text)),'nested_states':len(state_spans),'region_tokens':len(REGION.findall(text)),'nested_regions':len(region_spans),'building_tokens':len(build_matches),'buildings_inside_region':inside_count}
        files[p.name]=row
        for k,v in row.items(): totals[k]+=v
        # Country comments use three-letter country tags. State-name comments end
        # with STATE_NSM_### and must not be treated as duplicate country labels.
        if re.search(r's:STATE_[A-Za-z0-9_]+\s*=\s*\{[^\n]*#\s*(?:Country:|.+\([A-Z]{3}\))', text):
            bad_layout.append({'file':p.name,'issue':'country comment attached to STATE line'})
        if re.search(r'(?m)^[ \t]*#\s*(?:Country:.*|.*\([A-Z]{3}\))[ \t]*\n[ \t]*#\s*(?:Country:.*|.*\([A-Z]{3}\))[ \t]*$', text):
            bad_layout.append({'file':p.name,'issue':'consecutive country comments'})
    ok=(totals['state_tokens']==totals['nested_states'] and totals['region_tokens']==totals['nested_regions'] and totals['building_tokens']==totals['buildings_inside_region'] and not bad_layout and not orphan_buildings)
    report={'ok':ok,'totals':totals,'bad_layout':bad_layout,'orphan_buildings':orphan_buildings,'files':files}
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
