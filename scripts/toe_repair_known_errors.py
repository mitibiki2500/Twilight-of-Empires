from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERROR_LOG = ROOT / "gpt送信用" / "logs" / "error.log"
VANILLA_COMMON = ROOT / "gpt送信用" / "common"
LIVE_COMMON = ROOT / "common"

SEPOY_BARS = {
    "sepoy_mutiny_progress_bar_bengal",
    "sepoy_mutiny_progress_bar_bombay",
    "sepoy_mutiny_progress_bar_madras",
}
MISSING_JES = {"je_cement_the_rightful_dynasty"}
MARKER = "# ToE 1.13 compatibility: disabled dangling reference: "


def strip_line_for_braces(line: str) -> str:
    out=[]; in_string=False; escaped=False
    for ch in line:
        if in_string:
            if escaped: escaped=False
            elif ch == "\\": escaped=True
            elif ch == '"': in_string=False
            out.append(" "); continue
        if ch == '"': in_string=True; out.append(" "); continue
        if ch == '#': break
        out.append(ch)
    return ''.join(out)


def brace_delta(line: str) -> int:
    s=strip_line_for_braces(line)
    return s.count('{')-s.count('}')


def check_balanced(text: str) -> tuple[bool,str]:
    depth=0
    for lineno,line in enumerate(text.splitlines(),1):
        depth += brace_delta(line)
        if depth < 0: return False,f"extra closing brace at line {lineno}"
    return (depth==0, "" if depth==0 else f"unclosed brace depth {depth}")


def is_comment(line: str) -> bool:
    return line.lstrip().startswith('#')


def target_regex(target: str) -> str:
    return rf"(?<![A-Za-z0-9_.-]){re.escape(target)}(?![A-Za-z0-9_.-])"


def parse_log_errors(log_text: str):
    entries=[]; current=None
    for line in log_text.splitlines():
        if 'Script system error!' in line:
            current={'error':'','location':''}; entries.append(current); continue
        if current is None: continue
        m=re.match(r'^\s*Error:\s*(.*)',line)
        if m: current['error']=m.group(1); continue
        m=re.match(r'^\s*Script location:\s*([^:]+(?:/[^:]+)*):\d+',line)
        if m:
            current['location']=m.group(1).replace('\\','/')
            current=None
    return [e for e in entries if e['error'] and e['location']]


def collect_missing_events(log_text: str) -> set[str]:
    return set(re.findall(r"Event not found! EventID:\s*([^\s\]]+)",log_text))


def ensure_logged_caller_files(entries) -> list[str]:
    """If an error comes from a vanilla common file absent in the mod, copy exact 1.13.11 source before sanitizing it."""
    copied=[]
    relevant_prefixes=('trigger_event effect','add_progress effect','add_journal_entry effect')
    for e in entries:
        if not e['error'].startswith(relevant_prefixes): continue
        loc=e['location']
        if not loc.startswith('common/'): continue
        rel=loc[len('common/'):]
        dst=LIVE_COMMON/rel
        if dst.exists(): continue
        src=VANILLA_COMMON/rel
        if not src.exists():
            raise RuntimeError(f"Logged caller is absent in MOD and vanilla mirror: {loc}")
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dst)
        copied.append(loc)
    return sorted(set(copied))


def iter_txt_files():
    if not LIVE_COMMON.exists(): return
    yield from (p for p in LIVE_COMMON.rglob('*.txt') if p.is_file())


def comment_range(lines:list[str],start:int,end:int,reason:str)->None:
    indent=re.match(r'^\s*',lines[start]).group(0)
    lines.insert(start,f"{indent}{MARKER}{reason}")
    end += 1
    for i in range(start+1,end+1):
        if lines[i].strip() and not is_comment(lines[i]):
            # Preserve original indentation after '# ' so nested blocks remain readable.
            lines[i]=indent+'# '+lines[i][len(indent):]


def find_assignment_block(lines:list[str],hit:int,assignment:str)->tuple[int,int]|None:
    pat=re.compile(rf'^\s*{re.escape(assignment)}\s*=\s*\{{')
    for start in range(hit,max(-1,hit-120),-1):
        if is_comment(lines[start]): continue
        if not pat.search(strip_line_for_braces(lines[start])): continue
        depth=0; opened=False
        for end in range(start,len(lines)):
            clean=strip_line_for_braces(lines[end])
            if '{' in clean: opened=True
            depth += clean.count('{')-clean.count('}')
            if opened and depth==0:
                return (start,end) if start<=hit<=end else None
    return None


def disable_direct(lines:list[str],assignment:str,targets:set[str],kind:str)->int:
    changed=0
    pat=re.compile(rf'^(\s*){re.escape(assignment)}\s*=\s*([A-Za-z0-9_.-]+)\s*(?:#.*)?$')
    i=0
    while i<len(lines):
        if is_comment(lines[i]): i+=1; continue
        m=pat.match(lines[i])
        if m and m.group(2) in targets:
            indent,target=m.group(1),m.group(2)
            lines.insert(i,f"{indent}{MARKER}{kind} {target}"); i+=1
            lines[i]=indent+'# '+lines[i][len(indent):]
            changed+=1
        i+=1
    return changed


def disable_inline_trigger_events(lines:list[str],targets:set[str])->int:
    """Remove compact `trigger_event = { id = X ... }` expressions while preserving the enclosing statement."""
    changed=0
    i=0
    # Compact event blocks in current vanilla scripts do not nest braces internally.
    pat=re.compile(r'trigger_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.-]+)(?:\s+[^{}]*)?\}')
    while i<len(lines):
        if is_comment(lines[i]): i+=1; continue
        line=lines[i]
        matches=list(pat.finditer(strip_line_for_braces(line)))
        if not matches: i+=1; continue
        # Replace from right to left using positions from the comment/string-stripped line (same character width for pre-comment portion).
        replaced=line
        hit_targets=[]
        for m in reversed(matches):
            target=m.group(1)
            if target not in targets: continue
            replaced=replaced[:m.start()]+replaced[m.end():]
            hit_targets.append(target)
        if hit_targets:
            suffix=';'.join(reversed(hit_targets))
            if replaced.strip():
                replaced=replaced.rstrip()+f"  {MARKER}{suffix}"
            else:
                indent=re.match(r'^\s*',line).group(0)
                replaced=f"{indent}{MARKER}{suffix}"
            lines[i]=replaced
            changed += len(hit_targets)
        i+=1
    return changed


def disable_blocks(lines:list[str],assignment:str,targets:set[str],kind:str)->int:
    changed=0; i=0
    while i<len(lines):
        if is_comment(lines[i]): i+=1; continue
        raw=strip_line_for_braces(lines[i])
        matched=next((t for t in targets if re.search(target_regex(t),raw)),None)
        if not matched: i+=1; continue
        block=find_assignment_block(lines,i,assignment)
        if not block: i+=1; continue
        start,end=block
        comment_range(lines,start,end,f"{kind} {matched}")
        changed+=1; i=end+2
    return changed


def has_live_assignment_ref(lines:list[str],idx:int,assignment:str,target:str)->bool:
    clean=strip_line_for_braces(lines[idx])
    if not re.search(target_regex(target),clean): return False
    # Direct or compact assignment on same line.
    if re.search(rf'\b{re.escape(assignment)}\s*=',clean): return True
    return find_assignment_block(lines,idx,assignment) is not None


def count_live_refs(targets:set[str],assignment:str):
    out=[]
    for p in iter_txt_files():
        lines=p.read_text(encoding='utf-8-sig',errors='strict').splitlines()
        for idx,line in enumerate(lines):
            if is_comment(line): continue
            for t in targets:
                if has_live_assignment_ref(lines,idx,assignment,t):
                    out.append((p.relative_to(ROOT).as_posix(),idx+1,t))
    return out


def main():
    log_text=ERROR_LOG.read_text(encoding='utf-8-sig',errors='replace')
    entries=parse_log_errors(log_text)
    missing_events=collect_missing_events(log_text)
    if not missing_events: raise RuntimeError('No missing event IDs found; refusing broad repair')

    copied=ensure_logged_caller_files(entries)
    changed_files=[]; event_fixes=progress_fixes=je_fixes=0

    for p in iter_txt_files():
        original=p.read_text(encoding='utf-8-sig',errors='strict')
        had_bom=p.read_bytes().startswith(b'\xef\xbb\xbf')
        lines=original.splitlines()
        n_event=disable_direct(lines,'trigger_event',missing_events,'missing event')
        n_event+=disable_inline_trigger_events(lines,missing_events)
        n_event+=disable_blocks(lines,'trigger_event',missing_events,'missing event')
        n_progress=disable_blocks(lines,'add_progress',SEPOY_BARS,'missing progress bar')
        n_je=disable_direct(lines,'add_journal_entry',MISSING_JES,'missing journal entry')
        n_je+=disable_blocks(lines,'add_journal_entry',MISSING_JES,'missing journal entry')
        if n_event or n_progress or n_je:
            new='\n'.join(lines)+('\n' if original.endswith('\n') else '')
            ok,msg=check_balanced(new)
            if not ok: raise RuntimeError(f"Brace validation failed after editing {p}: {msg}")
            p.write_text(new,encoding='utf-8-sig' if had_bom else 'utf-8')
            changed_files.append(p.relative_to(ROOT).as_posix())
            event_fixes+=n_event; progress_fixes+=n_progress; je_fixes+=n_je

    # Copied caller files with no recognized repair indicate parser coverage failure and are unsafe to commit.
    copied_rel={x for x in copied}
    changed_abs={'common/'+x[len('common/'):] if x.startswith('common/') else x for x in changed_files}
    unmodified_copies=[x for x in copied if x not in changed_abs]
    if unmodified_copies:
        raise RuntimeError(f"Copied vanilla callers but failed to sanitize them: {unmodified_copies}")

    bad=[]
    for p in iter_txt_files():
        ok,msg=check_balanced(p.read_text(encoding='utf-8-sig',errors='strict'))
        if not ok: bad.append((p.relative_to(ROOT).as_posix(),msg))
    if bad: raise RuntimeError(f"Structural validation failures: {bad[:20]}")

    left_events=count_live_refs(missing_events,'trigger_event')
    left_progress=count_live_refs(SEPOY_BARS,'add_progress')
    left_jes=count_live_refs(MISSING_JES,'add_journal_entry')

    print(f"Logged script errors: {len(entries)}")
    print(f"Missing event IDs: {len(missing_events)}")
    print(f"Copied exact vanilla 1.13.11 caller files: {len(copied)}")
    for x in copied: print('COPIED',x)
    print(f"Changed files: {len(changed_files)}")
    print(f"Disabled missing-event calls: {event_fixes}")
    print(f"Disabled invalid progress-bar calls: {progress_fixes}")
    print(f"Disabled invalid journal-entry calls: {je_fixes}")
    for x in changed_files: print('CHANGED',x)
    if left_events or left_progress or left_jes:
        print('LEFT_EVENT_REFS',left_events[:100])
        print('LEFT_PROGRESS_REFS',left_progress[:100])
        print('LEFT_JE_REFS',left_jes[:100])
        raise RuntimeError('Known dangling references remain after repair')
    if progress_fixes != 12:
        raise RuntimeError(f"Expected 12 sepoy progress fixes from log, got {progress_fixes}")
    if je_fixes != 3:
        raise RuntimeError(f"Expected 3 missing-JE fixes from log, got {je_fixes}")
    if event_fixes < 130:
        raise RuntimeError(f"Unexpectedly few missing-event fixes: {event_fixes}")
    print('KNOWN_REFERENCE_REPAIR_OK')

if __name__=='__main__':
    main()
