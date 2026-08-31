#!/usr/bin/env python3
from __future__ import annotations

from collections import Counter
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BDIR = ROOT / "common/history/buildings"
CREATE = re.compile(r'(?m)^([ \t]*)create_building\s*=\s*\{')
BTYPE = re.compile(r'\bbuilding\s*=\s*"([^"]+)"')

# These are the exact nested create_building sites reported from current main by
# tools/audit_building_structure.py on 2026-08-31.  Process bottom-to-top so
# moving a later block cannot invalidate an earlier line number.
TARGETS: dict[str, list[tuple[int, str, str]]] = {
    "00_NorthRia.txt": [
        (5094, "building_glassworks", "building_silk_plantation"),
    ],
    "01_SouthRia.txt": [
        (2035, "building_port", "building_silk_plantation"),
    ],
    "04_NorthAfrica.txt": [
        (537, "building_trade_center", "building_sugar_plantation"),
        (570, "building_cotton_plantation", "building_silk_plantation"),
        (847, "building_cotton_plantation", "building_silk_plantation"),
        (1284, "building_trade_center", "building_silk_plantation"),
        (1741, "building_cotton_plantation", "building_silk_plantation"),
        (2853, "building_trade_center", "building_silk_plantation"),
        (3964, "building_government_administration", "building_silk_plantation"),
        (4084, "building_livestock_ranch", "building_silk_plantation"),
        (4502, "building_wheat_farm", "building_silk_plantation"),
        (6168, "building_wheat_farm", "building_silk_plantation"),
    ],
    "05_SouthAfrica.txt": [
        (512, "building_cotton_plantation", "building_silk_plantation"),
        (707, "building_iron_mine", "building_silk_plantation"),
        (919, "building_tea_plantation", "building_silk_plantation"),
        (1053, "building_port", "building_silk_plantation"),
        (1167, "building_trade_center", "building_silk_plantation"),
        (1927, "building_wheat_farm", "building_silk_plantation"),
        (2952, "building_trade_center", "building_silk_plantation"),
        (3062, "building_banana_plantation", "building_silk_plantation"),
    ],
    "06_WestAsia.txt": [
        (4136, "building_iron_mine", "building_silk_plantation"),
        (6297, "building_furniture_manufactory", "building_silk_plantation"),
    ],
}


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
    raise RuntimeError(f"unclosed brace at offset {open_pos}")


def line_start(text: str, line_no: int) -> int:
    if line_no < 1:
        raise ValueError(line_no)
    pos = 0
    for _ in range(line_no - 1):
        pos = text.find('\n', pos)
        if pos < 0:
            raise RuntimeError(f"line {line_no} not found")
        pos += 1
    return pos


def create_at_line(text: str, line_no: int) -> re.Match[str]:
    pos = line_start(text, line_no)
    m = CREATE.match(text, pos)
    if not m:
        actual = text[pos:text.find('\n', pos)]
        raise RuntimeError(f"expected create_building at line {line_no}, got {actual!r}")
    return m


def create_block(text: str, m: re.Match[str]) -> tuple[int, int, str]:
    op = text.find('{', m.start(), m.end() + 2)
    cl = match_brace(text, op)
    return op, cl, text[m.start():cl + 1]


def building_type(block: str) -> str | None:
    m = BTYPE.search(block)
    return None if m is None else m.group(1)


def dedent_to(block: str, old_indent: str, new_indent: str) -> str:
    out: list[str] = []
    for line in block.splitlines(True):
        if line.startswith(old_indent):
            out.append(new_indent + line[len(old_indent):])
        else:
            out.append(line)
    return ''.join(out)


def normalize_extracted_building(block: str) -> str:
    # Several pasted silk plantations inherited the host building's PM line
    # (cotton/tea/iron/wheat/banana).  A silk plantation must use its own PM.
    if building_type(block) == "building_silk_plantation":
        block, n = re.subn(
            r'(?m)^([ \t]*)activate_production_methods\s*=\s*\{[^\n]*\}\s*$',
            r'\1activate_production_methods={ "default_building_silk_plantation" "pm_road_carts" }',
            block,
            count=1,
        )
        if n != 1:
            raise RuntimeError("silk plantation did not contain exactly one PM line")
    return block


def move_known_nested(text: str, line_no: int, expected_outer: str, expected_inner: str) -> str:
    outer = create_at_line(text, line_no)
    _, outer_close, outer_raw = create_block(text, outer)
    actual_outer = building_type(outer_raw)
    if actual_outer != expected_outer:
        raise RuntimeError(
            f"line {line_no}: expected outer {expected_outer}, got {actual_outer}"
        )

    nested = [m for m in CREATE.finditer(text, outer.start() + 1, outer_close) if m.start() < outer_close]
    if len(nested) != 1:
        raise RuntimeError(f"line {line_no}: expected exactly one nested create_building, got {len(nested)}")
    inner = nested[0]
    _, inner_close, inner_raw = create_block(text, inner)
    actual_inner = building_type(inner_raw)
    if actual_inner != expected_inner:
        raise RuntimeError(
            f"line {line_no}: expected inner {expected_inner}, got {actual_inner}"
        )

    inner_raw = dedent_to(inner_raw, inner.group(1), outer.group(1))
    inner_raw = normalize_extracted_building(inner_raw).rstrip()

    # Remove only the nested create_building block.  Keep all surrounding braces
    # and ownership data untouched; token fragments are repaired in a later pass.
    text = text[:inner.start()] + text[inner_close + 1:]

    # Re-find the same outer block at the same byte offset after removal.
    outer2 = CREATE.match(text, outer.start())
    if not outer2:
        raise RuntimeError(f"line {line_no}: outer create_building disappeared after extraction")
    _, outer_close2, _ = create_block(text, outer2)
    text = text[:outer_close2 + 1] + "\n\n" + inner_raw + text[outer_close2 + 1:]
    return text


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact match, found {count}")
    return text.replace(old, new, 1)


def repair_special_structure(files: dict[str, str]) -> None:
    # West Asia: duplicated add_ownership opener left the tooling workshop open,
    # causing all later state blocks to be parsed inside STATE_NSM_429.
    p = "06_WestAsia.txt"
    files[p] = replace_once(
        files[p],
        '\t\t\t\tadd_ownership={\n\t\t\t\tadd_ownership={\n',
        '\t\t\t\tadd_ownership={\n',
        "06_WestAsia duplicate add_ownership",
    )

    # Oceania: STATE_NSM_184 wheat farm closed the manor-house ownership but not
    # add_ownership, so reserves and every following state were swallowed by it.
    p = "09_Oceania.txt"
    files[p] = replace_once(
        files[p],
        '\t\t\t\t\t\tregion="STATE_NSM_184"\n\t\t\t\t}\n\t\t\t\treserves=1\n',
        '\t\t\t\t\t\tregion="STATE_NSM_184"\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\treserves=1\n',
        "09_Oceania missing add_ownership close",
    )

    # 1.13 building history requires ownership data; direct levels= is ignored.
    p = "08_CentralIslands.txt"
    old = (
        '\t\t\tcreate_building = {\n'
        '\t\t\t\tbuilding = "building_sugar_plantation"\n'
        '\t\t\t\tlevels = 5\n'
        '\t\t\t\tactivate_production_methods={ "default_building_sugar_plantation" "pm_road_carts" }\n'
        '\t\t\t}\n'
    )
    new = (
        '\t\t\tcreate_building = {\n'
        '\t\t\t\tbuilding = "building_sugar_plantation"\n'
        '\t\t\t\tadd_ownership={\n'
        '\t\t\t\t\tcountry={ country="c:GSU" levels=5 }\n'
        '\t\t\t\t}\n'
        '\t\t\t\treserves=1\n'
        '\t\t\t\tactivate_production_methods={ "default_building_sugar_plantation" "pm_road_carts" }\n'
        '\t\t\t}\n'
    )
    count = files[p].count(old)
    if count != 2:
        raise RuntimeError(f"08_CentralIslands direct levels blocks: expected 2, found {count}")
    files[p] = files[p].replace(old, new)


def repair_split_tokens(text: str) -> tuple[str, int]:
    total = 0
    patterns = [
        # glassworks: b + inserted block + uilding
        (r'(?m)^([ \t]*)b[ \t]*\n(?:[ \t]*\n)*[ \t]*uilding\s*=', r'\1building='),
        # iron mine ownership: lev + inserted block + els
        (r'(?m)^([ \t]*)lev[ \t]*\n(?:[ \t]*\n)*[ \t]*els\s*=', r'\1levels='),
        # tea/port PMs split by an inserted block
        (r'(?m)^([ \t]*)act[ \t]*\n(?:[ \t]*\n)*[ \t]*ivate_production_methods\s*=', r'\1activate_production_methods='),
        (r'(?m)^([ \t]*)a[ \t]*\n(?:[ \t]*\n)*[ \t]*ctivate_production_methods\s*=', r'\1activate_production_methods='),
        # wheat farm PM split as activate_pro / duction_methods
        (r'(?m)^([ \t]*)activate_pro[ \t]*\n(?:[ \t]*\n)*[ \t]*duction_methods\s*=', r'\1activate_production_methods='),
        # banana manor-house ownership split as ... c / ountry=...
        (r'(?m)(\bbuilding=\{[^\n]*?)[ \t]c[ \t]*\n(?:[ \t]*\n)*[ \t]*ountry\s*=', r'\1 country='),
    ]
    for pat, repl in patterns:
        text, n = re.subn(pat, repl, text)
        total += n
    return text, total


def counts_by_building(files: dict[str, str]) -> Counter[str]:
    c: Counter[str] = Counter()
    for text in files.values():
        c.update(BTYPE.findall(text))
    return c


def main() -> None:
    paths = sorted(BDIR.glob('*.txt'))
    files = {p.name: p.read_text(encoding='utf-8-sig') for p in paths}
    before_buildings = counts_by_building(files)

    # Repair the two malformed brace/opening cases first; they are intentionally
    # not handled as nested-building moves.
    repair_special_structure(files)

    moved = 0
    for filename, targets in TARGETS.items():
        text = files[filename]
        for line_no, outer, inner in sorted(targets, reverse=True):
            text = move_known_nested(text, line_no, outer, inner)
            moved += 1
        text, repaired = repair_split_tokens(text)
        files[filename] = text
        if repaired:
            print(filename, "split-token repairs:", repaired)

    # Run split repair once on every file so the exact known signatures cannot remain.
    split_total = 0
    for filename, text in list(files.items()):
        text, n = repair_split_tokens(text)
        split_total += n
        files[filename] = text

    after_buildings = counts_by_building(files)
    if before_buildings != after_buildings:
        raise RuntimeError(
            f"building-type inventory changed unexpectedly: before={before_buildings} after={after_buildings}"
        )

    changed = []
    for p in paths:
        new = files[p.name]
        old = p.read_text(encoding='utf-8-sig')
        if new != old:
            p.write_text(new, encoding='utf-8-sig', newline='\n')
            changed.append(p.name)

    print("moved nested buildings:", moved)
    print("additional split-token repairs:", split_total)
    print("changed files:", changed)
    if moved != 22:
        raise RuntimeError(f"expected 22 targeted nested moves, got {moved}")
    if set(changed) != {
        '00_NorthRia.txt', '01_SouthRia.txt', '04_NorthAfrica.txt',
        '05_SouthAfrica.txt', '06_WestAsia.txt', '08_CentralIslands.txt',
        '09_Oceania.txt'
    }:
        raise RuntimeError(f"unexpected changed-file set: {changed}")


if __name__ == '__main__':
    main()
