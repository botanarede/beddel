"""Configure sys.path for standalone kit test execution.

Adds the kit's ``python/`` directory (the package lives there since the kit
layout moved from ``src/`` to ``python/``) to sys.path so
``import beddel_protocol_mcp`` resolves.  The ``beddel`` SDK itself must be
installed (``pip install beddel``).

Also provides the fixtures of the Streamable HTTP client tests (an in-process
fake MCP server and OAuth stub; no network, no credential).
"""

import sys
from pathlib import Path

import pytest

_KIT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_KIT_ROOT / "python"))


@pytest.fixture
def fake():
    """A fresh fake MCP server + OAuth stub."""
    from mcp_fakes import FakeServer

    return FakeServer()


@pytest.fixture
def creds_dir(tmp_path: Path) -> Path:
    """A credential directory outside any repository (pytest's tmp dir)."""
    return tmp_path / "credentials"


@pytest.fixture
def store(creds_dir: Path):
    from beddel_protocol_mcp.credentials import CredentialStore

    return CredentialStore(creds_dir)


@pytest.fixture
async def make_client(fake, creds_dir):
    """Factory for clients wired to the fake; all are disconnected at teardown."""
    from beddel_protocol_mcp.http_client import ADAPTER_NAME, StreamableHTTPMCPClient
    from mcp_fakes import MCP_URL

    created: list[StreamableHTTPMCPClient] = []

    def factory(authorization: str = "oauth", **kwargs):
        options = {
            "httpx_transport": fake.transport(),
            "credentials_dir": creds_dir,
            "retry_backoff": 0.01,
            "connect_timeout": 5.0,
            "request_timeout": 5.0,
        }
        options.update(kwargs)
        endpoint = options.pop("endpoint", MCP_URL)
        client = StreamableHTTPMCPClient(ADAPTER_NAME, endpoint, authorization, **options)
        created.append(client)
        return client

    yield factory
    for client in created:
        await client.disconnect()
