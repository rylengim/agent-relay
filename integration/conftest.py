"""Fixtures for an existing relay process; never import or reset its database."""

import os
from urllib.parse import urlsplit

import httpx
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--save-demo-credentials",
        action="store_true",
        help="Save test identities to a private temporary JSON file for dashboard checks.",
    )


@pytest.fixture
def relay():
    base_url = os.environ.get("RELAY_TEST_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        pytest.fail(
            "RELAY_TEST_BASE_URL is required. Start the API and set it to its origin "
            "(for example http://127.0.0.1:8000).",
            pytrace=False,
        )
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        pytest.fail("RELAY_TEST_BASE_URL must be an HTTP(S) origin without credentials or a path.", pytrace=False)
    with httpx.Client(base_url=base_url, timeout=10.0, trust_env=False) as client:
        try:
            response = client.get("/ready")
        except httpx.RequestError:
            pytest.fail("The API is unreachable at RELAY_TEST_BASE_URL. Start the API first.", pytrace=False)
        assert response.status_code == 200, "The running API must report database readiness."
        assert response.json() == {"status": "ready"}
        yield client
