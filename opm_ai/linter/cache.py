"""LinterCache: bounded LRU keyed on (path, content_sha256).

Catalogue version is folded into the key by the caller (LinterAPI)
before get/put, so this module has no opinion about catalogue logic.

Thread-safe. Uses a single re-entrant lock around all mutations.
"""
from __future__ import annotations

import copy
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    size: int
    evictions: int


class LinterCache(Generic[T]):
    def __init__(self, max_size: int = 256) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self._max = max_size
        self._data: OrderedDict[tuple[str, str], T] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @staticmethod
    def _key(path: Path, sha: str) -> tuple[str, str]:
        return (str(path), sha)

    def get(self, path: Path, sha: str) -> Optional[T]:
        k = self._key(path, sha)
        with self._lock:
            v = self._data.get(k)
            if v is None:
                self._misses += 1
                return None
            self._data.move_to_end(k)
            self._hits += 1
            return copy.deepcopy(v)

    def put(self, path: Path, sha: str, value: T) -> None:
        k = self._key(path, sha)
        with self._lock:
            if k in self._data:
                self._data.move_to_end(k)
                self._data[k] = value
                return
            self._data[k] = value
            if len(self._data) > self._max:
                self._data.popitem(last=False)
                self._evictions += 1

    def invalidate(self, path: Optional[Path] = None) -> None:
        with self._lock:
            if path is None:
                self._data.clear()
                return
            prefix = str(path)
            keys = [k for k in self._data if k[0] == prefix]
            for k in keys:
                del self._data[k]

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                size=len(self._data),
                evictions=self._evictions,
            )
