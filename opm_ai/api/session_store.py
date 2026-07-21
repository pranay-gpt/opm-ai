"""In-memory chat session store with bounded eviction."""

import asyncio
import uuid
from collections import OrderedDict
from threading import Lock
from typing import Optional

from opm_ai.api.schemas import ChatMessage
from opm_ai.settings import settings


class SessionStore:
    """Thread-safe bounded session store with LRU eviction."""

    def __init__(self, max_entries: Optional[int] = None):
        self._sessions: OrderedDict[str, list[ChatMessage]] = OrderedDict()
        self._locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
        self._lock = Lock()
        self._max_entries = max_entries if max_entries is not None else settings.session_store_max_entries

    def _evict_if_needed(self) -> None:
        """Evict oldest sessions if over capacity."""
        while len(self._sessions) >= self._max_entries:
            # Remove oldest session (first item in OrderedDict)
            oldest_session_id = next(iter(self._sessions))
            del self._sessions[oldest_session_id]

    def get_or_create_session(self, session_id: Optional[str] = None) -> tuple[str, list[ChatMessage]]:
        """Get existing session or create a new one.

        Returns:
            Tuple of (session_id, message_history)
        """
        with self._lock:
            self._evict_if_needed()

            if session_id is None:
                session_id = str(uuid.uuid4())

            if session_id not in self._sessions:
                self._sessions[session_id] = []

            # Move to end (most recently used)
            history = self._sessions.pop(session_id)
            self._sessions[session_id] = history

            return session_id, history

    def get_session(self, session_id: str) -> Optional[list[ChatMessage]]:
        """Get session history by ID, moving to MRU position."""
        with self._lock:
            if session_id not in self._sessions:
                return None

            # Move to end (most recently used)
            history = self._sessions.pop(session_id)
            self._sessions[session_id] = history
            return history

    def update_session(self, session_id: str, history: list[ChatMessage]) -> None:
        """Update session history, moving to MRU position."""
        with self._lock:
            if session_id in self._sessions:
                self._sessions.pop(session_id)
            self._sessions[session_id] = history

    def get_session_lock(self, session_id: str) -> asyncio.Lock:
        """Get the per-session asyncio.Lock, creating it if needed.

        The lock dict is bounded like the session dict (same max_entries,
        LRU eviction) so concurrent connections on one session id always
        receive the same Lock object while it is live.
        """
        with self._lock:
            if session_id in self._locks:
                lock = self._locks.pop(session_id)
            else:
                lock = asyncio.Lock()
                while len(self._locks) >= self._max_entries:
                    self._locks.popitem(last=False)
            self._locks[session_id] = lock
            return lock

    def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID."""
        with self._lock:
            self._locks.pop(session_id, None)
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def clear(self) -> None:
        """Clear all sessions."""
        with self._lock:
            self._sessions.clear()
            self._locks.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)


# Global session store instance
_session_store = SessionStore()


def get_session_store() -> SessionStore:
    """Get the global session store instance."""
    return _session_store


def get_or_create_session(session_id: Optional[str] = None) -> tuple[str, list[ChatMessage]]:
    """Get existing session or create a new one.

    Returns:
        Tuple of (session_id, message_history)
    """
    return _session_store.get_or_create_session(session_id)


def get_session(session_id: str) -> Optional[list[ChatMessage]]:
    """Get session history by ID."""
    return _session_store.get_session(session_id)


def update_session(session_id: str, history: list[ChatMessage]) -> None:
    """Update session history."""
    _session_store.update_session(session_id, history)


def get_session_lock(session_id: str) -> asyncio.Lock:
    """Get the per-session asyncio.Lock for read-modify-write sections."""
    return _session_store.get_session_lock(session_id)


def delete_session(session_id: str) -> bool:
    """Delete a session by ID."""
    return _session_store.delete_session(session_id)


def clear_sessions() -> None:
    """Clear all sessions."""
    _session_store.clear()