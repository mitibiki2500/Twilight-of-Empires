#!/usr/bin/env python3
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDING_DIR = ROOT / "common/history/buildings"

STATE_RE = re.compile(r'(?m)^\s*s:(STATE_[A-Za-z0-9_]+)\s*=\s*\{')
REGION_RE = re.compile(r'(?m)^\s*region_state:([A-Za-z0-9_]+)\s*=\s*\{')
BUILD_RE = re.compile(r'(?m)^\s*create_building\s*=\s*\{')
OWN_RE = re.compile(r'(?m)^\s*add_ownership\s*=\s*\{')
OWN_ENTRY_RE = re.compile(r'(?m)^\s*(country|building)\s*=\s*\{')
BUILDING_TYPE_RE = re.compile(r'\bbuilding\s*=\s*"([^"]+)"')
LEVEL_RE = re.compile(r'\blevels\s*=\s*(\d+)')

# Confirmed from the user's in-game bureaucracy screenshot and the previous
# 268 -> 105 balancing pass. State IDs are bound explicitly so ordering cannot
# accidentally move levels to another state.
XBB_ADMIN_TARGET = {
    "STATE_NSM_170": 3,
    "STATE_NSM_333": 3,
    "STATE_NSM_043": 14,
    "STATE_NSM_061": 7,
    "STATE_NSM_242": 6,
    "STATE_NSM_265": 13,
    "STATE_NSM_303": 13,
    "STATE_NSM_409": 18,
    "STATE_NSM_449": 17,
    "STATE_NSM_477": 7,
    "STATE_NSM_496": 4,
}


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


def find_blocks(text: str, pattern: re.Pattern[str], start: int = 0, end: int | None = None):
    if end is None:
        end = len(text)
    pos = start
    out = []
    while True:
        m = pattern.search(text, pos, end)
        if not m:
            break
        open_pos = text.find('{', m.start(), m.end() + 2)
        close_pos = match_brace(text, open_pos)
        if close_pos >= end:
            break
        out.append((m, open_pos, close_pos))
        pos = close_pos + 1
    return out


def canonical(text: str) -> str:
    text = re.sub(r'(?m)#.*$', '', text)
    return re.sub(r'\s+', '', text)


def replace_spans(text: str, replacements):
    for start, end, new in sorted(replacements, key=lambda x: x[0], reverse=True):
        text = text[:start] + new + text[end:]
    return text


def indent_block(text: str, prefix: str) -> str:
    lines = text.strip('\n').splitlines()
    # Remove common leading whitespace before applying the requested indentation.
    nonempty = [ln for ln in lines if ln.strip()]
    common = min((len(ln) - len(ln.lstrip())) for ln in nonempty) if nonempty else 0
    return '\n'.join(prefix + (ln[common:] if ln.strip() else '') for ln in lines)


def load_country_names():
    names = {}
    for p in ROOT.glob('localization/**/*.yml'):
        try:
            txt = p.read_text(encoding='utf-8-sig', errors='ignore')
        except OSError:
            continue
        for m in re.finditer(r'(?m)^\s*(X[A-Z0-9]{2}):\d*\s+"([^"]+)"', txt):
            names.setdefault(m.group(1), m.group(2))
    return names


def extract_ownership_entries(block_text: str):
    entries = []
    for _, oo, oc in find_blocks(block_text, OWN_RE):
        own_body = block_text[oo + 1:oc]
        for em, eo, ec in find_blocks(own_body, OWN_ENTRY_RE):
            raw = own_body[em.start():ec + 1]
            body = own_body[eo + 1:ec]
            levels = [int(x) for x in LEVEL_RE.findall(body)]
            # Target identity excludes level and formatting but retains country/type/region.
            target = canonical(LEVEL_RE.sub('', body))
            entries.append({
                'kind': em.group(1),
                'raw': raw,
                'body': body,
                'levels': sum(levels),
                'target': target,
                'exact': canonical(raw),
            })
    return entries


def build_ownership(entries, indent='\t\t\t\t'):
    # Identical ownership entries repeated by copied/revised create_building blocks
    # count once. Same target with genuinely different level values is additive.
    unique = []
    seen_exact = set()
    for e in entries:
        if e['exact'] in seen_exact:
            continue
        seen_exact.add(e['exact'])
        unique.append(e)

    grouped = defaultdict(list)
    order = []
    for e in unique:
        key = (e['kind'], e['target'])
        if key not in grouped:
            order.append(key)
        grouped[key].append(e)

    rendered = []
    for key in order:
        vals = grouped[key]
        # If the same target+level is repeated only because another property/PM was
        # revised, do not double the building. Different level values are additions.
        distinct_levels = []
        for e in vals:
            if e['levels'] not in distinct_levels:
                distinct_levels.append(e['levels'])
        total = sum(distinct_levels)
        template = vals[-1]['raw']
        if LEVEL_RE.search(template):
            template = LEVEL_RE.sub(f'levels={total}', template, count=1)
        rendered.append(indent_block(template, indent + '\t'))

    if not rendered:
        return ''
    return f"{indent}add_ownership={{\n" + '\n'.join(rendered) + f"\n{indent}}}"


def merge_building_blocks(blocks_raw):
    # Remove exact copies first; they are known integration duplicates and must not
    # increase levels.
    unique = []
    seen = set()
    for raw in blocks_raw:
        c = canonical(raw)
        if c in seen:
            continue
        seen.add(c)
        unique.append(raw)
    if len(unique) == 1:
        return unique[0]

    # Last block carries the last effective PM/reserves/other settings.
    base = unique[-1]
    all_entries = []
    for raw in unique:
        all_entries.extend(extract_ownership_entries(raw))
    ownership = build_ownership(all_entries, '\t\t\t\t')

    own_blocks = find_blocks(base, OWN_RE)
    if own_blocks:
        replacements = []
        for idx, (m, oo, oc) in enumerate(own_blocks):
            replacements.append((m.start(), oc + 1, ownership if idx == 0 else ''))
        base = replace_spans(base, replacements)
    elif ownership:
        # Insert after the building line if ownership was absent from the last block.
        bm = BUILDING_TYPE_RE.search(base)
        if bm:
            line_end = base.find('\n', bm.end())
            if line_end != -1:
                base = base[:line_end + 1] + ownership + '\n' + base[line_end + 1:]
    return base


def cleanup_region_body(body: str):
    bblocks = find_blocks(body, BUILD_RE)
    grouped = defaultdict(list)
    for bm, bo, bc in bblocks:
        raw = body[bm.start():bc + 1]
        tm = BUILDING_TYPE_RE.search(raw)
        btype = tm.group(1) if tm else '<missing>'
        grouped[btype].append((bm.start(), bc + 1, raw))

    replacements = []
    for btype, items in grouped.items():
        if len(items) <= 1:
            continue
        merged = merge_building_blocks([x[2] for x in items])
        first = items[0]
        replacements.append((first[0], first[1], merged))
        for item in items[1:]:
            replacements.append((item[0], item[1], ''))
    body = replace_spans(body, replacements)
    # Collapse source-comment spam left by former split blocks.
    body = re.sub(r'(?m)(^\s*# source:[^\n]+\n)(?:\s*\n|\s*# source:[^\n]+\n)+', r'\1', body)
    body = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', body)
    return body.strip('\n')


def cleanup_state(state_text: str, country_names):
    state_open = state_text.find('{')
    state_close = match_brace(state_text, state_open)
    body = state_text[state_open + 1:state_close]
    rblocks = find_blocks(body, REGION_RE)
    grouped = defaultdict(list)
    order = []
    for rm, ro, rc in rblocks:
        country = rm.group(1)
        if country not in grouped:
            order.append(country)
        grouped[country].append((rm, ro, rc))

    replacements = []
    for country in order:
        items = grouped[country]
        combined_parts = [body[ro + 1:rc] for _, ro, rc in items]
        combined = cleanup_region_body('\n'.join(combined_parts))
        name = country_names.get(country)
        label = f"# {name} ({country})" if name else f"# Country: {country}"
        new = f"\t\t{label}\n\t\tregion_state:{country}={{\n"
        if combined.strip():
            new += indent_block(combined, '\t\t\t') + '\n'
        new += "\t\t}"
        first_m, _, first_c = items[0]
        replacements.append((first_m.start(), first_c + 1, new))
        for rm, _, rc in items[1:]:
            replacements.append((rm.start(), rc + 1, ''))

    body = replace_spans(body, replacements)
    body = re.sub(r'\n[ \t]*\n(?:[ \t]*\n)+', '\n\n', body)
    return state_text[:state_open + 1] + body + state_text[state_close:]


def apply_xbb_admin(text: str):
    replacements = []
    for sm, so, sc in find_blocks(text, STATE_RE):
        state = sm.group(1)
        if state not in XBB_ADMIN_TARGET:
            continue
        state_body = text[so + 1:sc]
        for rm, ro, rc in find_blocks(state_body, REGION_RE):
            if rm.group(1) != 'XBB':
                continue
            region_body = state_body[ro + 1:rc]
            for bm, bo, bc in find_blocks(region_body, BUILD_RE):
                raw = region_body[bm.start():bc + 1]
                tm = BUILDING_TYPE_RE.search(raw)
                if not tm or tm.group(1) != 'building_government_administration':
                    continue
                target = XBB_ADMIN_TARGET[state]
                # Government administration is country-owned here. Replace every
                # ownership level in the merged block with the explicit state target.
                new_raw = LEVEL_RE.sub(f'levels={target}', raw)
                abs_start = so + 1 + ro + 1 + bm.start()
                abs_end = so + 1 + ro + 1 + bc + 1
                replacements.append((abs_start, abs_end, new_raw))
    return replace_spans(text, replacements)


def main():
    names = load_country_names()
    changed = []
    for path in sorted(BUILDING_DIR.glob('*.txt')):
        original = path.read_text(encoding='utf-8-sig')
        text = original
        state_blocks = find_blocks(text, STATE_RE)
        state_repls = []
        for sm, so, sc in state_blocks:
            raw = text[sm.start():sc + 1]
            cleaned = cleanup_state(raw, names)
            state_repls.append((sm.start(), sc + 1, cleaned))
        text = replace_spans(text, state_repls)
        text = apply_xbb_admin(text)
        if text != original:
            path.write_text(text, encoding='utf-8-sig')
            changed.append(path.name)
    print('Changed building files:', ', '.join(changed) if changed else 'none')
    print('XBB target total:', sum(XBB_ADMIN_TARGET.values()))


if __name__ == '__main__':
    main()
