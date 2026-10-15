"""Tests for the operator authorization entry point (Story 1.1, AC 9).

The browser is replaced by a coroutine that plays the user agent: it reads the
authorization URL the SDK built and calls the redirect back on the loopback
callback server the command started.  The authorization server is the OAuth
stub of ``mcp_fakes``; no network, no credential, no real browser.
"""

from __future__ import annotations

import asyncio
import logging
import os
import stat
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from beddel_protocol_mcp.authorize import LOOPBACK_HOST, _CallbackServer, authorize, main
from beddel_protocol_mcp.credentials import CredentialStore
from mcp_fakes import AUTH_HOST, MCP_URL, FakeServer

from beddel.domain.errors import MCPError
from beddel.error_codes import MCP_AUTHORIZATION_REQUIRED, MCP_CONNECTION_FAILED

KIT_ROOT = Path(__file__).resolve().parent.parent


def _tokens_stored(store: CredentialStore) -> bool:
    record = store.read(MCP_URL, "oauth")
    return record is not None and record.tokens is not None


@pytest.fixture(autouse=True)
def _protected_server(fake: FakeServer) -> None:
    """Every operator test targets a server that demands authorization."""
    fake.require_token = True


def _user_agent(fake: FakeServer, urls: list[str], *, mode: str = "approve") -> Any:
    """Return an ``open_url`` coroutine that plays the user approving (or not)."""

    async def open_url(url: str) -> None:
        urls.append(url)
        if mode == "ignore":
            return
        query = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        redirect = query["redirect_uri"]
        if mode == "deny":
            target = f"{redirect}?error=access_denied&state={query['state']}"
        else:
            code = fake.new_code(query["code_challenge"])
            state = "forged-state" if mode == "bad-state" else query["state"]
            target = f"{redirect}?code={code}&state={state}&iss=https://{AUTH_HOST}"
        async with httpx2.AsyncClient(trust_env=False) as browser:
            await browser.get(target)

    return open_url


async def _run(fake: FakeServer, store: CredentialStore, mode: str = "approve", **kwargs: Any):
    urls: list[str] = []
    lines: list[str] = []
    await authorize(
        MCP_URL,
        store=store,
        open_url=_user_agent(fake, urls, mode=mode),
        httpx_transport=fake.transport(),
        echo=lines.append,
        timeout=kwargs.pop("timeout", 20.0),
        **kwargs,
    )
    return urls, lines


class TestOperatorAuthorization:
    async def test_flow_stores_owner_only_credentials_and_prints_no_secret(
        self,
        fake: FakeServer,
        store: CredentialStore,
        creds_dir: Path,
        make_client: Any,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fake.require_token = True
        caplog.set_level(logging.DEBUG)

        def no_chmod(*_a: Any, **_k: Any) -> None:
            raise AssertionError("permissions were changed after creation")

        previous = os.umask(0)  # prove the 0600 is requested at creation, not inherited
        try:
            monkeypatch.setattr(os, "chmod", no_chmod)
            monkeypatch.setattr(os, "fchmod", no_chmod, raising=False)
            urls, lines = await _run(fake, store)
        finally:
            os.umask(previous)

        record = store.path_for(MCP_URL, "oauth")
        assert stat.S_IMODE(record.stat().st_mode) == 0o600
        assert stat.S_IMODE(creds_dir.stat().st_mode) == 0o700
        assert sorted(p.name for p in creds_dir.iterdir()) == [record.name]  # no temp files left
        assert fake.registrations == 1 and fake.token_requests == ["authorization_code"]
        printed = "\n".join(lines) + capsys.readouterr().out
        logged = "\n".join(r.getMessage() for r in caplog.records)
        for token in fake.issued:
            assert token not in printed and token not in logged
        assert "Authorization stored" in printed
        # the credentials work in a run
        client = make_client("oauth")
        assert await client.list_tools()
        assert urls  # the operator was handed an authorization URL

    async def test_redirect_is_received_on_the_loopback_address_only(
        self, fake: FakeServer, store: CredentialStore
    ) -> None:
        urls, _ = await _run(fake, store)
        redirect = parse_qs(urlsplit(urls[0]).query)["redirect_uri"][0]
        parts = urlsplit(redirect)
        assert parts.scheme == "http" and parts.hostname == LOOPBACK_HOST
        assert parts.path == "/callback"

    async def test_callback_server_is_bound_explicitly_to_127_0_0_1(self) -> None:
        server = _CallbackServer(0)
        port = await server.start()
        try:
            assert server.sockname_hosts == [LOOPBACK_HOST]
            async with httpx2.AsyncClient(trust_env=False) as client:
                other = await client.get(f"http://{LOOPBACK_HOST}:{port}/not-the-callback")
                assert other.status_code == 404
                post = await client.post(f"http://{LOOPBACK_HOST}:{port}/callback", content=b"x")
                assert post.status_code == 404
                ok = await client.get(f"http://{LOOPBACK_HOST}:{port}/callback?code=c&state=s")
                assert ok.status_code == 200
            assert await server.wait(1.0) == {"code": "c", "state": "s"}
        finally:
            await server.close()

    async def test_refresh_after_operator_flow_uses_the_discovered_token_endpoint(
        self, fake: FakeServer, store: CredentialStore, make_client: Any
    ) -> None:
        fake.require_token = True
        await _run(fake, store)
        stored = store.read(MCP_URL, "oauth")
        assert stored is not None and stored.tokens is not None
        assert stored.oauth_metadata is not None
        stored.expires_at = time.time() - 60  # the access token is now expired
        fake.access_tokens.discard(stored.tokens.access_token)
        store.write(MCP_URL, "oauth", stored)
        assert await make_client("oauth").list_tools()
        assert fake.token_requests == ["authorization_code", "refresh_token"]

    @pytest.mark.parametrize("mode", ["deny", "bad-state"])
    async def test_denied_or_forged_redirect_stores_nothing(
        self, mode: str, fake: FakeServer, store: CredentialStore
    ) -> None:
        with pytest.raises(MCPError) as caught:
            await _run(fake, store, mode=mode)
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert "forged-state" not in str(caught.value)
        assert not _tokens_stored(store)

    @pytest.mark.parametrize("mode", ["deny", "bad-state", "ignore"])
    async def test_failed_flow_leaves_no_sdk_exception_chained(
        self, mode: str, fake: FakeServer, store: CredentialStore
    ) -> None:
        # The SDK's own errors quote the state / token-exchange text; none may
        # stay reachable from the error the command raises.
        with pytest.raises(MCPError) as caught:
            await _run(fake, store, mode=mode, timeout=0.3)
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert caught.value.__context__ is None
        assert caught.value.__cause__ is None

    async def test_unusable_credential_store_error_is_unchained_too(
        self, fake: FakeServer
    ) -> None:
        inside = KIT_ROOT / "tests" / "_credentials_must_not_exist"
        with pytest.raises(MCPError) as caught:
            await _run(fake, CredentialStore(inside))
        assert caught.value.__context__ is None
        assert caught.value.__cause__ is None

    async def test_no_redirect_within_the_timeout_fails_and_stores_nothing(
        self, fake: FakeServer, store: CredentialStore
    ) -> None:
        started = time.monotonic()
        with pytest.raises(MCPError) as caught:
            await _run(fake, store, mode="ignore", timeout=0.3)
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert time.monotonic() - started < 15.0
        assert not _tokens_stored(store)

    async def test_credentials_are_never_written_inside_a_repository(
        self, fake: FakeServer
    ) -> None:
        inside = KIT_ROOT / "tests" / "_credentials_must_not_exist"
        with pytest.raises(MCPError) as caught:
            await _run(fake, CredentialStore(inside))
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert "repository" in caught.value.message
        assert not inside.exists()

    async def test_only_the_oauth_method_has_a_flow(self, fake: FakeServer, store: Any) -> None:
        with pytest.raises(MCPError) as caught:
            await authorize(MCP_URL, authorization="none", store=store)
        assert caught.value.code == MCP_CONNECTION_FAILED

    async def test_endpoint_rules_apply_to_the_operator_command(self, store: Any) -> None:
        with pytest.raises(MCPError) as caught:
            await authorize("http://example.com/mcp", store=store)
        assert caught.value.code == MCP_CONNECTION_FAILED

    def test_command_line_refuses_an_insecure_endpoint_with_exit_code_1(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--endpoint", "http://example.com/mcp?token=cli-secret"]) == 1
        err = capsys.readouterr().err
        assert "cli-secret" not in err and "BEDDEL-MCP-600" in err

    def test_command_line_is_a_kit_module_not_a_beddel_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exit_info:
            main(["--help"])
        assert exit_info.value.code == 0
        assert "python -m beddel_protocol_mcp.authorize" in capsys.readouterr().out
        assert asyncio.iscoroutinefunction(authorize)
