from __future__ import annotations

import re
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE_COMMON = ROOT / "common"
VANILLA_COMMON = ROOT / "gpt送信用" / "common"


def strip_comments(line: str) -> str:
    out = []
    in_string = False
    escaped = False
    for ch in line:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            out.append(' ')
            continue
        if ch == '"':
            in_string = True
            out.append(' ')
            continue
        if ch == '#':
            break
        out.append(ch)
    return ''.join(out)


def top_blocks(text: str):
    lines = text.splitlines()
    depth = 0
    start = None
    name = None
    for i, line in enumerate(lines):
        clean = strip_comments(line)
        if depth == 0:
            m = re.match(r'^\s*([^\s={}]+)\s*=\s*\{', clean)
            if m:
                start = i
                name = m.group(1)
        depth += clean.count('{') - clean.count('}')
        if start is not None and depth == 0:
            yield name, lines[start:i + 1]
            start = None
            name = None
    if depth != 0:
        raise RuntimeError(f"Unbalanced braces: depth={depth}")


def ensure_default_character_template() -> bool:
    rel = Path('character_templates/00_default_template.txt')
    src = VANILLA_COMMON / rel
    dst = LIVE_COMMON / rel
    if not src.exists():
        raise RuntimeError(f"Vanilla 1.13.11 mirror missing required template: {src}")
    src_bytes = src.read_bytes()
    if dst.exists() and dst.read_bytes() == src_bytes:
        changed = False
        print('DEFAULT_TEMPLATE already exact vanilla mirror')
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        if dst.read_bytes() != src_bytes:
            raise RuntimeError('Default template copy verification failed')
        changed = True
        print('DEFAULT_TEMPLATE restored from exact vanilla mirror')
    text = dst.read_text(encoding='utf-8-sig', errors='strict')
    blocks = list(top_blocks(text))
    defaults = [b for b in blocks if b[0] == 'default']
    if len(defaults) != 1:
        raise RuntimeError(f"Expected exactly one default character template, got {len(defaults)}")
    required = {
        'first_name', 'last_name', 'historical', 'religion', 'culture', 'female',
        'home_region', 'holding_type', 'dna', 'age', 'interest_group',
        'commander_rank', 'trait_generation'
    }
    clean_block = '\n'.join(strip_comments(line) for line in defaults[0][1])
    missing = sorted(k for k in required if not re.search(rf'\b{re.escape(k)}\s*=', clean_block))
    if missing:
        raise RuntimeError(f"Default character template missing required fields: {missing}")
    print('DEFAULT_TEMPLATE_COMPLETE_OK')
    return changed


def fix_prestige_goods() -> bool:
    p = LIVE_COMMON / 'prestige_goods/00_prestige_goods.txt'
    raw = p.read_text(encoding='utf-8-sig', errors='strict')
    had_bom = p.read_bytes().startswith(b'\xef\xbb\xbf')
    replacements = {
        'base_good = opium # ToE: 無効化済み定義をautomobiles上限から退避':
            'base_good = explosives # ToE: 無効化済み定義をPrestige Goods上限衝突のないgoodsへ退避',
        'base_good = opium # ToE: 無効化済み定義をwine上限から退避':
            'base_good = fertilizer # ToE: 無効化済み定義をPrestige Goods上限衝突のないgoodsへ退避',
    }
    new = raw
    hits = 0
    for old, repl in replacements.items():
        n = new.count(old)
        if n > 1:
            raise RuntimeError(f"Unexpected duplicate prestige repair marker: {old} x{n}")
        if n == 1:
            new = new.replace(old, repl)
            hits += 1
    if new != raw:
        p.write_text(new, encoding='utf-8-sig' if had_bom else 'utf-8')
        print(f'PRESTIGE_GOODS repaired markers={hits}')
    else:
        print('PRESTIGE_GOODS target lines already repaired')

    counts = defaultdict(list)
    for fp in sorted((LIVE_COMMON / 'prestige_goods').glob('*.txt')):
        text = fp.read_text(encoding='utf-8-sig', errors='strict')
        for name, block in top_blocks(text):
            base = None
            for line in block:
                m = re.search(r'\bbase_good\s*=\s*([A-Za-z0-9_]+)', strip_comments(line))
                if m:
                    base = m.group(1)
                    break
            if base:
                counts[base].append((name, fp.name))
    bad = {good: defs for good, defs in counts.items() if len(defs) > 3}
    for good, defs in sorted(counts.items()):
        print('PRESTIGE_COUNT', good, len(defs), defs)
    if bad:
        raise RuntimeError(f"Prestige Goods still exceed hard cap 3: {bad}")
    print('PRESTIGE_GOODS_CAP_OK')
    return new != raw


def main():
    changed_default = ensure_default_character_template()
    changed_prestige = fix_prestige_goods()
    print('CHANGED_DEFAULT_TEMPLATE', changed_default)
    print('CHANGED_PRESTIGE_GOODS', changed_prestige)
    print('REMAINING_ASSERTION_SOURCE_FIX_OK')


if __name__ == '__main__':
    main()
