"""Integration tests for the runtime settings API (POST/GET /api/settings).

Covers:
1. GET returns provider + key booleans, never key material.
2. POST offline -> groq with a fake key takes effect in-process.
3. A fresh LLMClient after the override targets the new provider
   (groq SDK constructor monkeypatched: no network).
4. Empty-string key clears a configured key.

All tests force explicit settings state and restore it afterwards; nothing
here depends on a .env or real keys.
"""

import pytest
from fastapi.testclient import TestClient

from opm_ai.api.server import create_app
from opm_ai.settings import settings

FAKE_KEY = "gsk_fake_test_key_do_not_leak"


@pytest.fixture()
def client(restore_settings):
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def restore_settings():
    """Force a known offline state and restore the singleton afterwards."""
    saved = (
        settings.llm_provider,
        settings.groq_api_key,
        settings.openai_api_key,
        settings.nvidia_nim_api_key,
    )
    settings.llm_provider = "offline"
    settings.groq_api_key = None
    settings.openai_api_key = None
    settings.nvidia_nim_api_key = None
    yield
    (
        settings.llm_provider,
        settings.groq_api_key,
        settings.openai_api_key,
        settings.nvidia_nim_api_key,
    ) = saved


@pytest.mark.integration
def test_get_settings_default_offline(client):
    """GET /api/settings in forced-offline state."""
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "offline"
    assert data["active_provider"] == "offline"
    assert data["keys_configured"] == {"groq": False, "openai": False, "nim": False}


@pytest.mark.integration
def test_post_settings_offline_to_groq(client):
    """POST provider=groq with a fake key: GET reflects it, key never echoed."""
    response = client.post("/api/settings", json={
        "provider": "groq",
        "groq_api_key": FAKE_KEY,
    })
    assert response.status_code == 200
    assert FAKE_KEY not in response.text

    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "groq"
    assert data["active_provider"] == "groq"
    assert data["keys_configured"]["groq"] is True
    assert FAKE_KEY not in response.text

    # The in-memory singleton picked up the override.
    assert settings.llm_provider == "groq"
    assert settings.active_llm_client == "groq"


@pytest.mark.integration
def test_provider_without_key_resolves_offline(client):
    """Selecting a keyless provider: stored, but active resolution stays offline."""
    response = client.post("/api/settings", json={"provider": "openai"})
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"
    assert data["active_provider"] == "offline"


@pytest.mark.integration
def test_fresh_llmclient_targets_new_provider(client, monkeypatch):
    """A fresh LLMClient after the override constructs the groq SDK client
    with the overridden key (constructor faked: no network)."""
    import groq

    constructed = {}

    class FakeGroq:
        def __init__(self, api_key=None):
            constructed["api_key"] = api_key

    monkeypatch.setattr(groq, "Groq", FakeGroq)

    client.post("/api/settings", json={
        "provider": "groq",
        "groq_api_key": FAKE_KEY,
    })

    from opm_ai.llm.client import LLMClient
    llm = LLMClient()
    assert llm.available is True
    assert constructed["api_key"] == FAKE_KEY


@pytest.mark.integration
def test_empty_string_clears_key(client):
    """POSTing an empty key string clears the configured key."""
    client.post("/api/settings", json={
        "provider": "groq",
        "groq_api_key": FAKE_KEY,
    })
    response = client.post("/api/settings", json={
        "provider": "offline",
        "groq_api_key": "",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["keys_configured"]["groq"] is False
    assert settings.groq_api_key is None


@pytest.mark.integration
def test_omitted_key_untouched(client):
    """POSTing without a key field leaves the existing key configured."""
    client.post("/api/settings", json={
        "provider": "groq",
        "groq_api_key": FAKE_KEY,
    })
    response = client.post("/api/settings", json={"provider": "offline"})
    assert response.status_code == 200
    assert response.json()["keys_configured"]["groq"] is True


@pytest.mark.integration
def test_invalid_provider_rejected(client):
    """Unknown provider name -> 422 from Literal validation."""
    response = client.post("/api/settings", json={"provider": "skynet"})
    assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
