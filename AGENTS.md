# AGENTS instructions

This repository implements a proxy for Model Context Protocol (MCP) servers.
It is written in Python and exposes a CLI executable `mcp-proxy`.

The code is organised as follows:

- `src/mcp_proxy/`
  - `__main__.py` – application entry point parsing command line arguments and starting either an SSE client or SSE server.
  - `mcp_server.py` – spawns an SSE/Streamable HTTP server that proxies to local stdio MCP servers.
  - `proxy_server.py` – creates an MCP server which forwards requests to a remote MCP client session.
  - `sse_client.py` and `streamablehttp_client.py` – run local stdio servers that proxy to remote endpoints over SSE or Streamable HTTP.
  - `oauth.py` – helper functions for OAuth authentication.
  - `config_loader.py` – loads named server definitions from a JSON configuration file.
  - `sse_client.py` / `streamablehttp_client.py` – implement client modes connecting to remote servers.
- `tests/` – `pytest` test suite covering the modules above.
- `config_example.json` – example configuration for named servers used by tests.

## Running tests

Install the package with development tools and run `pytest`:

```bash
pip install -e .
pip install pytest pytest-asyncio
pytest
```

Some tests currently fail when executed in this environment but running them is recommended.

## File cross references

Instructions for both automated agents and human contributors are maintained
here and in `CLAUDE.md`. The `CLAUDE.md` file simply refers back to this
`AGENTS.md` so both files stay in sync.
