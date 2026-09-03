import os
import pytest

@pytest.fixture(scope="session", autouse=True)
def setup_env_vars():
    """Set dummy env vars before any test imports main.py"""
    os.environ.setdefault("SERPAPI_API_KEY", "test_key")
    os.environ.setdefault("OPENROUTER_API_KEY", "test_key")
