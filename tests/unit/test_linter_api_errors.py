"""LinterAPI error taxonomy tests."""
import asyncio
from pathlib import Path

import pytest

from opm_ai.linter.api import LinterAPI, LinterError, LinterTimeoutError


def test_missing_source_raises_file_not_found(tmp_path: Path):
    api = LinterAPI()
    with pytest.raises(FileNotFoundError):
        api.lint(tmp_path / "does_not_exist.DATA")


def test_non_data_extension_raises_linter_error(tmp_path: Path):
    p = tmp_path / "wrong.txt"
    p.write_text("not a deck", encoding="utf-8")
    api = LinterAPI()
    with pytest.raises(LinterError, match="unsupported source type"):
        api.lint(p)


def test_string_source_path_is_accepted(tmp_path: Path):
    p = tmp_path / "x.DATA"
    p.write_text("RUNSPEC\nEND\n", encoding="utf-8")
    api = LinterAPI()
    # No exception; just confirm we didn't crash.
    api.lint(str(p))


# ---------------------------------------------------------------------------
# Fuzz / boundary tests for the LinterAPI facade (Task 13).
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "linter_api"


def test_binary_file_raises_linter_error_or_file_not_found(tmp_path: Path):
    """Linting a binary file (e.g. PNG header with .png extension) must raise.

    Per the spec: must raise `LinterError` (or `FileNotFoundError` if the
    extension isn't .DATA/.INC). PNG is not a valid deck extension so the
    facade's extension guard raises `LinterError` immediately.
    """
    p = tmp_path / "fake.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    api = LinterAPI()
    with pytest.raises((LinterError, FileNotFoundError)):
        api.lint(p)


def test_binary_content_with_data_extension_does_not_silently_succeed(tmp_path: Path):
    """A binary blob with .DATA extension must NOT silently pass.

    The facade has no content sniffer; the underlying linter is responsible
    for surfacing this as parse errors. We assert the result is non-passing,
    i.e. it didn't pretend the binary was a valid deck.
    """
    p = tmp_path / "fake.DATA"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    api = LinterAPI()
    result = api.lint(p)
    # The linter must surface the unparseable content.
    if result.passed:
        # A passing result on a PNG blob is a bug.
        pytest.fail(
            "Linter silently passed binary PNG content as a clean deck"
        )


def test_empty_data_file_does_not_crash(tmp_path: Path):
    """An empty .DATA file must not crash; should return a LintResult."""
    p = tmp_path / "empty.DATA"
    p.write_text("", encoding="utf-8")
    api = LinterAPI()
    # Must not raise; accept any returned LintResult (may include
    # parse warnings, but the call itself must complete).
    result = api.lint(p)
    assert result is not None
    assert hasattr(result, "issues")
    assert hasattr(result, "passed")


def test_repeated_lint_is_stable_and_idempotent():
    """Linting the same clean fixture 100 times must not leak or raise."""
    path = FIXTURE_DIR / "clean.DATA"
    api = LinterAPI()
    api.invalidate_cache()

    first = api.lint(path)
    for _ in range(100):
        result = api.lint(path)
        # Each call must return an equivalent LintResult.
        assert result is not None
        assert result.deck_path == first.deck_path
        assert result.passed == first.passed
        assert len(result.issues) == len(first.issues)


def test_invalidate_cache_twice_is_idempotent():
    """Calling invalidate_cache() twice in a row must not raise."""
    path = FIXTURE_DIR / "clean.DATA"
    api = LinterAPI()
    api.lint(path)  # warm cache
    api.invalidate_cache()
    # Second call must be a no-op, not an error.
    api.invalidate_cache()
    stats = api.cache_stats()
    assert stats.size == 0


def test_async_lint_returns_result_or_timeout():
    """Async path with a normal timeout must return a LintResult or timeout.

    Verifies that `lint_async` from a sync context (via asyncio.run) works.
    """
    api = LinterAPI()
    result = asyncio.run(api.lint_async(FIXTURE_DIR / "clean.DATA"))
    assert result is not None
    assert result.deck_path.endswith("clean.DATA")


def test_async_lint_timeout_path():
    """Async path with a tiny timeout raises LinterTimeoutError OR completes.

    Either outcome is acceptable: we only assert no silent crash. On a very
    fast machine a 1 ms budget may still permit a sub-zero cache-hit return.
    """
    api = LinterAPI(linter_timeout_s=0.001)
    try:
        asyncio.run(api.lint_async(FIXTURE_DIR / "clean.DATA"))
    except LinterTimeoutError:
        return
    except LinterError:
        # If the linter bails out before the executor times out, that's
        # also acceptable behaviour.
        return
