"""LinterAPI sync entry-point tests."""
import time
from pathlib import Path

import pytest

from opm_ai.linter.api import LinterAPI, default_api


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "linter_api"


def test_lint_returns_lint_result_on_clean_deck():
    result = default_api.lint(FIXTURE_DIR / "clean.DATA")
    assert result.deck_path.endswith("clean.DATA")
    assert result.passed is True
    assert len(result.errors) == 0


def test_lint_unknown_keyword_yields_error():
    result = default_api.lint(FIXTURE_DIR / "parse_error.DATA")
    assert result.passed is False
    assert len(result.errors) >= 1


def test_lint_missing_required_sections_warns_or_errors():
    result = default_api.lint(FIXTURE_DIR / "missing_sections.DATA")
    # GRID and SCHEDULE missing -> ERROR (no INCLUDE present).
    assert len(result.errors) >= 1
    severities = {i.severity for i in result.issues}
    assert "ERROR" in severities


def test_lint_returns_deepcopy_per_call():
    a = default_api.lint(FIXTURE_DIR / "clean.DATA")
    b = default_api.lint(FIXTURE_DIR / "clean.DATA")
    assert a is not b
    a.issues.append("mutated")
    assert len(b.issues) == len(a.issues) - 1


def test_invalidate_cache_clears_stats():
    api = LinterAPI()
    api.lint(FIXTURE_DIR / "clean.DATA")  # warm
    api.lint(FIXTURE_DIR / "clean.DATA")  # hit
    s_before = api.cache_stats()
    api.invalidate_cache()
    s_after = api.cache_stats()
    assert s_before.size > 0
    assert s_after.size == 0


# ---------------------------------------------------------------------------
# Performance + cache-hit semantics (Task 12).
#
# These tests pin two behavioural guarantees of the facade cache:
#   1. A cache HIT is measurably faster than a MISS (>= 5x on this machine
#      we observed ~1000x; 5x is the generous floor for CI stability).
#   2. A cache HIT returns a deep copy of the stored LintResult, so two
#      callers that mutate their own copy cannot leak state into each other.
#
# Wall-clock budget for the whole test_linter_api.py file: < 5s on CI.
# ---------------------------------------------------------------------------

CLEAN_DECK = FIXTURE_DIR / "clean.DATA"


def _median(samples: list[float]) -> float:
    s = sorted(samples)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def test_cache_hit_is_measurably_faster_than_cold_lint():
    """A cache HIT must be at least 5x faster than a cold MISS."""
    api = LinterAPI()
    api.invalidate_cache()

    # One warm-up call so JIT/imports/catalogue_version don't pollute the
    # first cold sample. The warm-up itself fills the cache.
    api.lint(CLEAN_DECK)

    # Measure cold: invalidate between runs so each is a true MISS.
    api.invalidate_cache()
    cold_samples: list[float] = []
    for _ in range(3):
        t0 = time.perf_counter()
        api.lint(CLEAN_DECK)
        cold_samples.append(time.perf_counter() - t0)
        api.invalidate_cache()

    # Warm the cache once, then measure warm hits.
    api.lint(CLEAN_DECK)
    warm_samples: list[float] = []
    for _ in range(20):
        t0 = time.perf_counter()
        api.lint(CLEAN_DECK)
        warm_samples.append(time.perf_counter() - t0)

    cold = _median(cold_samples)
    warm = _median(warm_samples)
    assert warm > 0.0, "warm sample was zero — timer broken"
    ratio = cold / warm
    assert ratio >= 5.0, (
        f"cache hit only {ratio:.1f}x faster than cold (cold={cold*1000:.2f}ms, "
        f"warm={warm*1e6:.2f}us); expected >= 5x"
    )


def test_cache_hit_returns_deepcopy_not_shared_state():
    """Two consecutive cache HITS must return independent objects.

    The facade's cache.get() returns a deep copy of the stored result;
    that property must hold for every cache hit so that mutating one
    caller's LintResult cannot leak into another caller's view.
    """
    from opm_ai.linter.models import LintIssue

    api = LinterAPI()
    api.invalidate_cache()

    # First call: miss (the executor returns the original LintResult and
    # stores it; callers of the miss path can therefore mutate it, but
    # that's a documented optimisation opportunity in the plan, not part
    # of the HIT-path contract).
    api.lint(CLEAN_DECK)

    # Second + third calls: both HITS. They must each get their own deep
    # copy of the cached value.
    b = api.lint(CLEAN_DECK)
    c = api.lint(CLEAN_DECK)

    assert b is not c, "two cache hits returned the same instance"
    assert b.deck_path == c.deck_path

    original_count = len(b.issues)
    b.issues.append(
        LintIssue(severity="ERROR", message="mutation-marker")
    )
    assert len(b.issues) == original_count + 1
    assert len(c.issues) == original_count, (
        "appending to a cached LintResult leaked into a sibling call's "
        "result — cache hit returned a reference instead of a deepcopy"
    )


def test_cache_stats_reflect_hits_and_misses():
    """CacheStats.hits and .misses must track the facade's read traffic."""
    api = LinterAPI()
    api.invalidate_cache()
    api.lint(CLEAN_DECK)  # 1 miss (cache empty), no prior state
    api.lint(CLEAN_DECK)  # 1 hit
    api.lint(CLEAN_DECK)  # 1 hit

    stats = api.cache_stats()
    assert stats.misses >= 1, f"expected >= 1 miss, got {stats.misses}"
    assert stats.hits >= 2, f"expected >= 2 hits, got {stats.hits}"
    assert stats.size == 1
    assert stats.hits + stats.misses >= 3
