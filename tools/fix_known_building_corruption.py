#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BDIR = ROOT / "common/history/buildings"

CREATE = re.compile(r'(?m)^([ \t]*)create_building\s*=\s*\{')
REGION = re.compile(r'(?m)^([ \t]*)region_state:([A-Za-z0-9_]+)\s*=\s*\{')
ADD_OWN = re.compile(r'(?m)^([ \t]*)add_ownership\s*=\s*\{')


def match_brace(text: str, open_pos: int) -> int:
    depth = 0
    in_string = False
    esc = False
    for i in range(open_pos, len(text)):
        c = text[i]
        if in_string:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"unclosed brace at {open_pos}")


def block_for_match(text: str, m: re.Match[str]) -> tuple[int, int]:
    op = text.find('{', m.start(), m.end() + 2)
    return op, match_brace(text, op)


def dedent_to(block: str, old_indent: str, new_indent: str) -> str:
    out = []
    for line in block.splitlines(True):
        if line.startswith(old_indent):
            out.append(new_indent + line[len(old_indent):])
        else:
            out.append(line)
    return ''.join(out)


def repair_split_tokens(text: str) -> tuple[str, int]:
    pats = [
        (r'(?m)^([ \t]*)lev[ \t]*\n[ \t]*els[ \t]*=', r'\1levels='),
        (r'(?m)^([ \t]*)c[ \t]*\n[ \t]*ountry[ \t]*=', r'\1country='),
        (r'(?m)^([ \t]*)b[ \t]*\n[ \t]*uilding[ \t]*=', r'\1building='),
        (r'(?m)^([ \t]*)a[ \t]*\n[ \t]*ctivate_production_methods[ \t]*=', r'\1activate_production_methods='),
    ]
    total = 0
    for pat, repl in pats:
        text, n = re.subn(pat, repl, text)
        total += n
    return text, total


def extract_nested_create_buildings(text: str) -> tuple[str, int]:
    moved = 0
    while True:
        matches = list(CREATE.finditer(text))
        blocks = []
        for m in matches:
            try:
                op, cl = block_for_match(text, m)
            except ValueError:
                continue
            blocks.append((m, op, cl))

        nested = None
        # Pick deepest/right-most nested block so indices remain predictable.
        for im, iop, icl in reversed(blocks):
            outers = [(om, oop, ocl) for om, oop, ocl in blocks if om.start() < im.start() < ocl]
            if outers:
                outer = min(outers, key=lambda b: b[2] - b[0].start())
                nested = (outer, (im, iop, icl))
                break
        if nested is None:
            break

        (om, oop, ocl), (im, iop, icl) = nested
        inner_start = im.start()
        inner_end = icl + 1
        inner = text[inner_start:inner_end]
        inner = dedent_to(inner, im.group(1), om.group(1))

        # Remove the misplaced inner block first.
        text = text[:inner_start] + text[inner_end:]
        text, _ = repair_split_tokens(text)

        # Recompute the outer block after removal and insert the extracted block as its sibling.
        om2 = next(m for m in CREATE.finditer(text) if m.start() == om.start())
        oop2, ocl2 = block_for_match(text, om2)
        insert_at = ocl2 + 1
        text = text[:insert_at] + "\n\n" + inner.rstrip() + text[insert_at:]
        moved += 1

    return text, moved


def containing_region_tag(text: str, pos: int) -> str | None:
    best = None
    for m in REGION.finditer(text):
        try:
            op, cl = block_for_match(text, m)
        except ValueError:
            continue
        if m.start() <= pos <= cl:
            if best is None or (cl - m.start()) < best[0]:
                best = (cl - m.start(), m.group(2))
    return None if best is None else best[1]


def direct_depth_one_levels(block: str) -> tuple[re.Match[str] | None, int | None]:
    # Find levels=N directly under create_building, not inside ownership subblocks.
    op = block.find('{')
    depth = 0
    in_string = False
    line_start = 0
    for i, c in enumerate(block):
        if c == '"':
            in_string = not in_string
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif c == '\n':
            line = block[line_start:i]
            if depth == 1:
                m = re.match(r'^([ \t]*)levels\s*=\s*(\d+)\s*$', line)
                if m:
                    return m, line_start
            line_start = i + 1
    return None, None


def convert_direct_levels(text: str) -> tuple[str, int]:
    converted = 0
    # Work right-to-left because replacements change offsets.
    blocks = []
    for m in CREATE.finditer(text):
        try:
            op, cl = block_for_match(text, m)
        except ValueError:
            continue
        blocks.append((m, cl))

    for m, cl in reversed(blocks):
        raw = text[m.start():cl + 1]
        if re.search(r'(?m)^\s*add_ownership\s*=', raw):
            continue
        lm, rel = direct_depth_one_levels(raw)
        if not lm:
            continue
        tag = containing_region_tag(text, m.start())
        if not tag:
            continue
        abs_start = m.start() + rel
        line_end = text.find('\n', abs_start)
        if line_end < 0:
            line_end = len(text)
        indent = lm.group(1)
        n = lm.group(2)
        repl = (
            f'{indent}add_ownership={{\n'
            f'{indent}\tcountry={{ country="c:{tag}" levels={n} }}\n'
            f'{indent}}}'
        )
        text = text[:abs_start] + repl + text[line_end:]
        converted += 1
    return text, converted


def move_invalid_ownership_payload(text: str) -> tuple[str, int]:
    moved = 0
    # If reserves/PM lines ended up inside add_ownership due a missing/misplaced brace,
    # move only those invalid payload lines immediately after the ownership block.
    while True:
        found = None
        for m in ADD_OWN.finditer(text):
            try:
                op, cl = block_for_match(text, m)
            except ValueError:
                continue
            raw = text[m.start():cl + 1]
            bad = list(re.finditer(r'(?m)^([ \t]*)(reserves\s*=.*|activate_production_methods\s*=.*)$', raw))
            if bad:
                found = (m, cl, bad)
                break
        if not found:
            break
        m, cl, bad = found
        raw = text[m.start():cl + 1]
        payload = []
        for bm in reversed(bad):
            payload.append(bm.group(2).strip())
            s, e = bm.start(), bm.end()
            raw = raw[:s] + raw[e:]
        payload.reverse()
        text = text[:m.start()] + raw + text[cl + 1:]
        # recompute ownership close after replacement
        m2 = next(x for x in ADD_OWN.finditer(text) if x.start() == m.start())
        op2, cl2 = block_for_match(text, m2)
        base_indent = m2.group(1)
        child_indent = base_indent
        insertion = ''.join(f'\n{child_indent}{p}' for p in payload)
        text = text[:cl2 + 1] + insertion + text[cl2 + 1:]
        moved += len(payload)
    return text, moved


def fix_file(path: Path) -> dict[str, int]:
    original = path.read_text(encoding='utf-8-sig')
    text = original
    text, n_nested = extract_nested_create_buildings(text)
    text, n_split = repair_split_tokens(text)
    text, n_direct = convert_direct_levels(text)
    text, n_payload = move_invalid_ownership_payload(text)
    text, n_split2 = repair_split_tokens(text)
    n_split += n_split2

    if text != original:
        path.write_text(text, encoding='utf-8-sig', newline='\n')
    return {
        'nested_blocks_moved': n_nested,
        'split_tokens_repaired': n_split,
        'direct_levels_converted': n_direct,
        'ownership_payload_moved': n_payload,
        'changed': int(text != original),
    }


def main() -> None:
    total = {'nested_blocks_moved':0,'split_tokens_repaired':0,'direct_levels_converted':0,'ownership_payload_moved':0,'changed':0}
    for path in sorted(BDIR.glob('*.txt')):
        stats = fix_file(path)
        if stats['changed']:
            print(path.name, stats)
        for k, v in stats.items():
            total[k] += v
    print('TOTAL', total)


if __name__ == '__main__':
    main()
