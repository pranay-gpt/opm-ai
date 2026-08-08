"""Scan fixtures for ENDSCALE evidence (Phase 2.5 calibration).

ENDSCALE schema (per OPM Flow Reference Manual):
- Item 1: scaling direction.
    Allowed: NODIR (default), DIR, REVERS, IRREV, PREV.
    Legacy: 0 = NODIR, 1 = DIR, 2 = full DIR, 3 = directional,
            4 = REVERS.
- Item 2: relative-perm threshold toggle.
    Allowed: NO (default), YES.
- Item 3: pcow threshold toggle.
    Allowed: NO (default), YES.

So ENDSCALE accepts either string tokens (modern) or integer
codes (legacy). My initial spec said all-int; that's wrong.
"""
import re
from pathlib import Path

ENDSCALE_RE = re.compile(r'^\s*ENDSCALE\b', re.MULTILINE | re.IGNORECASE)

FIXTURES = Path('../../../tests/fixtures').resolve()
all_files = sorted(FIXTURES.rglob('*.DATA'))
print(f"Scanning {len(all_files)} fixtures")

valid = 0
total = 0
issues = []
accepted = []  # (item1, item2, item3) tuples

ALLOWED_DIR = {'NODIR', 'DIR', 'REVERS', 'IRREV', 'PREV', '0', '1', '2', '3', '4'}
ALLOWED_TOGGLE = {'NO', 'YES', '0', '1'}

for f in all_files:
    text = f.read_text(errors='replace')
    m = ENDSCALE_RE.search(text)
    if not m:
        continue
    total += 1
    start = m.end()

    same_line = text[m.start():text.find('\n', m.start())]
    nums_str = same_line.replace('ENDSCALE', '', 1).strip()
    items = nums_str.split() if nums_str else []

    if not items:
        for line in text[start:start+500].split('\n')[:3]:
            stripped = line.split('--')[0].strip()
            if not stripped or stripped.startswith('/'):
                continue
            items = stripped.split()
            break

    items = [x.rstrip('/').rstrip().strip("'").strip('"').upper() for x in items]
    if not items:
        # bare ENDSCALE / is fine — defaults apply
        accepted.append(('(bare)', '', ''))
        valid += 1
        continue

    n = len(items)
    if n < 1 or n > 3:
        issues.append((f, f"wrong item count: {n} ({items})"))
        continue

    item1 = items[0]
    if item1 not in ALLOWED_DIR:
        issues.append((f, f"bad dir: {item1}"))
        continue

    item2 = items[1] if n >= 2 else 'NO'
    if item2 not in ALLOWED_TOGGLE:
        issues.append((f, f"bad toggle2: {item2}"))
        continue

    item3 = items[2] if n >= 3 else 'NO'
    if item3 not in ALLOWED_TOGGLE:
        issues.append((f, f"bad toggle3: {item3}"))
        continue

    accepted.append((item1, item2, item3))
    valid += 1

print(f"\nENDSCALE in {total} fixtures")
print(f"  Valid: {valid}")
print(f"  Issues: {len(issues)}")
if issues:
    print("Issues:")
    for f, msg in issues[:10]:
        print(f"  {f.relative_to(FIXTURES)}: {msg}")

from collections import Counter
print("\nObserved (item1, item2, item3) tuples (top 15):")
for tup, n in Counter(accepted).most_common(15):
    print(f"  {n:4} {tup}")