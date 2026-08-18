"""LinterExecutor: bounded worker pool with timeout enforcement.

Sync `submit()` blocks the calling thread on a `Future.result(timeout=...)`.
Async `submit_async()` schedules the work onto the same pool via
`loop.run_in_executor`, then awaits with `asyncio.wait_for`. Either
path raises `LinterTimeoutError` if the call exceeds the configured
budget; the underlying future is cancelled and the worker is freed.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class LinterError(Exception):
    """Base class for all linter-API-level errors."""


class LinterTimeoutError(LinterError):
    """A lint call exceeded the configured timeout."""


class LinterExecutor:
    def __init__(self, max_workers: int = 4, timeout_s: float = 30.0) -> None:
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._timeout_s = timeout_s
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="linter-api",
        )

    def submit(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        future: Future[T] = self._pool.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=self._timeout_s)
        except asyncio.TimeoutError:  # noqa: PERF203 - intentional
            future.cancel()
            raise LinterTimeoutError(
                f"lint call exceeded {self._timeout_s}s budget"
            ) from None

    async def submit_async(
        self, fn: Callable[..., T], /, *args: Any, **kwargs: Any
    ) -> T:
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(self._pool, lambda: fn(*args, **kwargs))
        try:
            return await asyncio.wait_for(future, timeout=self._timeout_s)
        except asyncio.TimeoutError:
            future.cancel()
            raise LinterTimeoutError(
                f"lint call exceeded {self._timeout_s}s budget"
            ) from None

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)
