#!/usr/bin/env python3
from __future__ import annotations
import json,re
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]
BDIR=ROOT/'common/history/buildings'
SDIR=ROOT/'map_data/state_regions'
OUT=ROOT/'tools/economy_city_audit.json'

STATE_RE=re.compile(r's:(STATE_[A-Za-z0-9_]+)\s*=\s*\{')
REGION_RE=re.compile(r'region_state:([A-Za-z0-9_]+)\s*=\s*\{')
BUILD_RE=re.compile(r'create_building\s*=\s*\{')
TYPE_RE=re.compile(r'building\s*=\s*"([^"]+)"')
LEVEL_RE=re.compile(r'levels\s*=\s*(\d+)')

# small brace parser, comments/quotes aware
def close_brace(t,op):
    d=0;q=False;i=op
    while i<len(t):
        c=t[i]
        if q:
            if c=='\\\\': i+=2; continue
            if c=='"': q=False
        else:
            if c=='"': q=True
            elif c=='#':
                n=t.find('\n',i); i=len(t) if n<0 else n; continue
            elif c=='{': d+=1
            elif c=='}':
                d-=1
                if d==0:return i
        i+=1
    raise ValueError(op)
def blocks(t,rx,start=0,end=None):
    end=len(t) if end is None else end; p=start
    while True:
        m=rx.search(t,p,end)
        if not m:break
        op=t.find('{',m.start(),m.end()+2); cl=close_brace(t,op)
        if cl>=end:break
        yield m,op,cl;p=cl+1

def building_levels(raw):
    # ownership levels are the effective starting levels in these ToE history files
    own=re.search(r'add_ownership\s*=\s*\{',raw)
    if not own:return 0
    op=raw.find('{',own.start()); cl=close_brace(raw,op)
    return sum(map(int,LEVEL_RE.findall(raw[op+1:cl])))

def economy():
    by_country=defaultdict(lambda:defaultdict(int)); states=defaultdict(set)
    wanted={'building_government_administration':'admin','building_paper_mill':'paper','building_construction_sector':'construction','building_trade_center':'trade'}
    for p in BDIR.glob('*.txt'):
        t=p.read_text(encoding='utf-8-sig',errors='ignore')
        for sm,so,sc in blocks(t,STATE_RE):
            sid=sm.group(1)
            for rm,ro,rc in blocks(t,REGION_RE,so+1,sc):
                c=rm.group(1);states[c].add(sid)
                for bm,bo,bc in blocks(t,BUILD_RE,ro+1,rc):
                    raw=t[bm.start():bc+1];tm=TYPE_RE.search(raw)
                    if tm and tm.group(1) in wanted:
                        by_country[c][wanted[tm.group(1)]]+=building_levels(raw)
    rows=[]
    for c in sorted(set(by_country)|set(states)):
        d=by_country[c]; n=len(states[c]); a=d['admin']
        rows.append({'country':c,'states':n,'administration':a,'admin_per_state':round(a/n,2) if n else None,'paper_mills':d['paper'],'construction_sectors':d['construction'],'trade_centers':d['trade']})
    # Static triage only, not a bureaucracy verdict: extremes are best targets for in-game verification.
    ranked=sorted(rows,key=lambda r:(r['admin_per_state'] if r['admin_per_state'] is not None else -1),reverse=True)
    return {'countries':rows,'high_admin_per_state_candidates':ranked[:20],'low_admin_per_state_candidates':sorted([r for r in rows if r['states']>=2],key=lambda r:r['admin_per_state'] if r['admin_per_state'] is not None else 999)[:20]}

def city():
    state_rx=re.compile(r'(?m)^\s*(STATE_[A-Za-z0-9_]+)\s*=\s*\{')
    id_rx=re.compile(r'(?m)^\s*id\s*=\s*(\d+)')
    city_rx=re.compile(r'(?m)^\s*city\s*=\s*"?([xX][0-9A-Fa-f]+)"?')
    prov_rx=re.compile(r'(?m)^\s*provinces\s*=\s*\{([^}]*)\}')
    locator=ROOT/'gfx/map/map_object_data/generated_map_object_locators_city.txt'
    lt=locator.read_text(encoding='utf-8-sig',errors='ignore') if locator.exists() else ''
    locator_ids=set(map(int,re.findall(r'(?m)^\s*id\s*=\s*(\d+)',lt)))
    rows=[]; all_ids=[]
    for p in SDIR.glob('*.txt'):
        if p.name=='99_seas.txt':continue
        t=p.read_text(encoding='utf-8-sig',errors='ignore')
        for sm,so,sc in blocks(t,state_rx):
            raw=t[sm.start():sc+1]; im=id_rx.search(raw); cm=city_rx.search(raw); pm=prov_rx.search(raw)
            if not im:continue
            i=int(im.group(1)); all_ids.append(i)
            provs=set(re.findall(r'[xX][0-9A-Fa-f]+',pm.group(1))) if pm else set()
            cp=cm.group(1) if cm else None
            rows.append({'state':sm.group(1),'id':i,'city_province':cp,'has_city_hub':bool(cp),'city_in_provinces':bool(cp and cp in provs),'has_city_locator':i in locator_ids})
    missing_hub=[r for r in rows if not r['has_city_hub']]
    bad_hub=[r for r in rows if r['has_city_hub'] and not r['city_in_provinces']]
    missing_locator=[r for r in rows if r['has_city_hub'] and not r['has_city_locator']]
    extra_locator=sorted(locator_ids-set(all_ids))
    return {'state_count':len(rows),'city_locator_count':len(locator_ids),'missing_city_hub':missing_hub,'city_hub_outside_state_provinces':bad_hub,'missing_city_locator':missing_locator,'extra_city_locator_ids':extra_locator,'city_data_directory_exists':(ROOT/'gfx/map/city_data').exists(),'locator_file_exists':locator.exists()}

def main():
    r={'economy':economy(),'city_graphics':city()}
    OUT.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'economy_countries':len(r['economy']['countries']),'city':r['city_graphics']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
