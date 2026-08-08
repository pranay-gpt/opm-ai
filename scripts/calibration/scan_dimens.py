"""Scan fixtures for DIMENS evidence (Phase 2.5 calibration)."""
import re
from pathlib import Path

DIMENS_RE = re.compile(r'^\s*DIMENS\b', re.MULTILINE | re.IGNORECASE)

FIXTURES = Path('../../../tests/fixtures').resolve()
all_files = sorted(FIXTURES.rglob('*.DATA'))
print(f"Scanning {len(all_files)} fixtures")

valid = 0
total = 0
out_of_range = []
issues = []
all_nx, all_ny, all_nz = [], [], []

for f in all_files:
    text = f.read_text(errors='replace')
    m = DIMENS_RE.search(text)
    if not m:
        continue
    total += 1
    start = m.end()

    same_line = text[m.start():text.find('\n', m.start())]
    nums_str = same_line.replace('DIMENS', '', 1).strip()
    items = nums_str.split() if nums_str else []

    if not items:
        for line in text[start:start+500].split('\n')[:3]:
            stripped = line.split('--')[0].strip()
            if not stripped or stripped.startswith('/'):
                continue
            items = stripped.split()
            break

    if len(items) < 3:
        issues.append((f, f"only {len(items)} items"))
        continue

    items = [x.rstrip('/').rstrip() for x in items]
    try:
        nx, ny, nz = int(items[0]), int(items[1]), int(items[2])
    except ValueError:
        issues.append((f, f"non-integer: {items[:3]}"))
        continue

    if not (1 <= nx <= 1000 and 1 <= ny <= 1000 and 1 <= nz <= 1000):
        out_of_range.append((f, f"{nx},{ny},{nz}"))
        continue

    valid += 1
    all_nx.append(nx); all_ny.append(ny); all_nz.append(nz)

print(f"\nDIMENS in {total} fixtures")
print(f"  Valid: {valid}")
print(f"  Out of range: {len(out_of_range)}")
print(f"  Parse issues: {len(issues)}")
if out_of_range:
    print("\nOut of range:")
    for f, msg in out_of_range[:10]:
        print(f"  {f.relative_to(FIXTURES)}: {msg}")
if issues:
    print("\nParse issues:")
    for f, msg in issues[:10]:
        print(f"  {f.relative_to(FIXTURES)}: {msg}")

if all_nx:
    print(f"\nObserved nx: [{min(all_nx)}, {max(all_nx)}]")
    print(f"Observed ny: [{min(all_ny)}, {max(all_ny)}]")
    print(f"Observed nz: [{min(all_nz)}, {max(all_nz)}]")