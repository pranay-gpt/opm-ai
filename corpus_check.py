from opm_ai.linter import lint_deck_v2
from pathlib import Path

fixtures = list(Path('tests/fixtures').rglob('*.DATA'))
print(f'Total fixtures: {len(fixtures)}')

total_issues = 0
total_l171 = 0
total_l160 = 0
total_l202 = 0
total_l170 = 0
total_l221 = 0
clean = 0
errors = 0

for f in fixtures:
    try:
        result = lint_deck_v2(f)
        issues = result.issues
        total_issues += len(issues)
        l171 = sum(1 for i in issues if i.code == 171)
        l160 = sum(1 for i in issues if i.code == 160)
        l202 = sum(1 for i in issues if i.code == 202)
        l170 = sum(1 for i in issues if i.code == 170)
        l221 = sum(1 for i in issues if i.code == 221)
        total_l171 += l171
        total_l160 += l160
        total_l202 += l202
        total_l170 += l170
        total_l221 += l221
        if len(issues) == 0:
            clean += 1
    except Exception as e:
        errors += 1
        print(f'Error on {f}: {e}')

print(f'Total issues: {total_issues}')
print(f'Clean fixtures: {clean}')
print(f'L171 (unknown keyword): {total_l171}')
print(f'L160 (loose token): {total_l160}')
print(f'L202 (record length): {total_l202}')
print(f'L170 (wrong section): {total_l170}')
print(f'L221 (crossref warning): {total_l221}')
print(f'Errors: {errors}')