"""Integration tests for API hardening: path validation and store eviction.

Covers:
1. Path traversal attempts -> 400
2. Allowed temp paths -> 200
3. Job store eviction (oldest completed evicted, running jobs survive)
4. Session store eviction (LRU behavior)
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile

from opm_ai.api.server import create_app
from opm_ai.api.job_store import create_job, get_job, set_job_completed, set_job_running
from opm_ai.api.schemas import SimulationResultDTO
from opm_ai.api.session_store import get_or_create_session, get_session, update_session
from opm_ai.api.schemas import ChatMessage


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient for integration tests."""
    app = create_app()
    with TestClient(app) as client:
        yield client


class TestPathValidation:
    """Tests for path validation and traversal protection."""

    @pytest.mark.integration
    def test_path_traversal_etc_passwd_rejected(self, client):
        """POST /api/build with output_path '/etc/passwd.DATA' -> 400 (outside allowed roots)."""
        response = client.post("/api/build", json={
            "description": "Simple depletion case",
            "output_path": "/etc/passwd.DATA"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "outside allowed directories" in data["detail"].lower() or "not allowed" in data["detail"].lower()

    @pytest.mark.integration
    def test_path_traversal_relative_outside_rejected(self, client):
        """POST /api/build with an output_path outside every allowed root -> 400.

        Uses an absolute path under $HOME (not an allowlisted root) so the result
        does not depend on the test's CWD depth. A relative '../..' target is a
        poor probe here: from the repo root it resolves into /tmp, which IS an
        allowed root, so it would (correctly) be accepted.
        """
        response = client.post("/api/build", json={
            "description": "Simple depletion case",
            "output_path": str(Path.home() / "evil.DATA"),
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data

    @pytest.mark.integration
    def test_lint_deck_path_traversal_rejected(self, client):
        """POST /api/lint with deck_path outside allowed roots -> 400."""
        response = client.post("/api/lint", json={
            "deck_path": "/etc/passwd.DATA"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data

    @pytest.mark.integration
    def test_run_deck_path_traversal_rejected(self, client):
        """POST /api/run with deck_path outside allowed roots -> 400."""
        response = client.post("/api/run", json={
            "deck_path": "/etc/passwd",
            "timeout": 60
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data

    @pytest.mark.integration
    def test_allowed_temp_path_accepted(self, client):
        """POST /api/build with output_path under /tmp -> 200."""
        # Use a path under system temp dir which is always allowed
        temp_path = Path(tempfile.gettempdir()) / "smoke_test.DATA"
        response = client.post("/api/build", json={
            "description": "Simple depletion case",
            "output_path": str(temp_path)
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["lint"]["passed"] is True

    @pytest.mark.integration
    def test_missing_data_suffix_rejected(self, client):
        """POST /api/build with output_path missing .DATA suffix -> 400."""
        temp_path = Path(tempfile.gettempdir()) / "smoke_test.txt"
        response = client.post("/api/build", json={
            "description": "Simple depletion case",
            "output_path": str(temp_path)
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert ".data" in data["detail"].lower() or "suffix" in data["detail"].lower()

    @pytest.mark.integration
    def test_directory_rejected_as_file(self, client, tmp_path):
        """POST /api/build with output_path pointing to existing directory -> 400."""
        # Create a directory
        dir_path = tmp_path / "somedir"
        dir_path.mkdir()
        response = client.post("/api/build", json={
            "description": "Simple depletion case",
            "output_path": str(dir_path)
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "directory" in data["detail"].lower()

    @pytest.mark.integration
    def test_allowed_temp_path_accepted(self, client):
        """POST /api/build with output_path under /tmp -> 200."""
        # Use a path under system temp dir which is always allowed
        temp_path = Path(tempfile.gettempdir()) / "smoke_test.DATA"
        response = client.post("/api/build", json={
            "description": "Simple depletion case",
            "output_path": str(temp_path)
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["lint"]["passed"] is True

    @pytest.mark.integration
    def test_missing_data_suffix_rejected(self, client):
        """POST /api/build with output_path missing .DATA suffix -> 400."""
        temp_path = Path(tempfile.gettempdir()) / "smoke_test.txt"
        response = client.post("/api/build", json={
            "description": "Simple depletion case",
            "output_path": str(temp_path)
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert ".data" in data["detail"].lower() or "suffix" in data["detail"].lower()

    @pytest.mark.integration
    def test_directory_rejected_as_file(self, client, tmp_path):
        """POST /api/build with output_path pointing to existing directory -> 400."""
        # Create a directory
        dir_path = tmp_path / "somedir"
        dir_path.mkdir()
        response = client.post("/api/build", json={
            "description": "Simple depletion case",
            "output_path": str(dir_path)
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "directory" in data["detail"].lower()


class TestJobStoreEviction:
    """Tests for bounded job store with LRU eviction of completed jobs."""

    @pytest.mark.integration
    def test_job_store_evicts_oldest_completed(self, client):
        """Job store evicts oldest completed job when capacity exceeded."""
        # Save original capacity
        from opm_ai.api.job_store import _job_store
        original_max = _job_store._max_entries

        try:
            # Temporarily reduce capacity for testing
            _job_store._max_entries = 3
            _job_store._jobs.clear()

            # Create 3 completed jobs
            job_ids = []
            for i in range(3):
                jid = create_job(f"job-{i}")
                set_job_running(jid)
                result_dto = SimulationResultDTO(
                    success=True,
                    output_dir=f"/tmp/out_{i}",
                    returncode=0,
                    duration_s=1.0,
                    stdout="",
                    stderr="",
                    warnings=[],
                    summary_files={},
                    prt_path=None,
                )
                set_job_completed(jid, result_dto)
                job_ids.append(jid)

            # All 3 should exist
            assert len(_job_store._jobs) == 3

            # Create a 4th completed job - should evict oldest (job-0)
            jid4 = create_job("job-3")
            set_job_running(jid4)
            result_dto = SimulationResultDTO(
                success=True,
                output_dir="/tmp/out_3",
                returncode=0,
                duration_s=1.0,
                stdout="",
                stderr="",
                warnings=[],
                summary_files={},
                prt_path=None,
            )
            set_job_completed(jid4, result_dto)

            # Should still be at capacity
            assert len(_job_store._jobs) == 3
            # Oldest completed (job-0) should be evicted
            assert get_job("job-0") is None
            # Others should remain
            assert get_job("job-1") is not None
            assert get_job("job-2") is not None
            assert get_job("job-3") is not None

        finally:
            _job_store._max_entries = original_max
            _job_store._jobs.clear()

    @pytest.mark.integration
    def test_job_store_never_evicts_running(self, client):
        """Job store never evicts running/pending jobs, returns 429 if all running at capacity."""
        from opm_ai.api.job_store import _job_store
        original_max = _job_store._max_entries

        try:
            _job_store._max_entries = 2
            _job_store._jobs.clear()

            # Create 2 running jobs (at capacity)
            jid1 = create_job("running-1")
            set_job_running(jid1)

            jid2 = create_job("running-2")
            set_job_running(jid2)

            assert len(_job_store._jobs) == 2

            # Try to create a 3rd job - should raise ValueError (capacity full, no completed to evict)
            try:
                create_job("running-3")
                pytest.fail("Expected ValueError for capacity with all running")
            except ValueError as e:
                assert "at capacity" in str(e) or "cannot accept new jobs" in str(e)

        finally:
            _job_store._max_entries = original_max
            _job_store._jobs.clear()

    @pytest.mark.integration
    def test_run_endpoint_returns_429_when_store_full_of_running(self, client):
        """POST /api/run returns 429 when job store at capacity with all running."""
        from opm_ai.api.job_store import _job_store
        original_max = _job_store._max_entries

        try:
            _job_store._max_entries = 2
            _job_store._jobs.clear()

            # Fill with 2 running jobs
            jid1 = create_job("running-1")
            set_job_running(jid1)
            jid2 = create_job("running-2")
            set_job_running(jid2)

            # Try to start a run - should get 429
            temp_deck = Path(tempfile.gettempdir()) / "test_deck.DATA"
            temp_deck.write_text("RUNSPEC\n/\nGRID\n/\nPROPS\n/\nSOLUTION\n/\nSCHEDULE\n/\n")
            try:
                response = client.post("/api/run", json={
                    "deck_path": str(temp_deck),
                    "timeout": 60
                })
                # Should get 429 (capacity exceeded)
                assert response.status_code == 429, f"Expected 429, got {response.status_code}: {response.text}"
                data = response.json()
                assert "detail" in data
            finally:
                temp_deck.unlink(missing_ok=True)

        finally:
            _job_store._max_entries = original_max
            _job_store._jobs.clear()


class TestSessionStoreEviction:
    """Tests for bounded session store with LRU eviction."""

    @pytest.mark.integration
    def test_session_store_evicts_lru(self, client):
        """Session store evicts least recently used session when capacity exceeded."""
        from opm_ai.api.session_store import _session_store
        original_max = _session_store._max_entries

        try:
            _session_store._max_entries = 3
            _session_store._sessions.clear()

            # Create 3 sessions
            for i in range(3):
                sid, history = get_or_create_session(f"session-{i}")
                history.append(ChatMessage(role="user", content=f"msg {i}"))
                update_session(sid, history)

            assert len(_session_store._sessions) == 3

            # Create 4th session - should evict oldest (session-0)
            sid4, history4 = get_or_create_session("session-3")
            history4.append(ChatMessage(role="user", content="msg 3"))
            update_session(sid4, history4)

            assert len(_session_store._sessions) == 3
            assert get_session("session-0") is None
            assert get_session("session-1") is not None
            assert get_session("session-2") is not None
            assert get_session("session-3") is not None

        finally:
            _session_store._max_entries = original_max
            _session_store._sessions.clear()

    @pytest.mark.integration
    def test_session_lru_update_on_access(self, client):
        """Accessing a session moves it to MRU (most recently used)."""
        from opm_ai.api.session_store import _session_store
        original_max = _session_store._max_entries

        try:
            _session_store._max_entries = 2
            _session_store._sessions.clear()

            # Create 2 sessions
            get_or_create_session("session-a")
            get_or_create_session("session-b")

            # Access session-a (moves to MRU)
            get_session("session-a")

            # Add session-c - should evict session-b (now LRU)
            get_or_create_session("session-c")

            assert get_session("session-a") is not None  # MRU, kept
            assert get_session("session-b") is None      # LRU, evicted
            assert get_session("session-c") is not None  # New, kept

        finally:
            _session_store._max_entries = original_max
            _session_store._sessions.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])