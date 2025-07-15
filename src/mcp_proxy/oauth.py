from __future__ import annotations

"""Utilities for performing OAuth flow with MCP servers."""

import asyncio
import base64
import hashlib
import secrets
from urllib.parse import urlencode, urljoin, urlparse

import contextlib
import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

MCP_PROTOCOL_VERSION = "2025-03-26"


def authorization_base_url(server_url: str) -> str:
    """Return the authorization base URL derived from the MCP server URL."""
    parsed = urlparse(server_url)
    return f"{parsed.scheme}://{parsed.netloc}"


async def discover_metadata(base_url: str) -> dict[str, str]:
    """Discover OAuth endpoints from the server."""
    discovery_url = urljoin(base_url, "/.well-known/oauth-authorization-server")
    async with httpx.AsyncClient() as client:
        resp = await client.get(discovery_url, headers={"MCP-Protocol-Version": MCP_PROTOCOL_VERSION})
        if resp.status_code == 200:
            data = resp.json()
            return {
                "authorization_endpoint": data["authorization_endpoint"],
                "token_endpoint": data["token_endpoint"],
                "registration_endpoint": data.get("registration_endpoint") or urljoin(base_url, "/register"),
            }
    return {
        "authorization_endpoint": urljoin(base_url, "/authorize"),
        "token_endpoint": urljoin(base_url, "/token"),
        "registration_endpoint": urljoin(base_url, "/register"),
    }


async def dynamic_client_registration(endpoint: str, redirect_uri: str) -> str:
    """Perform OAuth dynamic client registration and return client_id."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            endpoint,
            json={
                "redirect_uris": [redirect_uri],
                "client_name": "mcp-proxy",
                "token_endpoint_auth_method": "none",
            },
        )
        resp.raise_for_status()
        return resp.json()["client_id"]


@contextlib.asynccontextmanager
async def _run_temp_server(app: Starlette) -> contextlib.AsyncIterator[str]:
    """Run a temporary callback server and yield its redirect URI."""
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    try:
        while not server.started:
            await asyncio.sleep(0.01)
        host, port = next(
            iter([sock.getsockname() for s in server.servers for sock in s.sockets])
        )
        yield f"http://{host}:{port}/callback"
    finally:
        server.should_exit = server.force_exit = True
        await task


async def _authorization_flow(metadata: dict[str, str]) -> str:
    """Run the authorization code flow and return an access token."""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()
    auth_code_holder: dict[str, str | None] = {"code": None}
    event = asyncio.Event()

    async def handle_callback(request: Request) -> PlainTextResponse:
        auth_code_holder["code"] = request.query_params.get("code")
        event.set()
        return PlainTextResponse("Authentication complete. You may close this window.")

    app = Starlette(routes=[Route("/callback", handle_callback)])
    async with _run_temp_server(app) as redirect_uri:
        client_id = await dynamic_client_registration(metadata["registration_endpoint"], redirect_uri)
        auth_url = metadata["authorization_endpoint"] + "?" + urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        try:
            import webbrowser

            webbrowser.open(auth_url)
        except Exception:
            print(f"Open the following URL to authenticate: {auth_url}")
        await event.wait()

    code = auth_code_holder["code"]
    if code is None:
        raise RuntimeError("Authorization code not received")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            metadata["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": code_verifier,
            },
        )
        token_resp.raise_for_status()
        return token_resp.json()["access_token"]


async def obtain_access_token(server_url: str) -> str:
    """Obtain an OAuth access token for the given MCP server URL."""
    base_url = authorization_base_url(server_url)
    metadata = await discover_metadata(base_url)
    return await _authorization_flow(metadata)
