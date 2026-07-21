"""Concurrency tests for the per-session lock in the chat session store.

The websocket handler in routes/chat.py wraps every session
read-modify-write in `async with get_session_lock(session_id)`. These
tests drive that same pattern with concurrent coroutines on one session
id and assert no update is lost. asyncio.run inside sync tests: the suite
has no pytest-asyncio and these tests need their own event loop anyway.
"""

import asyncio

import pytest

from opm_ai.api.schemas import ChatMessage
from opm_ai.api.session_store import (
    _session_store,
    clear_sessions,
    get_or_create_session,
    get_session,
    get_session_lock,
    update_session,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_sessions()
    yield
    clear_sessions()


async def _locked_append(session_id: str, content: str) -> None:
    """Mirror chat.py's locked read-modify-write, with forced yields at the
    points where the handler awaits (LLM call, websocket send) so that an
    unlocked version demonstrably interleaves and loses updates."""
    lock = get_session_lock(session_id)
    async with lock:
        _, history = get_or_create_session(session_id)
        snapshot = list(history)
        await asyncio.sleep(0)
        snapshot.append(ChatMessage(role="user", content=content))
        await asyncio.sleep(0)
        update_session(session_id, snapshot)


@pytest.mark.integration
def test_concurrent_writers_do_not_lose_updates():
    """Two concurrent 'connections' (tasks) x 25 appends on one session id:
    all 50 messages survive."""
    session_id = "race-session"

    async def writer(name: str, n: int):
        for i in range(n):
            await _locked_append(session_id, f"{name}-{i}")

    async def main():
        await asyncio.gather(writer("conn-a", 25), writer("conn-b", 25))

    asyncio.run(main())

    history = get_session(session_id)
    assert history is not None
    contents = [m.content for m in history]
    assert len(contents) == 50
    for name in ("conn-a", "conn-b"):
        assert [c for c in contents if c.startswith(name)] == [
            f"{name}-{i}" for i in range(25)
        ]


@pytest.mark.integration
def test_same_session_id_shares_one_lock():
    """Concurrent connections on one session id must serialize on the SAME
    Lock object; a different session gets its own."""
    async def main():
        lock_a1 = get_session_lock("session-a")
        lock_a2 = get_session_lock("session-a")
        lock_b = get_session_lock("session-b")
        assert lock_a1 is lock_a2
        assert lock_a1 is not lock_b

    asyncio.run(main())


@pytest.mark.integration
def test_lock_dict_bounded_like_session_store():
    """The lock dict evicts LRU at the same max_entries bound as sessions."""
    original_max = _session_store._max_entries
    try:
        _session_store._max_entries = 3

        async def main():
            for i in range(5):
                get_session_lock(f"session-{i}")

        asyncio.run(main())
        assert len(_session_store._locks) == 3
        assert set(_session_store._locks) == {"session-2", "session-3", "session-4"}
    finally:
        _session_store._max_entries = original_max


@pytest.mark.integration
def test_lock_actually_serializes_critical_section():
    """While one task holds the session lock, another task's critical
    section cannot start (checked via an in-section flag)."""
    session_id = "serialize-check"
    in_section = {"count": 0, "max_seen": 0}

    async def worker():
        lock = get_session_lock(session_id)
        async with lock:
            in_section["count"] += 1
            in_section["max_seen"] = max(in_section["max_seen"], in_section["count"])
            await asyncio.sleep(0.01)
            in_section["count"] -= 1

    async def main():
        await asyncio.gather(*(worker() for _ in range(5)))

    asyncio.run(main())
    assert in_section["max_seen"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
