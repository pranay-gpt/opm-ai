"""LinterExecutor unit tests."""
import asyncio
import time

import pytest

from opm_ai.linter.executor import LinterExecutor, LinterError, LinterTimeoutError


def test_submit_returns_value():
    ex = LinterExecutor(max_workers=2, timeout_s=1.0)
    try:
        assert ex.submit(lambda x: x * 2, 21) == 42
    finally:
        ex.shutdown()


def test_submit_raises_timeout_error_on_slow_call():
    ex = LinterExecutor(max_workers=2, timeout_s=0.1)
    try:
        with pytest.raises(LinterTimeoutError):
            ex.submit(time.sleep, 2.0)
    finally:
        ex.shutdown()


def test_submit_propagates_exceptions():
    ex = LinterExecutor(max_workers=2, timeout_s=1.0)
    try:
        with pytest.raises(ValueError, match="boom"):
            ex.submit(lambda: (_ for _ in ()).throw(ValueError("boom")))
    finally:
        ex.shutdown()


def test_submit_async_works_in_event_loop():
    ex = LinterExecutor(max_workers=2, timeout_s=1.0)
    try:
        async def run():
            return await ex.submit_async(lambda x: x + 1, 41)
        assert asyncio.run(run()) == 42
    finally:
        ex.shutdown()


def test_submit_async_raises_timeout():
    ex = LinterExecutor(max_workers=2, timeout_s=0.1)
    try:
        async def run():
            await ex.submit_async(time.sleep, 2.0)
        with pytest.raises(LinterTimeoutError):
            asyncio.run(run())
    finally:
        ex.shutdown()


def test_linter_timeout_is_subclass_of_linter_error():
    assert issubclass(LinterTimeoutError, LinterError)
