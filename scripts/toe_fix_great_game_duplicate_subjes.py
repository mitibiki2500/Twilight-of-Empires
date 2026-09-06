from pathlib import Path
import re
p=Path('common/journal_entries/00_player_objectives_great_game.txt')
s=p.read_text(encoding='utf-8-sig')
jes=['je_toe_gg_steppe','je_toe_gg_sosilia','je_toe_gg_plains','je_toe_gg_route','je_toe_gg_tegar_ria','je_toe_gg_expel_tegar_ria','je_toe_gg_tortal','je_toe_gg_south_lefria']
count=0
for je in jes:
    pattern=rf'''if = \{{ limit = \{{ NOT = \{{ has_global_variable = ([^}}]+) \}} \}} add_journal_entry = \{{ type = {je} \}} \}}'''
    def repl(m):
        nonlocal_dummy=None
        return f'''if = {{
                limit = {{
                    NOT = {{ has_global_variable = {m.group(1)} }}
                    NOT = {{ has_journal_entry = {je} }}
                }}
                add_journal_entry = {{ type = {je} }}
            }}'''
    s,n=re.subn(pattern,repl,s)
    if n:
        count += n
if count != 28:
    raise SystemExit(f'Expected 28 Great Game subJE add guards, changed {count}')
# Structural brace check ignoring comments/quoted strings.
clean=re.sub(r'"(?:\\.|[^"\\])*"','""',s)
clean=re.sub(r'#.*','',clean)
d=0
for ch in clean:
    if ch=='{': d+=1
    elif ch=='}':
        d-=1
        if d<0: raise SystemExit('brace underflow')
if d: raise SystemExit(f'brace imbalance {d}')
p.write_text(s,encoding='utf-8-sig')
print('GREAT_GAME_DUPLICATE_SUBJE_GUARDS',count)
