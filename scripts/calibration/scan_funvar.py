"""Verify FUNVAR evidence: every FU_* token must appear in a FUNVAR
record in the same deck."""
import re
from pathlib import Path

FUNVAR_RE = re.compile(r'^\s*FUNVAR\b', re.MULTILINE | re.IGNORECASE)
FU_RE = re.compile(r'\b(FU_[A-Z][A-Z0-9_]*)\b')
WU_RE = re.compile(r'\b(WU_[A-Z][A-Z0-9_]*)\b')

FIXTURES = Path('../../../tests/fixtures').resolve()
all_files = sorted(FIXTURES.rglob('*.DATA'))

valid = 0
total_fu = 0  # fixtures that use FU_*
total_wu = 0
unmatched_fu = []
unmatched_wu = []

for f in all_files:
    text = f.read_text(errors='replace')
    fu_tokens = set(FU_RE.findall(text))
    wu_tokens = set(WU_RE.findall(text))

    # FUNVAR declarations: collect FU_ tokens on FUNVAR lines
    funvar_tokens = set()
    for m in FUNVAR_RE.finditer(text):
        # Same line
        line_end = text.find('\n', m.start())
        same = text[m.start():line_end if line_end >= 0 else len(text)]
        funvar_tokens.update(FU_RE.findall(same))
        # Following lines (FUNVAR can span lines)
        # Look at the next few lines
        block = text[m.start():m.start()+500]
        # Stop at '/' terminator
        if '/' in block:
            block = block.split('/', 1)[0]
        funvar_tokens.update(FU_RE.findall(block))

    if fu_tokens:
        total_fu += 1
        missing = fu_tokens - funvar_tokens
        if missing:
            unmatched_fu.append((f, missing, funvar_tokens))

    if wu_tokens:
        total_wu += 1
        missing_wu = wu_tokens - funvar_tokens
        # WU_* declarations go in WU_*, not FUNVAR — separate concept.
        # Skip WU check for this calibration pass.
        # if missing_wu:
        #     unmatched_wu.append((f, missing_wu))

print(f"Fixtures with FU_*: {total_fu}")
print(f"Fixtures with WU_*: {total_wu}")
print()
if unmatched_fu:
    print(f"Fixtures where FU_* used but NOT declared in FUNVAR ({len(unmatched_fu)}):")
    for f, missing, declared in unmatched_fu[:15]:
        print(f"  {f.relative_to(FIXTURES)}: missing={missing}, declared={declared}")
else:
    print("All FU_* tokens are declared in FUNVAR. FUNVAR calibration passes.")
print()
print(f"Fixtures with WU_* tokens but no WUVAR declaration:")
wu_no_decl = []
for f in all_files:
    text = f.read_text(errors='replace')
    wu_tokens = set(WU_RE.findall(text))
    if not wu_tokens:
        continue
    # Find WUVAR or WU_VARIABLE declarations
    if not re.search(r'^\s*WUVAR\b|^\s*WU_VARIABLE\b|^\s*WUVARS\b', text, re.MULTILINE | re.IGNORECASE):
        wu_no_decl.append((f, wu_tokens))

if wu_no_decl:
    print(f"  {len(wu_no_decl)} fixtures")
    for f, toks in wu_no_decl[:5]:
        print(f"  {f.relative_to(FIXTURES)}: {toks}")
else:
    print("  0")