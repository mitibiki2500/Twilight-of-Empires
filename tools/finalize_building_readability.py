#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BDIR = ROOT / 'common/history/buildings'
COUNTRY_COMMENT = re.compile(r'^([ \t]*)#\s*(?:Country:\s*[A-Za-z0-9_]+|.*\([A-Z0-9]{3}\))\s*$')


def strip_comments_and_space(text: str) -> str:
    out = []
    for line in text.splitlines():
        quote = False
        escaped = False
        buf = []
        for ch in line:
            if quote:
                buf.append(ch)
                if escaped:
                    escaped = False
                elif ch == '\\':
                    escaped = True
                elif ch == '"':
                    quote = False
                continue
            if ch == '"':
                quote = True
                buf.append(ch)
            elif ch == '#':
                break
            else:
                buf.append(ch)
        out.append(''.join(buf))
    return re.sub(r'\s+', '', '\n'.join(out))


def current_main(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    cp = subprocess.run(
        ['git', 'show', f'origin/main:{rel}'], cwd=ROOT,
        capture_output=True, text=True, encoding='utf-8-sig', errors='replace'
    )
    if cp.returncode:
        raise RuntimeError(cp.stderr)
    return cp.stdout


def dedupe_country_comments(text: str) -> str:
    lines = text.splitlines()
    out = []
    for line in lines:
        if out and COUNTRY_COMMENT.match(line) and COUNTRY_COMMENT.match(out[-1]):
            # If cleanup inserted the same normalized country label next to an old
            # identical label, keep one. Do not touch distinct labels.
            if line.strip() == out[-1].strip():
                continue
        out.append(line)
    return '\n'.join(out) + ('\n' if text.endswith('\n') else '')


def main() -> None:
    changed = []
    for path in sorted(BDIR.glob('*.txt')):
        before_main = current_main(path)
        text = path.read_text(encoding='utf-8-sig')
        text = dedupe_country_comments(text)

        # This pass is requested as readability-only. No ownership, level,
        # production method, reserve, building type, state or country semantics
        # may change compared with the current main baseline.
        if strip_comments_and_space(before_main) != strip_comments_and_space(text):
            raise AssertionError(f'Semantic building-history change detected: {path.name}')

        original = path.read_text(encoding='utf-8-sig')
        if text != original:
            path.write_text(text, encoding='utf-8-sig')
            changed.append(path.name)
    print('Deduplicated country comments:', ', '.join(changed) if changed else 'none')
    print('Semantic comparison with current main: PASS (all building files)')


if __name__ == '__main__':
    main()
