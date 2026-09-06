from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERROR_LOG = ROOT / "gpt送信用" / "logs" / "error.log"

# Only live script areas are edited. Reference material under gpt送信用 is never modified.
SCAN_ROOTS = [ROOT / "common"]

SEPoy_BARS = {
    "sepoy_mutiny_progress_bar_bengal",
    "sepoy_mutiny_progress_bar_bombay",
    "sepoy_mutiny_progress_bar_madras",
}
MISSING_JES = {"je_cement_the_rightful_dynasty"}

MARKER = "# ToE 1.13 compatibility: disabled dangling reference: "


def strip_line_for_braces(line: str) -> str:
    out = []
    in_string = False
    escaped = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            out.append(" ")
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(" ")
            i += 1
            continue
        if ch == "#":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def brace_delta(line: str) -> int:
    s = strip_line_for_braces(line)
    return s.count("{") - s.count("}")


def check_balanced(text: str) -> tuple[bool, str]:
    depth = 0
    for lineno, line in enumerate(text.splitlines(), 1):
        depth += brace_delta(line)
        if depth < 0:
            return False, f"extra closing brace at line {lineno}"
    if depth:
        return False, f"unclosed brace depth {depth}"
    return True, ""


def is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def comment_range(lines: list[str], start: int, end: int, reason: str) -> None:
    indent = re.match(r"^\s*", lines[start]).group(0)
    lines.insert(start, f"{indent}{MARKER}{reason}")
    end += 1
    for i in range(start + 1, end + 1):
        if lines[i].strip() and not lines[i].lstrip().startswith("#"):
            lines[i] = indent + "# " + lines[i][len(indent):]


def find_assignment_block(lines: list[str], hit: int, assignment: str) -> tuple[int, int] | None:
    """Find nearest enclosing `assignment = { ... }` block that contains hit."""
    pat = re.compile(rf"^\s*{re.escape(assignment)}\s*=\s*\{{")
    for start in range(hit, max(-1, hit - 80), -1):
        if is_comment(lines[start]):
            continue
        if not pat.search(strip_line_for_braces(lines[start])):
            continue
        depth = 0
        opened = False
        for end in range(start, len(lines)):
            clean = strip_line_for_braces(lines[end])
            if "{" in clean:
                opened = True
            depth += clean.count("{") - clean.count("}")
            if opened and depth == 0:
                if start <= hit <= end:
                    return start, end
                break
    return None


def disable_direct_assignments(lines: list[str], assignment: str, targets: set[str], kind: str) -> int:
    changed = 0
    # Direct syntax: assignment = namespace.id
    pat = re.compile(rf"^(\s*){re.escape(assignment)}\s*=\s*([A-Za-z0-9_.-]+)\s*(?:#.*)?$")
    i = 0
    while i < len(lines):
        if is_comment(lines[i]):
            i += 1
            continue
        m = pat.match(lines[i])
        if m and m.group(2) in targets:
            indent = m.group(1)
            target = m.group(2)
            lines.insert(i, f"{indent}{MARKER}{kind} {target}")
            i += 1
            lines[i] = indent + "# " + lines[i][len(indent):]
            changed += 1
        i += 1
    return changed


def disable_block_assignments(lines: list[str], assignment: str, targets: set[str], kind: str) -> int:
    changed = 0
    i = 0
    while i < len(lines):
        if is_comment(lines[i]):
            i += 1
            continue
        raw = strip_line_for_braces(lines[i])
        if not any(t in raw for t in targets):
            i += 1
            continue
        # The target can be on an id/progress_bar/type line within a block.
        matched = next((t for t in targets if re.search(rf"(?<![A-Za-z0-9_.-]){re.escape(t)}(?![A-Za-z0-9_.-])", raw)), None)
        if not matched:
            i += 1
            continue
        block = find_assignment_block(lines, i, assignment)
        if not block:
            i += 1
            continue
        start, end = block
        comment_range(lines, start, end, f"{kind} {matched}")
        changed += 1
        i = end + 2
    return changed


def collect_missing_events(log_text: str) -> set[str]:
    return set(re.findall(r"Event not found! EventID:\s*([^\s\]]+)", log_text))


def iter_txt_files():
    for base in SCAN_ROOTS:
        if not base.exists():
            continue
        for p in base.rglob("*.txt"):
            if p.is_file():
                yield p


def count_live_target_refs(targets: set[str], assignment: str) -> list[tuple[str, int, str]]:
    leftovers = []
    for p in iter_txt_files():
        text = p.read_text(encoding="utf-8-sig", errors="strict")
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if is_comment(line):
                continue
            clean = strip_line_for_braces(line)
            for t in targets:
                if t in clean:
                    # Only report if within/at the requested assignment, not unrelated localization/comment strings.
                    idx = i - 1
                    if re.search(rf"\b{re.escape(assignment)}\s*=", clean) or find_assignment_block(lines, idx, assignment):
                        leftovers.append((p.relative_to(ROOT).as_posix(), i, t))
    return leftovers


def main() -> None:
    if not ERROR_LOG.exists():
        raise SystemExit(f"Missing log: {ERROR_LOG}")
    log_text = ERROR_LOG.read_text(encoding="utf-8-sig", errors="replace")
    missing_events = collect_missing_events(log_text)
    if not missing_events:
        raise SystemExit("No missing event IDs found in latest error.log; refusing broad repair.")

    changed_files: list[str] = []
    event_fixes = progress_fixes = je_fixes = 0

    for p in iter_txt_files():
        original = p.read_text(encoding="utf-8-sig", errors="strict")
        had_bom = p.read_bytes().startswith(b"\xef\xbb\xbf")
        lines = original.splitlines()

        before = len(lines)
        n_event = disable_direct_assignments(lines, "trigger_event", missing_events, "missing event")
        n_event += disable_block_assignments(lines, "trigger_event", missing_events, "missing event")
        n_progress = disable_block_assignments(lines, "add_progress", SEPoy_BARS, "missing progress bar")
        n_je = disable_direct_assignments(lines, "add_journal_entry", MISSING_JES, "missing journal entry")
        n_je += disable_block_assignments(lines, "add_journal_entry", MISSING_JES, "missing journal entry")

        if n_event or n_progress or n_je:
            new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
            ok, msg = check_balanced(new_text)
            if not ok:
                raise RuntimeError(f"Brace validation failed after editing {p}: {msg}")
            p.write_text(new_text, encoding="utf-8-sig" if had_bom else "utf-8")
            changed_files.append(p.relative_to(ROOT).as_posix())
            event_fixes += n_event
            progress_fixes += n_progress
            je_fixes += n_je

    # Whole live common structural check after all edits.
    bad = []
    for p in iter_txt_files():
        text = p.read_text(encoding="utf-8-sig", errors="strict")
        ok, msg = check_balanced(text)
        if not ok:
            bad.append((p.relative_to(ROOT).as_posix(), msg))
    if bad:
        raise RuntimeError(f"Structural validation failures: {bad[:20]}")

    # Verify that the exact error classes we repaired have no remaining live call sites.
    left_events = count_live_target_refs(missing_events, "trigger_event")
    left_progress = count_live_target_refs(SEPoy_BARS, "add_progress")
    left_jes = count_live_target_refs(MISSING_JES, "add_journal_entry")

    print(f"Missing event IDs from latest log: {len(missing_events)}")
    print(f"Changed files: {len(changed_files)}")
    print(f"Disabled missing-event calls: {event_fixes}")
    print(f"Disabled invalid progress-bar calls: {progress_fixes}")
    print(f"Disabled invalid journal-entry calls: {je_fixes}")
    for f in changed_files:
        print("CHANGED", f)

    if left_events or left_progress or left_jes:
        print("LEFT_EVENT_REFS", left_events[:100])
        print("LEFT_PROGRESS_REFS", left_progress[:100])
        print("LEFT_JE_REFS", left_jes[:100])
        raise RuntimeError("Known dangling references remain after repair")

    if event_fixes == 0:
        raise RuntimeError("Repair found no live missing-event calls; unexpected relative to audit")

    print("KNOWN_REFERENCE_REPAIR_OK")


if __name__ == "__main__":
    main()
