#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from collections import Counter
from pathlib import Path

import cleanup_buildings as c

# The v1 regexes used \s* at the beginning of line. In Python that can consume
# newlines, so replacement spans could start on the previous blank line and make
# comments visually attach to STATE lines. Restrict leading indentation to spaces/tabs.
c.STATE_RE = re.compile(r'(?m)^[ \t]*s:(STATE_[A-Za-z0-9_]+)[ \t]*=[ \t]*\{')
c.REGION_RE = re.compile(r'(?m)^[ \t]*region_state:([A-Za-z0-9_]+)[ \t]*=[ \t]*\{')
c.BUILD_RE = re.compile(r'(?m)^[ \t]*create_building[ \t]*=[ \t]*\{')
c.OWN_RE = re.compile(r'(?m)^[ \t]*add_ownership[ \t]*=[ \t]*\{')
c.OWN_ENTRY_RE = re.compile(r'(?m)^[ \t]*(country|building)[ \t]*=[ \t]*\{')

ROOT = Path(__file__).resolve().parents[1]
BUILDING_DIR = ROOT / 'common/history/buildings'
ROAD_BASELINE = 'aeae5de28ed0e89d0a1683d7c2f93b327710b365'  # pre-cleanup main parent
FUSHION_COUNTRIES = {'XBB', 'XBC'}
PM_RE = re.compile(r'activate_production_methods\s*=\s*\{([^}]*)\}', re.S)
STATE_LOC_RE = re.compile(r'(?m)^\s*(STATE_NSM_[A-Za-z0-9_]+):\d*\s+"([^"]+)"')


def load_state_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for p in ROOT.glob('localization/**/*.yml'):
        try:
            txt = p.read_text(encoding='utf-8-sig', errors='ignore')
        except OSError:
            continue
        for m in STATE_LOC_RE.finditer(txt):
            names.setdefault(m.group(1), m.group(2))
    return names


def git_show(ref: str, path: Path) -> str | None:
    rel = path.relative_to(ROOT).as_posix()
    cp = subprocess.run(
        ['git', 'show', f'{ref}:{rel}'],
        cwd=ROOT,
        text=True,
        encoding='utf-8-sig',
        errors='replace',
        capture_output=True,
        check=False,
    )
    return cp.stdout if cp.returncode == 0 else None


def iter_buildings(text: str):
    for sm, so, sc in c.find_blocks(text, c.STATE_RE):
        state = sm.group(1)
        state_body = text[so + 1:sc]
        for rm, ro, rc in c.find_blocks(state_body, c.REGION_RE):
            country = rm.group(1)
            region_body = state_body[ro + 1:rc]
            region_abs = so + 1 + ro + 1
            for bm, bo, bc in c.find_blocks(region_body, c.BUILD_RE):
                raw = region_body[bm.start():bc + 1]
                tm = c.BUILDING_TYPE_RE.search(raw)
                btype = tm.group(1) if tm else '<missing>'
                yield {
                    'state': state,
                    'country': country,
                    'building': btype,
                    'raw': raw,
                    'start': region_abs + bm.start(),
                    'end': region_abs + bc + 1,
                }


def road_keys(text: str) -> set[tuple[str, str, str]]:
    return {
        (b['state'], b['country'], b['building'])
        for b in iter_buildings(text)
        if 'pm_road_carts' in b['raw']
    }


def add_road_cart_to_block(raw: str) -> str:
    if 'pm_road_carts' in raw:
        return raw
    pm = PM_RE.search(raw)
    if pm:
        body = pm.group(1).rstrip()
        replacement = 'activate_production_methods={'+ body + ' "pm_road_carts" }'
        return raw[:pm.start()] + replacement + raw[pm.end():]

    # Historical road-enabled blocks normally already have a PM list. If a later
    # cleanup dropped the whole list, restore only the missing road PM, not an old
    # copy of the complete building block.
    close = raw.rfind('}')
    if close == -1:
        return raw
    first = raw.splitlines()[0]
    indent = first[:len(first) - len(first.lstrip(' \t'))]
    addition = f'\n{indent}\tactivate_production_methods={{ "pm_road_carts" }}\n{indent}'
    return raw[:close] + addition + raw[close:]


def restore_historical_roads(text: str, baseline: str | None) -> tuple[str, int]:
    if not baseline:
        return text, 0
    wanted = road_keys(baseline)
    replacements = []
    restored = 0
    for b in iter_buildings(text):
        key = (b['state'], b['country'], b['building'])
        if key not in wanted or 'pm_road_carts' in b['raw']:
            continue
        new = add_road_cart_to_block(b['raw'])
        if new != b['raw']:
            replacements.append((b['start'], b['end'], new))
            restored += 1
    return c.replace_spans(text, replacements), restored


def fushion_ownership_snapshot(text: str) -> Counter:
    out: Counter = Counter()
    for b in iter_buildings(text):
        if b['country'] not in FUSHION_COUNTRIES:
            continue
        for e in c.extract_ownership_entries(b['raw']):
            out[(
                b['state'], b['country'], b['building'], e['kind'], e['target'], e['levels']
            )] += 1
    return out


def add_state_name_comments(text: str, names: dict[str, str]) -> str:
    replacements = []
    for sm, so, sc in c.find_blocks(text, c.STATE_RE):
        state = sm.group(1)
        body = text[so + 1:sc]
        if re.search(r'(?m)^\s*#\s*州名\s*:', body):
            continue
        name = names.get(state, state)
        replacements.append((so + 1, so + 1, f'\n\t\t# 州名: {name} ({state})'))
    return c.replace_spans(text, replacements)


def code_without_comment(line: str) -> str:
    quote = False
    escaped = False
    out = []
    for ch in line:
        if quote:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                quote = False
            continue
        if ch == '"':
            quote = True
            out.append(ch)
            continue
        if ch == '#':
            break
        out.append(ch)
    return ''.join(out)


def brace_delta(line: str) -> int:
    code = code_without_comment(line)
    quote = False
    escaped = False
    delta = 0
    for ch in code:
        if quote:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                quote = False
            continue
        if ch == '"':
            quote = True
        elif ch == '{':
            delta += 1
        elif ch == '}':
            delta -= 1
    return delta


def normalize_indentation(text: str) -> str:
    lines = text.splitlines()
    out = []
    depth = 0
    for lineno, line in enumerate(lines, 1):
        stripped = line.lstrip(' \t')
        if not stripped:
            out.append('')
            continue

        code = code_without_comment(stripped).lstrip()
        leading_close = 0
        for ch in code:
            if ch == '}':
                leading_close += 1
            elif ch.isspace():
                continue
            else:
                break
        line_depth = max(depth - leading_close, 0)
        out.append('\t' * line_depth + stripped)
        depth += brace_delta(stripped)
        if depth < 0:
            raise ValueError(f'Negative brace depth at line {lineno}')
    if depth != 0:
        raise ValueError(f'Unbalanced braces after formatting: depth={depth}')
    return '\n'.join(out) + ('\n' if text.endswith('\n') else '')


def postprocess() -> None:
    names = load_state_names()
    total_roads = 0
    changed = []

    for path in sorted(BUILDING_DIR.glob('*.txt')):
        text = path.read_text(encoding='utf-8-sig')
        fushion_before = fushion_ownership_snapshot(text)
        baseline = git_show(ROAD_BASELINE, path)

        text, restored = restore_historical_roads(text, baseline)
        total_roads += restored
        text = add_state_name_comments(text, names)
        text = normalize_indentation(text)

        # Formatting/road restoration must never rewrite the user's present-day
        # Fushion/East-Fushion ownership. Road PM restoration is semantic only for PMs.
        fushion_after = fushion_ownership_snapshot(text)
        if fushion_before != fushion_after:
            missing = fushion_before - fushion_after
            added = fushion_after - fushion_before
            raise AssertionError(
                f'Fushion ownership changed in {path.name}: missing={missing} added={added}'
            )

        original = path.read_text(encoding='utf-8-sig')
        if text != original:
            path.write_text(text, encoding='utf-8-sig')
            changed.append(path.name)

    print('Readability-formatted building files:', ', '.join(changed) if changed else 'none')
    print('Historical pm_road_carts restored:', total_roads)


if __name__ == '__main__':
    # Preserve the existing duplicate/state/XBB administration cleanup first.
    c.main()
    # Then restore road-cart PMs that were lost by the old cleanup, add state-name
    # comments, normalize indentation, and verify Fushion ownership is unchanged.
    postprocess()
