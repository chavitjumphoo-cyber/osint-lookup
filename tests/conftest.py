"""Unit tests never contact real investigation targets or paid APIs."""

import httpx
import pytest
import requests


@pytest.fixture(autouse=True)
def no_external_requests(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Mock network requests explicitly in tests")

    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "request", blocked)
