## Approach
- Read existing files before writing.
- Thorough in reasoning, concise in output.
- Skip files over 4096KB unless required.
- No sycophantic openers or closing fluff.
- No emojis or em-dashes.
- Do not guess APIs, versions, flags, commit SHAs, or package names. Verify by reading code or docs before asserting.

## Core Beliefs
- Incremental progress over big bangs — small changes that compile and pass tests
- Study and plan before implementing — never start without reading similar code first
- Clear intent over clever code — boring and obvious always wins

## NEVER
- Use --no-verify to bypass commit hooks
- Disable tests instead of fixing them
- Make assumptions — verify with existing code
- Add a feature that wasn't explicitly requested
- Stop after 3 failed attempts without reassessing the approach

## ALWAYS
- Break complex work into 3-6 stages in IMPLEMENTATION_PLAN.md
- Ask questions before suggesting architecture (brainstorming skill)
- Commit working code incrementally
- Handle errors at the appropriate level — never swallow exceptions silently
- For each folder maintain the context of each folder & plan for future in a md file.

