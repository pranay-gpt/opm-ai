"""LinterCache unit tests."""
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

from opm_ai.linter.cache import LinterCache, CacheStats


@dataclass
class FakeResult:
    issues: list
    passed: bool = True


def test_miss_then_hit(tmp_path: Path):
    cache: LinterCache[FakeResult] = LinterCache(max_size=4)
    p = tmp_path / "a.DATA"
    sha = "abc123"
    assert cache.get(p, sha) is None
    r = FakeResult(issues=[])
    cache.put(p, sha, r)
    got = cache.get(p, sha)
    assert got is not None
    assert got is not r  # must be a copy, not the same object


def test_copy_is_deep_enough_to_be_mutable_safely(tmp_path: Path):
    cache: LinterCache[FakeResult] = LinterCache(max_size=4)
    p = tmp_path / "a.DATA"
    sha = "abc"
    cache.put(p, sha, FakeResult(issues=["x"]))
    a = cache.get(p, sha)
    a.issues.append("mutated")
    b = cache.get(p, sha)
    assert b.issues == ["x"]  # original list not affected


def test_lru_eviction(tmp_path: Path):
    cache: LinterCache[FakeResult] = LinterCache(max_size=2)
    for i in range(3):
        cache.put(tmp_path / f"{i}.DATA", f"sha{i}", FakeResult(issues=[]))
    # entry 0 (oldest) should have been evicted
    assert cache.get(tmp_path / "0.DATA", "sha0") is None
    assert cache.get(tmp_path / "2.DATA", "sha2") is not None


def test_stats_track_hits_and_misses(tmp_path: Path):
    cache: LinterCache[FakeResult] = LinterCache(max_size=4)
    cache.put(tmp_path / "a.DATA", "sha", FakeResult(issues=[]))
    cache.get(tmp_path / "a.DATA", "sha")   # hit
    cache.get(tmp_path / "b.DATA", "missing")  # miss
    s = cache.stats()
    assert s.hits == 1
    assert s.misses == 1
    assert s.size == 1


def test_invalidate_all(tmp_path: Path):
    cache: LinterCache[FakeResult] = LinterCache(max_size=4)
    for i in range(3):
        cache.put(tmp_path / f"{i}.DATA", f"sha{i}", FakeResult(issues=[]))
    cache.invalidate()
    s = cache.stats()
    assert s.size == 0


def test_concurrent_get_put_is_safe(tmp_path: Path):
    cache: LinterCache[FakeResult] = LinterCache(max_size=64)
    errors: list[BaseException] = []

    def worker(i: int):
        try:
            for j in range(50):
                cache.put(tmp_path / f"f{i}_{j}.DATA", f"s{j}", FakeResult(issues=[]))
                cache.get(tmp_path / f"f{i}_{j}.DATA", f"s{j}")
        except BaseException as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert not errors
