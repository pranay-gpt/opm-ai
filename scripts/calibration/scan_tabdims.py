"""Verify TABDIMS range evidence with proper multi-line parsing."""
import re
from pathlib import Path

TABDIMS_RE = re.compile(r'^\s*TABDIMS\b', re.MULTILINE | re.IGNORECASE)

FIXTURES = Path('../../../tests/fixtures').resolve()
all_files = sorted(FIXTURES.rglob('*.DATA'))

DEFAULTS = [0,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]

def expand_skip(items):
    out = []
    for x in items:
        if x.endswith('*') and x[:-1].isdigit():
            n = int(x[:-1])
            for i in range(n):
                out.append(None)
        else:
            out.append(x)
    return out

def parse_tabdims_record(text, start):
    """Parse TABDIMS record starting at `start`. Returns (items, end_pos)."""
    # Skip the header line
    pos = text.find('\n', start)
    if pos < 0:
        return [], start
    pos += 1
    items = []
    while pos < len(text):
        line_end = text.find('\n', pos)
        if line_end < 0:
            line_end = len(text)
        line = text[pos:line_end]
        # Strip comment
        no_comment = line.split('--', 1)[0]
        # Strip terminator
        if '/' in no_comment:
            no_comment = no_comment.split('/', 1)[0]
        toks = no_comment.split()
        items.extend(toks)
        if '/' in line:
            return items, line_end
        pos = line_end + 1
    return items, pos

valid = 0
total = 0
unparseable = []
non_int_after_expand = []

for f in all_files:
    text = f.read_text(errors='replace')
    m = TABDIMS_RE.search(text)
    if not m:
        continue
    total += 1
    raw_items, _ = parse_tabdims_record(text, m.end())

    items = expand_skip(raw_items)
    if len(items) > 24:
        unparseable.append((f, f"expanded > 24: {len(items)} ({raw_items[:5]}...)"))
        continue

    items_full = items + [None] * (24 - len(items))

    int_items = []
    bad = False
    for i, x in enumerate(items_full):
        if x is None:
            int_items.append(DEFAULTS[i])
            continue
        if x == '':
            int_items.append(DEFAULTS[i])
            continue
        try:
            int_items.append(int(x))
        except ValueError:
            non_int_after_expand.append((f, f"item {i+1}: {x!r} (raw: {raw_items[:10]})"))
            bad = True
            break
    if not bad:
        valid += 1

print(f"TABDIMS in {total} fixtures (with skip-syntax + multi-line)")
print(f"  Valid: {valid}")
print(f"  Unparseable (>24 after expand): {len(unparseable)}")
print(f"  Non-integer after expand: {len(non_int_after_expand)}")
if unparseable:
    for f, msg in unparseable[:5]:
        print(f"  TOO MANY {f.relative_to(FIXTURES)}: {msg}")
if non_int_after_expand:
    for f, msg in non_int_after_expand[:5]:
        print(f"  NON-INT {f.relative_to(FIXTURES)}: {msg}")