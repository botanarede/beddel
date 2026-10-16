"""Tests for the remote Streamable HTTP MCP client (Story 1.1).

Everything runs against ``mcp_fakes.FakeServer`` served through an ``httpx2``
ASGI transport: no network, no real destination, no credential.  Tokens are
generated per test; assertions never print one.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any

import httpx2
import pytest
import yaml
from beddel_protocol_mcp.http_client import (
    ADAPTER_NAME,
    AUTHORIZATION_METHODS,
    MCP_SPECIFICATION_REVISION,
    OPERATOR_COMMAND,
    StreamableHTTPMCPClient,
)
from mcp_fakes import MCP_URL, OTHER_AUTH_HOST, FakeServer, seed_credentials

from beddel.domain.errors import MCPError
from beddel.error_codes import (
    MCP_AUTHORIZATION_REQUIRED,
    MCP_CONNECTION_FAILED,
    MCP_SERVER_TIMEOUT,
    MCP_TOOL_INVOCATION_FAILED,
)

KIT_ROOT = Path(__file__).resolve().parent.parent
SPEC_ROOT = KIT_ROOT.parent.parent / "spec"
PINNED_SDK = "2.3.0"


def _assert_no_secret(fake: FakeServer, *texts: str) -> None:
    for token in fake.issued:
        for text in texts:
            assert token not in text


def _all_log_text(caplog: pytest.LogCaptureFixture) -> str:
    parts: list[str] = []
    for record in caplog.records:
        cause = record.exc_info[1] if record.exc_info else None
        parts.append(f"{record.getMessage()}\n{record.exc_text or ''}\n{cause!r}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# AC 1 - SDK pin and specification revision
# ---------------------------------------------------------------------------


class TestSdkPin:
    def test_manifest_pins_sdk_exactly_in_one_major_line(self) -> None:
        manifest = yaml.safe_load((KIT_ROOT / "kit.yaml").read_text())
        dependencies = manifest["targets"]["python"]["dependencies"]
        assert f"mcp=={PINNED_SDK}" in dependencies
        assert not any(dep.startswith("mcp>=") for dep in dependencies)

    def test_installed_sdk_is_the_pinned_release(self) -> None:
        assert importlib.metadata.version("mcp") == PINNED_SDK

    def test_sdk_python_requirement_is_compatible_with_the_core(self) -> None:
        requires = importlib.metadata.metadata("mcp")["Requires-Python"]
        assert requires == ">=3.10"
        assert sys.version_info >= (3, 12)  # the core's own minimum

    def test_readme_and_manifest_record_pin_and_specification_revision(self) -> None:
        readme = (KIT_ROOT / "README.md").read_text()
        manifest = (KIT_ROOT / "kit.yaml").read_text()
        assert MCP_SPECIFICATION_REVISION == "2026-07-28"
        for text in (readme, manifest):
            assert f"mcp=={PINNED_SDK}" in text
            assert MCP_SPECIFICATION_REVISION in text
        assert ">=3.10" in readme


# ---------------------------------------------------------------------------
# AC 2 - construction and lifecycle
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_constructor_performs_no_io(
        self, monkeypatch: pytest.MonkeyPatch, creds_dir: Path, fake: FakeServer
    ) -> None:
        def forbidden(*_args: Any, **_kwargs: Any) -> None:
            raise AssertionError("I/O during construction")

        monkeypatch.setattr(socket, "socket", forbidden)
        monkeypatch.setattr(os, "open", forbidden)
        monkeypatch.setattr(Path, "mkdir", forbidden)
        monkeypatch.setattr(httpx2.AsyncClient, "__init__", forbidden)
        monkeypatch.setattr(asyncio, "create_task", forbidden)
        for method in AUTHORIZATION_METHODS:
            StreamableHTTPMCPClient(
                transport=ADAPTER_NAME,
                endpoint=MCP_URL,
                authorization=method,
                credentials_dir=creds_dir,
            )
        assert not creds_dir.exists()
        assert fake.seen == []

    def test_constructor_takes_the_entry_fields_by_name(self) -> None:
        client = StreamableHTTPMCPClient(
            transport=ADAPTER_NAME, endpoint=MCP_URL, authorization="none"
        )
        assert "mcp.test/mcp" in repr(client)

    def test_adapter_is_declared_in_manifest_under_a_name(self) -> None:
        manifest = yaml.safe_load((KIT_ROOT / "kit.yaml").read_text())
        adapters = {a["name"]: a for a in manifest["targets"]["python"]["adapters"]}
        declared = adapters[ADAPTER_NAME]
        assert declared["port"] == "IMCPClient"
        assert declared["target"] == "beddel_protocol_mcp.http_client:StreamableHTTPMCPClient"

    def test_manifest_stays_valid_against_schema_and_model(self) -> None:
        import json

        from jsonschema import validate

        from beddel.domain.kit import SolutionKit

        manifest = yaml.safe_load((KIT_ROOT / "kit.yaml").read_text())
        validate(
            manifest, json.loads((SPEC_ROOT / "kits" / "kit-manifest.schema.json").read_text())
        )
        SolutionKit.model_validate(manifest)

    def test_package_exports_the_adapter(self) -> None:
        import beddel_protocol_mcp

        assert beddel_protocol_mcp.StreamableHTTPMCPClient is StreamableHTTPMCPClient

    @pytest.mark.parametrize(
        "method", ["bearer", "basic", "NONE", "OAuth", "", "oauth2", "tok-abc"]
    )
    def test_unknown_authorization_method_raises_without_io(
        self, method: str, fake: FakeServer, creds_dir: Path
    ) -> None:
        with pytest.raises(MCPError) as caught:
            StreamableHTTPMCPClient(
                transport=ADAPTER_NAME,
                endpoint=MCP_URL,
                authorization=method,
                credentials_dir=creds_dir,
                httpx_transport=fake.transport(),
            )
        assert caught.value.code == MCP_CONNECTION_FAILED
        if method:
            assert method not in caught.value.message  # the value is never echoed
        assert fake.seen == []
        assert not creds_dir.exists()

    def test_authorization_has_no_default(self) -> None:
        with pytest.raises(TypeError):
            StreamableHTTPMCPClient(transport=ADAPTER_NAME, endpoint=MCP_URL)  # type: ignore[call-arg]

    def test_wrong_transport_name_is_refused(self) -> None:
        with pytest.raises(MCPError) as caught:
            StreamableHTTPMCPClient(transport="mcp-sse", endpoint=MCP_URL, authorization="none")
        assert caught.value.code == MCP_CONNECTION_FAILED


class TestLifecycle:
    async def test_connects_on_first_call_only(self, make_client: Any, fake: FakeServer) -> None:
        client = make_client("none")
        assert fake.seen == []
        await client.list_tools()
        assert fake.seen
        count = len(fake.seen)
        await client.list_tools()
        assert [s.rpc_method for s in fake.seen].count("initialize") == 1
        assert len(fake.seen) > count

    async def test_concurrent_first_calls_connect_once(
        self, make_client: Any, fake: FakeServer
    ) -> None:
        client = make_client("none")
        await asyncio.gather(client.list_tools(), client.list_tools(), client.list_tools())
        assert [s.rpc_method for s in fake.seen].count("initialize") == 1

    async def test_connect_is_accepted_only_for_the_same_endpoint(
        self, make_client: Any, fake: FakeServer
    ) -> None:
        client = make_client("none")
        with pytest.raises(MCPError) as other:
            await client.connect("https://elsewhere.test/mcp")
        assert other.value.code == MCP_CONNECTION_FAILED
        with pytest.raises(MCPError):
            await client.connect("http://mcp.test/mcp")
        assert fake.seen == []
        await client.connect(MCP_URL)
        assert fake.seen

    async def test_disconnect_is_safe_before_during_and_after_connection(
        self, make_client: Any
    ) -> None:
        client = make_client("none")
        await client.disconnect()
        await client.disconnect()
        await client.list_tools()
        await client.disconnect()
        await client.disconnect()
        assert await client.list_tools()  # reconnects after a disconnect

    async def test_calls_from_one_task_and_disconnect_from_another(self, make_client: Any) -> None:
        client = make_client("none")
        assert await asyncio.create_task(client.list_tools())
        await client.disconnect()

    async def test_cancelled_call_leaves_client_safe_to_disconnect_and_reuse(
        self, make_client: Any, fake: FakeServer
    ) -> None:
        client = make_client("none")
        fake.initialize_delay = 30.0
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(client.list_tools(), timeout=0.3)
        assert time.monotonic() - started < 3.0
        await client.disconnect()
        fake.initialize_delay = 0.0
        assert await client.list_tools()


# ---------------------------------------------------------------------------
# AC 3, 4 - isError and descriptors
# ---------------------------------------------------------------------------


class TestResults:
    async def test_successful_call_returns_content(self, make_client: Any) -> None:
        client = make_client("none")
        content = await client.call_tool("echo", {"message": "hello"})
        assert content[0].text == "hello"

    async def test_is_error_result_raises_and_is_never_returned(
        self, make_client: Any, fake: FakeServer
    ) -> None:
        fake.is_error_result = True
        client = make_client("none")
        with pytest.raises(MCPError) as caught:
            await client.call_tool("echo", {"message": "server-text-must-not-leak"})
        assert caught.value.code == MCP_TOOL_INVOCATION_FAILED
        assert "server-text-must-not-leak" not in str(caught.value)
        assert "server-text-must-not-leak" not in repr(caught.value.details)

    async def test_descriptors_carry_input_schema(
        self, make_client: Any, fake: FakeServer
    ) -> None:
        client = make_client("none")
        tools = await client.list_tools()
        assert tools == [
            {
                "name": "echo",
                "description": "Echo the message",
                "inputSchema": fake.tools[0]["inputSchema"],
            }
        ]
        assert all("input_schema" not in tool for tool in tools)

    def test_port_contract_file_says_input_schema_camel_case(self) -> None:
        import json

        contract = json.loads((SPEC_ROOT / "contracts" / "IMCPClient.json").read_text())
        expectations = "\n".join(contract["behavioral_expectations"])
        assert "inputSchema" in expectations
        assert "input_schema" not in expectations


# ---------------------------------------------------------------------------
# AC 5 - credential binding
# ---------------------------------------------------------------------------


class TestCredentialBinding:
    def test_credentials_are_keyed_by_canonical_endpoint_and_method(self, store: Any) -> None:
        canonical = store.path_for(MCP_URL, "oauth")
        assert store.path_for(MCP_URL, "oauth") == canonical
        assert store.path_for("https://mcp.test/other", "oauth") != canonical
        assert store.path_for("https://other.test/mcp", "oauth") != canonical
        assert store.path_for(MCP_URL, "none") != canonical

    async def test_spellings_of_one_endpoint_share_credentials(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        seed_credentials(fake, store)
        client = make_client("oauth", endpoint="HTTPS://MCP.TEST:443/mcp")
        assert await client.list_tools()

    async def test_token_for_one_endpoint_is_never_presented_to_another(
        self, make_client: Any, fake: FakeServer, store: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        fake.require_token = True
        response = seed_credentials(fake, store, endpoint=MCP_URL)
        other = make_client("oauth", endpoint="https://mcp.test/other-endpoint")
        with pytest.raises(MCPError) as caught:
            await other.list_tools()
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert fake.seen == []  # nothing was sent anywhere
        assert response["access_token"] not in "".join(s.authorization or "" for s in fake.seen)

    async def test_record_moved_to_another_endpoint_is_not_honoured(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        seed_credentials(fake, store, endpoint=MCP_URL)
        other_endpoint = "https://mcp.test/other-endpoint"
        store.path_for(other_endpoint, "oauth").write_bytes(
            store.path_for(MCP_URL, "oauth").read_bytes()
        )
        os.chmod(store.path_for(other_endpoint, "oauth"), 0o600)
        other = make_client("oauth", endpoint=other_endpoint)
        with pytest.raises(MCPError) as caught:
            await other.list_tools()
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert fake.seen == []

    async def test_replacing_the_registration_discards_tokens_of_the_old_issuer(
        self, fake: FakeServer, store: Any
    ) -> None:
        from beddel_protocol_mcp.credentials import FileTokenStorage
        from mcp.shared.auth import OAuthClientInformationFull
        from pydantic import AnyUrl

        seed_credentials(fake, store)
        storage = FileTokenStorage(store, MCP_URL, "oauth")
        assert await storage.get_tokens() is not None
        current = await storage.get_client_info()
        assert current is not None
        replacement = OAuthClientInformationFull(
            client_id="client-new",
            redirect_uris=[AnyUrl("http://127.0.0.1:9/callback")],
            token_endpoint_auth_method="none",
            issuer=f"https://{OTHER_AUTH_HOST}",
        )
        await storage.set_client_info(replacement)
        assert await storage.get_tokens() is None
        assert (await storage.get_client_info()).client_id == "client-new"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# AC 6, 7, 8 - oauth in a run
# ---------------------------------------------------------------------------


class TestOAuthRun:
    async def test_valid_token_call_succeeds_and_token_never_leaks(
        self,
        make_client: Any,
        fake: FakeServer,
        store: Any,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fake.require_token = True
        response = seed_credentials(fake, store)
        caplog.set_level(logging.DEBUG)
        client = make_client("oauth")
        assert await client.list_tools()
        assert (await client.call_tool("echo", {"message": "ok"}))[0].text == "ok"
        presented = [s.authorization for s in fake.mcp_posts() if s.authorization]
        assert presented
        assert all(value == f"Bearer {response['access_token']}" for value in presented)
        captured = capsys.readouterr()
        _assert_no_secret(fake, _all_log_text(caplog), captured.out, captured.err, repr(client))

    async def test_missing_credentials_fail_before_any_request(
        self, make_client: Any, fake: FakeServer, creds_dir: Path
    ) -> None:
        fake.require_token = True
        client = make_client("oauth")
        with pytest.raises(MCPError) as caught:
            await client.call_tool("echo", {"message": "x"})
        error = caught.value
        assert error.code == MCP_AUTHORIZATION_REQUIRED
        assert OPERATOR_COMMAND in error.message
        assert MCP_URL in error.message
        assert fake.seen == []
        assert not creds_dir.exists()  # a run never creates the store

    async def test_revoked_credentials_fail_without_login_registration_or_browser(
        self,
        make_client: Any,
        fake: FakeServer,
        store: Any,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import webbrowser

        def no_browser(*_a: Any, **_k: Any) -> None:
            raise AssertionError("a run opened a browser")

        monkeypatch.setattr(webbrowser, "open", no_browser)
        monkeypatch.setattr("builtins.input", no_browser)
        fake.require_token = True
        response = seed_credentials(fake, store)
        fake.revoke_all()
        caplog.set_level(logging.DEBUG)
        client = make_client("oauth")
        with pytest.raises(MCPError) as caught:
            await client.call_tool("echo", {"message": "x"})
        error = caught.value
        assert error.code == MCP_AUTHORIZATION_REQUIRED
        assert OPERATOR_COMMAND in error.message
        for raw in ("401", "Unauthorized", "Traceback", "www-authenticate", "Bearer"):
            assert raw not in error.message
        assert fake.registrations == 0
        assert "authorization_code" not in fake.token_requests
        captured = capsys.readouterr()
        _assert_no_secret(
            fake,
            str(error),
            repr(error.details),
            _all_log_text(caplog),
            captured.out,
            captured.err,
        )
        assert response["refresh_token"] not in str(error)

    async def test_expired_and_not_refreshable_credentials_fail(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        seed_credentials(fake, store, expires_at=time.time() - 60, with_refresh=False)
        client = make_client("oauth")
        with pytest.raises(MCPError) as caught:
            await client.list_tools()
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert fake.token_requests == []

    async def test_failure_affects_only_that_call(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        seed_credentials(fake, store)
        fake.revoke_all()
        client = make_client("oauth")
        with pytest.raises(MCPError):
            await client.list_tools()
        seed_credentials(fake, store)  # the operator re-authorized
        assert await client.list_tools()

    async def test_unusable_credential_file_permissions_fail_closed(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        seed_credentials(fake, store)
        os.chmod(store.path_for(MCP_URL, "oauth"), 0o644)
        client = make_client("oauth")
        with pytest.raises(MCPError) as caught:
            await client.list_tools()
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert fake.seen == []

    async def test_run_never_registers_a_client_when_the_issuer_changed(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        fake.authorization_server_host = OTHER_AUTH_HOST
        seed_credentials(fake, store)  # registered with the previous issuer
        fake.revoke_all()
        client = make_client("oauth")
        with pytest.raises(MCPError) as caught:
            await client.list_tools()
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert fake.registrations == 0

    async def test_expired_access_token_is_refreshed_and_call_proceeds(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        old = seed_credentials(fake, store, expires_at=time.time() - 60)
        fake.access_tokens.discard(old["access_token"])  # the server rejects the old one
        client = make_client("oauth")
        assert await client.list_tools()
        assert fake.token_requests == ["refresh_token"]
        stored = store.read(MCP_URL, "oauth")
        assert stored is not None and stored.tokens is not None
        assert stored.tokens.access_token != old["access_token"]
        assert stored.expires_at is not None and stored.expires_at > time.time()
        assert old["access_token"] not in "".join(s.authorization or "" for s in fake.seen)

    async def test_failed_refresh_gives_the_same_error_for_that_call_only(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        old = seed_credentials(fake, store, expires_at=time.time() - 60)
        fake.access_tokens.discard(old["access_token"])
        fake.refresh_fails = True
        client = make_client("oauth")
        with pytest.raises(MCPError) as caught:
            await client.list_tools()
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert fake.token_requests == ["refresh_token"]
        fake.refresh_fails = False
        assert await client.list_tools()  # the next call refreshes and works


class TestCredentialsLostAfterConnect:
    """The SDK's auth flow runs inside the transport's POST task once connected."""

    async def test_token_revoked_after_connect_fails_fast_and_next_call_reconnects(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        seed_credentials(fake, store)
        client = make_client("oauth", request_timeout=10.0)
        assert await client.list_tools()
        fake.revoke_all()
        started = time.monotonic()
        with pytest.raises(MCPError) as caught:
            await client.call_tool("echo", {"message": "x"})
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert time.monotonic() - started < 3.0  # well under request_timeout
        assert fake.tool_calls == 0
        assert fake.registrations == 0
        assert "authorization_code" not in fake.token_requests
        seed_credentials(fake, store)  # the operator re-authorized
        assert (await client.call_tool("echo", {"message": "again"}))[0].text == "again"
        assert fake.tool_calls == 1

    async def test_token_expiring_after_connect_with_failing_refresh_fails_fast(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        seed_credentials(fake, store, expires_at=time.time() + 1.0)
        client = make_client("oauth", request_timeout=10.0)
        assert await client.list_tools()
        await asyncio.sleep(1.2)  # the access token is now expired
        fake.refresh_fails = True
        started = time.monotonic()
        with pytest.raises(MCPError) as caught:
            await client.call_tool("echo", {"message": "x"})
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        assert time.monotonic() - started < 3.0
        assert fake.token_requests == ["refresh_token"]
        assert fake.tool_calls == 0
        assert fake.registrations == 0
        fake.refresh_fails = False
        assert await client.call_tool("echo", {"message": "ok"})  # next call refreshes


# ---------------------------------------------------------------------------
# none rules (decision D-11)
# ---------------------------------------------------------------------------


class TestNoneMethod:
    async def test_none_against_an_open_server_sends_no_credentials(
        self, make_client: Any, fake: FakeServer
    ) -> None:
        client = make_client("none")
        assert await client.list_tools()
        assert all(s.authorization is None for s in fake.seen)
        assert {s.path for s in fake.seen} == {"/mcp"}  # no discovery, no OAuth endpoint

    @pytest.mark.parametrize("status", [401, 403])
    async def test_none_never_bypasses_authentication_the_server_requires(
        self,
        status: int,
        make_client: Any,
        fake: FakeServer,
        store: Any,
        creds_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import webbrowser

        def no_browser(*_a: Any, **_k: Any) -> None:
            raise AssertionError("none started a login")

        monkeypatch.setattr(webbrowser, "open", no_browser)
        fake.require_token = True
        fake.challenge_status = status
        seed_credentials(fake, store)  # stored credentials exist, but not for method none
        client = make_client("none")
        with pytest.raises(MCPError) as caught:
            await client.call_tool("echo", {"message": "x"})
        error = caught.value
        assert error.code == MCP_AUTHORIZATION_REQUIRED
        assert "'none'" in error.message
        # exactly one request, no retry, no discovery, no login, no other credentials
        assert len(fake.seen) == 1
        assert fake.seen[0].authorization is None
        assert fake.registrations == 0 and fake.token_requests == []
        assert fake.tool_calls == 0

    async def test_none_does_not_touch_the_credential_store(
        self, make_client: Any, fake: FakeServer, creds_dir: Path
    ) -> None:
        fake.require_token = True
        client = make_client("none")
        with pytest.raises(MCPError):
            await client.list_tools()
        assert not creds_dir.exists()


# ---------------------------------------------------------------------------
# AC 10 - endpoint validation
# ---------------------------------------------------------------------------


class TestEndpointValidation:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "http://example.com/mcp",
            "ftp://example.com/mcp",
            "https://user:pw-secret@example.com/mcp",
            "https://user@example.com/mcp",
            "https://example.com/mcp?token=query-secret",
            "https://example.com/mcp?x=1",
            "https://example.com/mcp#fragment-secret",
            "https://example.com:99999/mcp",
            "https://example.com/m cp",
            "https://",
            "example.com/mcp",
            "",
        ],
    )
    def test_refused_before_connecting_without_echoing_the_value(
        self, endpoint: str, fake: FakeServer
    ) -> None:
        with pytest.raises(MCPError) as caught:
            StreamableHTTPMCPClient(
                ADAPTER_NAME, endpoint, "none", httpx_transport=fake.transport()
            )
        assert caught.value.code == MCP_CONNECTION_FAILED
        for secret in ("pw-secret", "query-secret", "fragment-secret"):
            assert secret not in str(caught.value)
        assert fake.seen == []

    def test_plain_http_is_refused_even_on_loopback_unless_the_code_opts_in(self) -> None:
        with pytest.raises(MCPError):
            StreamableHTTPMCPClient(ADAPTER_NAME, "http://127.0.0.1:8080/mcp", "none")
        StreamableHTTPMCPClient(
            ADAPTER_NAME, "http://127.0.0.1:8080/mcp", "none", allow_insecure_loopback=True
        )
        with pytest.raises(MCPError):  # the opt-in never covers a non-loopback host
            StreamableHTTPMCPClient(
                ADAPTER_NAME, "http://example.com/mcp", "none", allow_insecure_loopback=True
            )


# ---------------------------------------------------------------------------
# AC 11 - timeouts, unavailability, retries
# ---------------------------------------------------------------------------


class _Refusing(httpx2.AsyncBaseTransport):
    def __init__(self) -> None:
        self.attempts = 0

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        self.attempts += 1
        raise httpx2.ConnectError("refused", request=request)


class _FailingRefresh(httpx2.AsyncBaseTransport):
    """Serves the fake, but times out on any refresh-token grant."""

    def __init__(self, inner: httpx2.AsyncBaseTransport) -> None:
        self.inner = inner
        self.refresh_attempts = 0

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        if b"grant_type=refresh_token" in request.content:
            self.refresh_attempts += 1
            raise httpx2.ReadTimeout("timed out", request=request)
        return await self.inner.handle_async_request(request)


class TestFailureSemantics:
    async def test_unreachable_server_fails_with_connection_error_after_bounded_retries(
        self, make_client: Any
    ) -> None:
        refusing = _Refusing()
        client = make_client("none", httpx_transport=refusing, max_connect_retries=2)
        with pytest.raises(MCPError) as caught:
            await client.list_tools()
        assert caught.value.code == MCP_CONNECTION_FAILED
        assert refusing.attempts == 3  # first attempt + 2 retries, then stop
        assert "refused" not in caught.value.message  # no raw transport text

    async def test_silent_server_fails_within_a_finite_timeout(
        self, make_client: Any, fake: FakeServer
    ) -> None:
        fake.silent = True
        client = make_client("none", connect_timeout=0.2, max_connect_retries=1)
        started = time.monotonic()
        with pytest.raises(MCPError) as caught:
            await client.list_tools()
        assert caught.value.code == MCP_SERVER_TIMEOUT
        assert time.monotonic() - started < 5.0

    async def test_slow_tool_call_times_out_and_is_never_retried(
        self, make_client: Any, fake: FakeServer
    ) -> None:
        client = make_client("none", request_timeout=0.3)
        await client.list_tools()
        fake.call_delay = 30.0
        with pytest.raises(MCPError) as caught:
            await client.call_tool("echo", {"message": "x"})
        assert caught.value.code == MCP_SERVER_TIMEOUT
        assert [s.rpc_method for s in fake.seen].count("tools/call") == 1

    async def test_failed_tool_call_is_not_retried(
        self, make_client: Any, fake: FakeServer
    ) -> None:
        client = make_client("none")
        await client.list_tools()
        fake.fail_status = 503
        with pytest.raises(MCPError) as caught:
            await client.call_tool("echo", {"message": "x"})
        assert caught.value.code == MCP_TOOL_INVOCATION_FAILED
        assert [s.rpc_method for s in fake.seen].count("tools/call") == 1

    async def test_attempt_that_sent_a_refresh_request_is_not_retried(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        old = seed_credentials(fake, store, expires_at=time.time() - 60)
        fake.access_tokens.discard(old["access_token"])
        transport = _FailingRefresh(fake.transport())
        client = make_client("oauth", httpx_transport=transport, max_connect_retries=3)
        with pytest.raises(MCPError) as caught:
            await client.list_tools()
        assert caught.value.code == MCP_SERVER_TIMEOUT
        assert transport.refresh_attempts == 1  # a rotating refresh token is never resent

    async def test_oauth_attempt_that_never_refreshed_is_still_retried(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        seed_credentials(fake, store)
        refusing = _Refusing()
        client = make_client("oauth", httpx_transport=refusing, max_connect_retries=2)
        with pytest.raises(MCPError) as caught:
            await client.list_tools()
        assert caught.value.code == MCP_CONNECTION_FAILED
        assert refusing.attempts == 3

    async def test_error_classes_are_distinct(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        codes: set[str] = set()
        refusing = make_client("none", httpx_transport=_Refusing(), max_connect_retries=0)
        with pytest.raises(MCPError) as connection:
            await refusing.list_tools()
        codes.add(connection.value.code)
        fake.silent = True
        silent = make_client("none", connect_timeout=0.2, max_connect_retries=0)
        with pytest.raises(MCPError) as timeout:
            await silent.list_tools()
        codes.add(timeout.value.code)
        fake.silent = False
        fake.require_token = True
        protected = make_client("none")
        with pytest.raises(MCPError) as authorization:
            await protected.list_tools()
        codes.add(authorization.value.code)
        fake.require_token = False
        fake.is_error_result = True
        failing = make_client("none")
        with pytest.raises(MCPError) as tool:
            await failing.call_tool("echo", {"message": "x"})
        codes.add(tool.value.code)
        assert codes == {
            MCP_CONNECTION_FAILED,
            MCP_SERVER_TIMEOUT,
            MCP_AUTHORIZATION_REQUIRED,
            MCP_TOOL_INVOCATION_FAILED,
        }


# ---------------------------------------------------------------------------
# No SDK or transport exception stays chained to what the client raises
# ---------------------------------------------------------------------------


def _unchained(error: BaseException) -> None:
    """SDK/transport exceptions can quote response text; none may stay reachable."""
    assert error.__context__ is None
    assert error.__cause__ is None


class TestNoChainedExceptions:
    async def test_authorization_required_on_connect_is_unchained(
        self, make_client: Any, fake: FakeServer
    ) -> None:
        fake.require_token = True
        with pytest.raises(MCPError) as none_method:
            await make_client("none").list_tools()
        assert none_method.value.code == MCP_AUTHORIZATION_REQUIRED
        _unchained(none_method.value)
        with pytest.raises(MCPError) as no_credentials:
            await make_client("oauth").list_tools()
        assert no_credentials.value.code == MCP_AUTHORIZATION_REQUIRED
        _unchained(no_credentials.value)

    async def test_authorization_required_on_a_live_connection_is_unchained(
        self, make_client: Any, fake: FakeServer, store: Any
    ) -> None:
        fake.require_token = True
        seed_credentials(fake, store)
        client = make_client("oauth")
        await client.list_tools()
        fake.revoke_all()
        with pytest.raises(MCPError) as caught:
            await client.call_tool("echo", {"message": "x"})
        assert caught.value.code == MCP_AUTHORIZATION_REQUIRED
        _unchained(caught.value)

    async def test_timeouts_are_unchained(self, make_client: Any, fake: FakeServer) -> None:
        fake.silent = True
        with pytest.raises(MCPError) as connecting:
            await make_client("none", connect_timeout=0.2, max_connect_retries=0).list_tools()
        assert connecting.value.code == MCP_SERVER_TIMEOUT
        _unchained(connecting.value)
        fake.silent = False
        client = make_client("none", request_timeout=0.3)
        await client.list_tools()
        fake.call_delay = 30.0
        with pytest.raises(MCPError) as calling:
            await client.call_tool("echo", {"message": "x"})
        assert calling.value.code == MCP_SERVER_TIMEOUT
        _unchained(calling.value)

    async def test_connection_and_server_errors_are_unchained(
        self, make_client: Any, fake: FakeServer
    ) -> None:
        refusing = make_client("none", httpx_transport=_Refusing(), max_connect_retries=1)
        with pytest.raises(MCPError) as connecting:
            await refusing.list_tools()
        assert connecting.value.code == MCP_CONNECTION_FAILED
        _unchained(connecting.value)
        client = make_client("none")
        await client.list_tools()
        fake.fail_status = 503
        with pytest.raises(MCPError) as calling:
            await client.call_tool("echo", {"message": "x"})
        assert calling.value.code == MCP_TOOL_INVOCATION_FAILED
        _unchained(calling.value)

    def test_refused_endpoint_and_corrupt_record_are_unchained(
        self, fake: FakeServer, store: Any
    ) -> None:
        from beddel_protocol_mcp.credentials import CredentialStoreError

        with pytest.raises(MCPError) as refused:
            StreamableHTTPMCPClient(ADAPTER_NAME, "https://example.com:99999/mcp", "none")
        _unchained(refused.value)
        seed_credentials(fake, store)
        path = store.path_for(MCP_URL, "oauth")
        path.write_text('{"tokens": {"access_token": 7')
        os.chmod(path, 0o600)
        with pytest.raises(CredentialStoreError) as corrupt:
            store.read(MCP_URL, "oauth")
        _unchained(corrupt.value)


# ---------------------------------------------------------------------------
# AC 13 - known asymmetry recorded
# ---------------------------------------------------------------------------


class TestKnownAsymmetry:
    def test_readme_records_the_sse_typescript_asymmetry(self) -> None:
        readme = (KIT_ROOT / "README.md").read_text()
        assert "Known asymmetry" in readme
        assert "mcp-sse-client.ts" in readme

    def test_no_typescript_sse_adapter_is_declared(self) -> None:
        manifest = yaml.safe_load((KIT_ROOT / "kit.yaml").read_text())
        targets = [a["target"] for a in manifest["targets"]["typescript"]["adapters"]]
        assert targets == ["./src/mcp-stdio-client.ts:MCPStdioClient"]
