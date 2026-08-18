"""opm_ai.linter.api - Public LinterAPI facade.

Hides L1/v2 split. Owns cache + executor. Sync `lint()` and async
`lint_async()` converge on the same code path.

Cache key: (str(path), content_sha256, catalogue_version).
"""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Optional

from opm_ai.linter.cache import CacheStats, LinterCache
from opm_ai.linter.executor import (
    LinterError,
    LinterExecutor,
    LinterTimeoutError,
)
from opm_ai.linter.models import LintIssue, LintResult
from opm_ai.linter.v2.catalogue._version import catalogue_version

__all__ = [
    "CacheStats",
    "LinterAPI",
    "LinterError",
    "LinterTimeoutError",
    "LintIssue",
    "LintResult",
    "default_api",
    "lint_deck",
]


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class LinterAPI:
    def __init__(
        self,
        *,
        max_workers: int = 4,
        cache_size: int = 256,
        linter_timeout_s: float = 30.0,
    ) -> None:
        self._cache: LinterCache[LintResult] = LinterCache(max_size=cache_size)
        self._executor = LinterExecutor(
            max_workers=max_workers,
            timeout_s=linter_timeout_s,
        )

    def lint(
        self,
        source: str | Path,
        *,
        with_explanation: bool = False,
        incremental_of: Optional[Path] = None,
    ) -> LintResult:
        # Spec scope: file paths only. `incremental_of` accepted but
        # currently a no-op until v2 incremental diffing lands (future
        # sibling spec). `with_explanation` accepted but currently a
        # no-op until the explainer integration is decided.
        path = Path(source)
        if path.suffix.lower() != ".data":
            raise LinterError(
                f"unsupported source type: {path.suffix!r} (expected .DATA)"
            )
        sha = _sha256_of(path)
        cached = self._cache.get(path, self._cache_key(path, sha))
        if cached is not None:
            return cached

        # Cache miss: schedule work on the bounded pool. Even in the
        # single-call case this gives uniform timeout + future-proofing
        # for parallel callers (LangChain batch).
        def _run() -> LintResult:
            from opm_ai.linter.linter import lint_deck_combined
            return lint_deck_combined(path)

        result = self._executor.submit(_run)
        self._cache.put(path, self._cache_key(path, sha), result)
        return result

    async def lint_async(
        self,
        source: str | Path,
        *,
        with_explanation: bool = False,
        incremental_of: Optional[Path] = None,
    ) -> LintResult:
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.lint(source)
        )

    def invalidate_cache(self, source: Optional[Path] = None) -> None:
        self._cache.invalidate(source)

    def cache_stats(self) -> CacheStats:
        return self._cache.stats()

    @staticmethod
    def _cache_key(path: Path, sha: str) -> tuple[str, str, int]:
        # catalogue_version is folded into the key so any catalogue
        # regeneration self-invalidates the cache.
        return (str(path), sha, catalogue_version())


default_api = LinterAPI()


def lint_deck(path: Path) -> LintResult:
    """Module-level shortcut: equivalent to `default_api.lint(path)`."""
    return default_api.lint(path)
