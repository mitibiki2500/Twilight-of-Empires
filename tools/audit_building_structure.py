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
# Corruption patterns seen in ToE when an inserted create_building split an existing token.
SPLIT_LEVELS_LEFT = re.compile(r'(?m)^[ \t]*lev[ \t]*$')
SPLIT_LEVELS_RIGHT = re.compile(r'(?m)^[ \t]*els[ \t]*=')
SPLIT_COUNTRY_LEFT = re.compile(r'(?m)^[ \t]*c[ \t]*$')
SPLIT_COUNTRY_RIGHT = re.compile(r'(?m)^[ \t]*ountry[ \t]*=')


def spans(text, pattern, start=0, end=None):
    return [(m, o, c) for m,o,c in a.blocks(text, pattern, start, len(text) if end is None else end)]


def line_no(text: str, pos: int) -> int:
    return text.count('\n', 0, pos) + 1


def main():
    files = {}
    totals = {
        'state_tokens':0,
        'nested_states':0,
        'region_tokens':0,
        'nested_regions':0,
        'building_tokens':0,
        'buildings_inside_region':0,
        'nested_create_buildings':0,
        'split_token_fragments':0,
    }
    bad_layout=[]
    orphan_buildings=[]
    nested_create_buildings=[]
    split_token_fragments=[]

    for p in sorted(BDIR.glob('*.txt')):
        text=p.read_text(encoding='utf-8-sig')
        state_spans=spans(text,STATE)
        region_spans=[]
        for sm,so,sc in state_spans:
            for rm,ro,rc in spans(text,REGION,so+1,sc):
                region_spans.append((rm,ro,rc,sm.group(1)))

        build_matches=list(BUILD.finditer(text))
        inside_count=0
        file_nested=0
        file_split=0

        # Detect create_building blocks physically nested inside another create_building.
        # Normal history layout has sibling create_building blocks under region_state;
        # nesting is a strong sign that a block was pasted into the middle of another one.
        build_blocks=[]
        for bm in build_matches:
            try:
                bo=text.find('{',bm.start(),bm.end()+2)
                bc=a.match_brace(text,bo)
                build_blocks.append((bm,bo,bc))
            except Exception:
                continue
        for i,(outer,obo,obc) in enumerate(build_blocks):
            for j,(inner,ibo,ibc) in enumerate(build_blocks):
                if i == j:
                    continue
                if outer.start() < inner.start() < obc:
                    nested_create_buildings.append({
                        'file':p.name,
                        'outer_line':line_no(text,outer.start()),
                        'inner_line':line_no(text,inner.start()),
                    })
                    file_nested += 1
                    break

        # Detect exact split-token signatures previously observed in corrupted ToE history.
        split_patterns = [
            ('split_levels_left', SPLIT_LEVELS_LEFT),
            ('split_levels_right', SPLIT_LEVELS_RIGHT),
            ('split_country_left', SPLIT_COUNTRY_LEFT),
            ('split_country_right', SPLIT_COUNTRY_RIGHT),
        ]
        for issue, pattern in split_patterns:
            for m in pattern.finditer(text):
                split_token_fragments.append({
                    'file':p.name,
                    'line':line_no(text,m.start()),
                    'issue':issue,
                    'text':m.group(0).strip(),
                })
                file_split += 1

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
            line=line_no(text,bm.start())
            orphan_buildings.append({'file':p.name,'line':line,'state':state_name,'building':bt.group(1) if bt else None,'country_hint':co.group(1) if co else None,'snippet':' '.join(raw.strip().split())[:500]})

        row={
            'state_tokens':len(STATE.findall(text)),
            'nested_states':len(state_spans),
            'region_tokens':len(REGION.findall(text)),
            'nested_regions':len(region_spans),
            'building_tokens':len(build_matches),
            'buildings_inside_region':inside_count,
            'nested_create_buildings':file_nested,
            'split_token_fragments':file_split,
        }
        files[p.name]=row
        for k,v in row.items(): totals[k]+=v
        # A comment must never be attached to the STATE declaration itself.
        # Adjacent state-name and country-name labels are intentional and readable.
        if re.search(r's:STATE_[A-Za-z0-9_]+\s*=\s*\{[^\n]*#', text):
            bad_layout.append({'file':p.name,'issue':'comment attached to STATE line'})

    ok=(
        totals['state_tokens']==totals['nested_states']
        and totals['region_tokens']==totals['nested_regions']
        and totals['building_tokens']==totals['buildings_inside_region']
        and not bad_layout
        and not orphan_buildings
        and not nested_create_buildings
        and not split_token_fragments
    )
    report={
        'ok':ok,
        'totals':totals,
        'bad_layout':bad_layout,
        'orphan_buildings':orphan_buildings,
        'nested_create_buildings':nested_create_buildings,
        'split_token_fragments':split_token_fragments,
        'files':files,
    }
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
