import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from mcp_proxy.oauth import authorization_base_url, discover_metadata


def test_authorization_base_url() -> None:
    assert (
        authorization_base_url("https://api.example.com/v1/mcp")
        == "https://api.example.com"
    )


class MockResponse:
    def __init__(self, status_code: int, data: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self._data = data or {}

    def json(self) -> dict[str, str]:
        return self._data


@pytest.mark.asyncio
async def test_discover_metadata_success() -> None:
    data = {
        "authorization_endpoint": "https://auth.example.com/authorize",
        "token_endpoint": "https://auth.example.com/token",
        "registration_endpoint": "https://auth.example.com/register",
    }
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=MockResponse(200, data))):
        metadata = await discover_metadata("https://api.example.com")
    assert metadata["authorization_endpoint"] == data["authorization_endpoint"]
    assert metadata["token_endpoint"] == data["token_endpoint"]


@pytest.mark.asyncio
async def test_discover_metadata_fallback() -> None:
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=MockResponse(404))):
        metadata = await discover_metadata("https://api.example.com")
    assert metadata["token_endpoint"] == "https://api.example.com/token"
