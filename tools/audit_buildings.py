#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDING_DIR = ROOT / "common/history/buildings"
REPORT = ROOT / "tools/building_audit_report.json"


def match_brace(text: str, open_pos: int) -> int:
    depth = 0
    i = open_pos
    quote = False
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                quote = False
            i += 1
            continue
        if ch == '"':
            quote = True
            i += 1
            continue
        if ch == '#':
            nl = text.find('\n', i)
            if nl == -1:
                return len(text) - 1
            i = nl + 1
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"Unmatched brace at {open_pos}")


def blocks(text: str, pattern: re.Pattern[str], start: int = 0, end: int | None = None):
    if end is None:
        end = len(text)
    pos = start
    while True:
        m = pattern.search(text, pos, end)
        if not m:
            break
        open_pos = text.find('{', m.start(), m.end() + 2)
        if open_pos < 0 or open_pos >= end:
            break
        close_pos = match_brace(text, open_pos)
        if close_pos >= end:
            break
        yield m, open_pos, close_pos
        pos = close_pos + 1


STATE_RE = re.compile(r'(?m)^\s*s:(STATE_[A-Za-z0-9_]+)\s*=\s*\{')
REGION_RE = re.compile(r'(?m)^\s*region_state:([A-Za-z0-9_]+)\s*=\s*\{')
BUILD_RE = re.compile(r'(?m)^\s*create_building\s*=\s*\{')
BUILDING_TYPE_RE = re.compile(r'\bbuilding\s*=\s*"([^"]+)"')
LEVEL_RE = re.compile(r'\blevels\s*=\s*(\d+)')
PM_RE = re.compile(r'activate_production_methods\s*=\s*\{([^}]*)\}', re.S)


def canonical(block_text: str) -> str:
    block_text = re.sub(r'(?m)#.*$', '', block_text)
    return re.sub(r'\s+', '', block_text)


def audit_file(path: Path):
    text = path.read_text(encoding='utf-8-sig')
    state_rows = []
    brace_error = None
    try:
        state_blocks = list(blocks(text, STATE_RE))
    except Exception as exc:
        state_blocks = []
        brace_error = str(exc)

    for sm, so, sc in state_blocks:
        state = sm.group(1)
        region_rows = []
        state_body_start, state_body_end = so + 1, sc
        try:
            region_blocks = list(blocks(text, REGION_RE, state_body_start, state_body_end))
        except Exception as exc:
            brace_error = brace_error or str(exc)
            region_blocks = []
        for rm, ro, rc in region_blocks:
            country = rm.group(1)
            building_rows = []
            try:
                building_blocks = list(blocks(text, BUILD_RE, ro + 1, rc))
            except Exception as exc:
                brace_error = brace_error or str(exc)
                building_blocks = []
            for bm, bo, bc in building_blocks:
                bt = text[bo + 1:bc]
                tm = BUILDING_TYPE_RE.search(bt)
                btype = tm.group(1) if tm else "<missing>"
                levels = [int(x) for x in LEVEL_RE.findall(bt)]
                pm = PM_RE.search(bt)
                building_rows.append({
                    "building": btype,
                    "levels_sum": sum(levels),
                    "levels": levels,
                    "pm": re.findall(r'"([^"]+)"', pm.group(1)) if pm else [],
                    "canonical": canonical(bt),
                })
            region_rows.append({"country": country, "buildings": building_rows})
        state_rows.append({"state": state, "regions": region_rows})
    return state_rows, brace_error


def main():
    all_states = []
    file_reports = {}
    brace_errors = {}
    for path in sorted(BUILDING_DIR.glob('*.txt')):
        rows, err = audit_file(path)
        all_states.extend((path.name, row) for row in rows)
        file_reports[path.name] = {"states": len(rows), "bytes": path.stat().st_size}
        if err:
            brace_errors[path.name] = err

    state_locations = defaultdict(list)
    region_dupes = []
    building_dupes = []
    exact_building_dupes = []
    admin_by_country = defaultdict(int)
    admin_by_country_state = defaultdict(lambda: defaultdict(int))

    for filename, srow in all_states:
        state = srow["state"]
        state_locations[state].append(filename)
        region_counts = Counter(r["country"] for r in srow["regions"])
        for country, count in sorted(region_counts.items()):
            if count > 1:
                region_dupes.append({"file": filename, "state": state, "country": country, "count": count})

        grouped = defaultdict(list)
        for r in srow["regions"]:
            grouped[r["country"]].extend(r["buildings"])
        for country, builds in grouped.items():
            bcounts = Counter(b["building"] for b in builds)
            for btype, count in sorted(bcounts.items()):
                if count > 1:
                    building_dupes.append({"file": filename, "state": state, "country": country, "building": btype, "count": count})
                    ccounts = Counter(b["canonical"] for b in builds if b["building"] == btype)
                    exact = sum(n - 1 for n in ccounts.values() if n > 1)
                    if exact:
                        exact_building_dupes.append({"file": filename, "state": state, "country": country, "building": btype, "exact_extra_copies": exact})
            for b in builds:
                if b["building"] == "building_government_administration":
                    admin_by_country[country] += b["levels_sum"]
                    admin_by_country_state[country][state] += b["levels_sum"]

    duplicated_states = [
        {"state": state, "locations": locs, "count": len(locs)}
        for state, locs in sorted(state_locations.items()) if len(locs) > 1
    ]

    report = {
        "summary": {
            "files": len(file_reports),
            "state_blocks": len(all_states),
            "duplicate_state_ids": len(duplicated_states),
            "duplicate_region_state_groups": len(region_dupes),
            "duplicate_building_groups": len(building_dupes),
            "exact_duplicate_building_groups": len(exact_building_dupes),
            "brace_errors": len(brace_errors),
        },
        "files": file_reports,
        "brace_errors": brace_errors,
        "duplicate_states": duplicated_states,
        "duplicate_region_states": region_dupes,
        "duplicate_buildings": building_dupes,
        "exact_duplicate_buildings": exact_building_dupes,
        "government_administration": {
            country: {
                "total_levels": total,
                "states": dict(sorted(admin_by_country_state[country].items())),
            }
            for country, total in sorted(admin_by_country.items())
        },
        "XBB_government_administration": {
            "total_levels": admin_by_country.get("XBB", 0),
            "states": dict(sorted(admin_by_country_state.get("XBB", {}).items())),
        },
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print("XBB", json.dumps(report["XBB_government_administration"], ensure_ascii=False))


if __name__ == '__main__':
    main()
