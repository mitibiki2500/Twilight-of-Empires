from pathlib import Path
from collections import Counter
import re
ROOT=Path(__file__).resolve().parents[1]
CRASHROOT=ROOT/'gpt送信用/crashes'
crashes=sorted([p for p in CRASHROOT.iterdir() if p.is_dir()]) if CRASHROOT.exists() else []
latest=crashes[-1] if crashes else None
print('LATEST_CRASH', latest)
if not latest: raise SystemExit(2)
for name in ['exception.txt','logs/error.log','logs/game.log','logs/debug.log','logs/system.log']:
 p=latest/name
 print(name, p.exists(), p.stat().st_size if p.exists() else 0)
err=(latest/'logs/error.log').read_text(encoding='utf-8-sig',errors='replace').splitlines()
print('ERROR_LINES',len(err))
c=Counter()
for line in err:
 s=line.strip()
 if not s: continue
 s=re.sub(r'^\\[[^]]+\\]\\s*','',s)
 c[s]+=1
print('\\nTOP_EXACT')
for s,n in c.most_common(200): print(f'{n}\\t{s}')
print('\\nTAIL200')
for i,line in enumerate(err[-200:], max(1,len(err)-199)): print(f'{i}: {line}')
patterns=['Assertion failed','Failed to find country','Failed to scope to journal entry type','Harbor travel node','Cannot connect state adjacency','Invalid database object','Event not found','Modifier type definition','Script system error','Could not get leader','unset scope','Unknown trigger','Unexpected token','non-land','fortification','land reform']
for pat in patterns:
 hits=[(i+1,l) for i,l in enumerate(err) if pat.lower() in l.lower()]
 print(f'\\nMATCH {pat} COUNT {len(hits)}')
 for i,l in hits[:200]: print(f'{i}: {l}')
