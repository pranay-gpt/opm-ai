"""Smoke tests — verify project structure and imports are intact."""
import importlib
import os


MODULES = [
    "opm_ai",
    "opm_ai.runner",
    "opm_ai.linter",
    "opm_ai.builder",
    "opm_ai.preprocess",
    "opm_ai.postprocess",
    "opm_ai.chat",
    "opm_ai.explainer",
]


def test_all_modules_importable():
    """Every opm_ai submodule must be importable."""
    for module in MODULES:
        mod = importlib.import_module(module)
        assert mod is not None, f"Failed to import {module}"


def test_env_example_exists():
    """Ensure .env.example is present so new users know what keys to set."""
    assert os.path.exists(".env.example"), ".env.example missing — add it for contributors"


def test_dockerfile_exists():
    """Dockerfile must exist for Docker-based deployment."""
    assert os.path.exists("docker/Dockerfile"), "docker/Dockerfile is missing"


def test_docker_compose_exists():
    """docker-compose.yml must exist."""
    assert os.path.exists("docker/docker-compose.yml"), "docker/docker-compose.yml is missing"
