"""opm_ai.linter.api - Public LinterAPI facade.

This module is the single integration point for callers (builder, chat tools,
future LangChain agent, tests). It hides the L1/v2 split, owns caching, and
dispatches sync and async lint work through a bounded thread pool.

The module-level `lint_deck()` and `default_api` instances are the canonical
entry points; everything else is implementation detail.
"""