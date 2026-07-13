"""Unit tests for KiroCLIAgentAdapter headless mode (Story K1.16).

Tests headless detection, trust_tools configuration, binary discovery,
and the interaction between headless mode and sandbox parameters.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from beddel_agent_kiro.adapter import _DEFAULT_CLI_PATH, KiroCLIAgentAdapter

from beddel.domain.errors import AgentError
from beddel.error_codes import AGENT_EXECUTION_FAILED

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROMPT = "Deploy the application"
_PATCH_EXEC = "beddel_agent_kiro.adapter.asyncio.create_subprocess_exec"
_PATCH_WHICH = "beddel_agent_kiro.adapter.shutil.which"
_PATCH_SUBPROCESS_RUN = "beddel_agent_kiro.adapter.subprocess.run"
_PATCH_PATH_EXISTS = "beddel_agent_kiro.adapter._DEFAULT_CLI_PATH"


def _make_mock_process(
    *,
    stdout: bytes = b"Done!",
    stderr: bytes = b"",
    returncode: int = 0,
) -> AsyncMock:
    """Build a mock async subprocess process object."""
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


# ===================================================================
# Headless Mode Detection (AC 1, 3, 7)
# ===================================================================


class TestHeadlessModeDetection:
    """Test that headless mode is activated/deactivated correctly."""

    def test_headless_active_via_api_key_param(self) -> None:
        """AC #3: explicit api_key activates headless."""
        adapter = KiroCLIAgentAdapter(
            api_key="kiro-test-key-123",
            cli_path=_DEFAULT_CLI_PATH,
        )
        assert adapter._headless is True

    def test_headless_active_via_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC #1: KIRO_API_KEY env var activates headless."""
        monkeypatch.setenv("KIRO_API_KEY", "kiro-env-key-456")
        adapter = KiroCLIAgentAdapter(cli_path=_DEFAULT_CLI_PATH)
        assert adapter._headless is True

    def test_headless_inactive_when_no_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC #7: no key means SSO mode (headless=False)."""
        monkeypatch.delenv("KIRO_API_KEY", raising=False)
        adapter = KiroCLIAgentAdapter(cli_path=_DEFAULT_CLI_PATH)
        assert adapter._headless is False

    def test_explicit_api_key_overrides_empty_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit api_key works even when env var is not set."""
        monkeypatch.delenv("KIRO_API_KEY", raising=False)
        adapter = KiroCLIAgentAdapter(
            api_key="explicit-key",
            cli_path=_DEFAULT_CLI_PATH,
        )
        assert adapter._headless is True

    def test_trust_tools_stored(self) -> None:
        """trust_tools parameter is stored for command building."""
        adapter = KiroCLIAgentAdapter(
            api_key="key",
            trust_tools=["read", "grep"],
            cli_path=_DEFAULT_CLI_PATH,
        )
        assert adapter._trust_tools == ["read", "grep"]

    def test_trust_tools_none_by_default(self) -> None:
        """trust_tools defaults to None."""
        adapter = KiroCLIAgentAdapter(cli_path=_DEFAULT_CLI_PATH)
        assert adapter._trust_tools is None


# ===================================================================
# _build_command() in Headless Mode (AC 2, 4, 6, 8)
# ===================================================================


class TestBuildCommandHeadless:
    """Test command building when headless mode is active."""

    def test_headless_trust_all_tools_default(self) -> None:
        """AC #2: headless with trust_tools=None appends --trust-all-tools."""
        adapter = KiroCLIAgentAdapter(
            api_key="key",
            trust_tools=None,
            cli_path=_DEFAULT_CLI_PATH,
        )
        cmd = adapter._build_command(
            _PROMPT, model="claude-sonnet-4.6", sandbox="read-only", tools=None
        )
        assert "--trust-all-tools" in cmd
        assert "--trust-tools=" not in cmd
        assert "-a" not in cmd

    def test_headless_explicit_trust_tools(self) -> None:
        """AC #4: headless with trust_tools=["read","grep"] uses --trust-tools=read,grep."""
        adapter = KiroCLIAgentAdapter(
            api_key="key",
            trust_tools=["read", "grep"],
            cli_path=_DEFAULT_CLI_PATH,
        )
        cmd = adapter._build_command(
            _PROMPT, model="claude-sonnet-4.6", sandbox="read-only", tools=None
        )
        assert "--trust-tools=read,grep" in cmd
        assert "--trust-all-tools" not in cmd

    def test_headless_overrides_sandbox_read_only(self) -> None:
        """AC #6: in headless, sandbox='read-only' still gets --trust-all-tools."""
        adapter = KiroCLIAgentAdapter(
            api_key="key",
            trust_tools=None,
            cli_path=_DEFAULT_CLI_PATH,
        )
        cmd = adapter._build_command(
            _PROMPT, model="claude-sonnet-4.6", sandbox="read-only", tools=None
        )
        # Sandbox would normally add --trust-tools= (empty), but headless overrides
        assert "--trust-all-tools" in cmd
        assert "--trust-tools=" not in [c for c in cmd if c == "--trust-tools="]

    def test_headless_overrides_sandbox_workspace_write(self) -> None:
        """In headless, sandbox='workspace-write' does NOT add -a."""
        adapter = KiroCLIAgentAdapter(
            api_key="key",
            trust_tools=["read", "write", "shell"],
            cli_path=_DEFAULT_CLI_PATH,
        )
        cmd = adapter._build_command(
            _PROMPT, model="claude-sonnet-4.6", sandbox="workspace-write", tools=None
        )
        assert "-a" not in cmd
        assert "--trust-tools=read,write,shell" in cmd

    def test_headless_no_interactive_flag_present(self) -> None:
        """AC #2: --no-interactive is always present."""
        adapter = KiroCLIAgentAdapter(
            api_key="key",
            cli_path=_DEFAULT_CLI_PATH,
        )
        cmd = adapter._build_command(
            _PROMPT, model="claude-sonnet-4.6", sandbox="read-only", tools=None
        )
        assert "--no-interactive" in cmd

    def test_headless_unknown_sandbox_does_not_raise(self) -> None:
        """In headless mode, unknown sandbox values are silently ignored."""
        adapter = KiroCLIAgentAdapter(
            api_key="key",
            cli_path=_DEFAULT_CLI_PATH,
        )
        # Should NOT raise even with weird sandbox value
        cmd = adapter._build_command(
            _PROMPT, model="claude-sonnet-4.6", sandbox="unknown-mode", tools=None
        )
        assert "--trust-all-tools" in cmd

    @pytest.mark.asyncio
    async def test_kiro_api_key_not_in_command(self) -> None:
        """AC #8: KIRO_API_KEY never appears in the command list."""
        adapter = KiroCLIAgentAdapter(
            api_key="super-secret-key-12345",
            cli_path=_DEFAULT_CLI_PATH,
        )
        mock_proc = _make_mock_process()

        with patch(_PATCH_EXEC, return_value=mock_proc) as mock_exec:
            await adapter.execute(_PROMPT)
            call_args = mock_exec.call_args[0]
            cmd_str = " ".join(str(a) for a in call_args)
            assert "super-secret-key-12345" not in cmd_str
            assert "KIRO_API_KEY" not in cmd_str


# ===================================================================
# SSO Mode Preserved (AC 7)
# ===================================================================


class TestSsoModePreserved:
    """Verify existing SSO behavior is unchanged when no API key is set."""

    def test_sso_sandbox_read_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SSO mode: read-only still produces --trust-tools= (empty)."""
        monkeypatch.delenv("KIRO_API_KEY", raising=False)
        adapter = KiroCLIAgentAdapter(cli_path=_DEFAULT_CLI_PATH)
        cmd = adapter._build_command(
            _PROMPT, model="claude-sonnet-4.6", sandbox="read-only", tools=None
        )
        assert "--trust-tools=" in cmd
        assert "--trust-all-tools" not in cmd

    def test_sso_sandbox_workspace_write(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SSO mode: workspace-write still produces -a."""
        monkeypatch.delenv("KIRO_API_KEY", raising=False)
        adapter = KiroCLIAgentAdapter(cli_path=_DEFAULT_CLI_PATH)
        cmd = adapter._build_command(
            _PROMPT, model="claude-sonnet-4.6", sandbox="workspace-write", tools=None
        )
        assert "-a" in cmd
        assert "--trust-all-tools" not in cmd

    def test_sso_unknown_sandbox_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SSO mode: unknown sandbox still raises AgentError."""
        monkeypatch.delenv("KIRO_API_KEY", raising=False)
        adapter = KiroCLIAgentAdapter(cli_path=_DEFAULT_CLI_PATH)
        with pytest.raises(AgentError) as exc_info:
            adapter._build_command(
                _PROMPT, model="claude-sonnet-4.6", sandbox="invalid", tools=None
            )
        assert exc_info.value.code == AGENT_EXECUTION_FAILED


# ===================================================================
# Binary Discovery (AC 5)
# ===================================================================


class TestBinaryDiscovery:
    """Test the _discover_cli() static method."""

    def test_discovery_default_path_exists(self, tmp_path: Path) -> None:
        """Step 1: default path found."""
        fake_cli = tmp_path / "kiro-cli"
        fake_cli.touch()
        with patch("beddel_agent_kiro.adapter._DEFAULT_CLI_PATH", fake_cli):
            result = KiroCLIAgentAdapter._discover_cli()
        assert result == fake_cli

    def test_discovery_which_fallback(self, tmp_path: Path) -> None:
        """Step 2: shutil.which finds it on PATH."""
        fake_default = tmp_path / "nonexistent" / "kiro-cli"
        found_path = "/usr/bin/kiro-cli"
        with (
            patch("beddel_agent_kiro.adapter._DEFAULT_CLI_PATH", fake_default),
            patch(_PATCH_WHICH, return_value=found_path),
        ):
            result = KiroCLIAgentAdapter._discover_cli()
        assert result == Path(found_path)

    def test_discovery_auto_install_success(self, tmp_path: Path) -> None:
        """Step 3: auto-install succeeds and binary appears at default path."""
        fake_default = tmp_path / "kiro-cli"
        # Initially does not exist
        call_count = 0

        def _exists_side_effect() -> bool:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False  # First check: not found
            fake_default.touch()
            return True  # After install: found

        mock_path = MagicMock(spec=Path)
        mock_path.exists = _exists_side_effect
        mock_path.__str__ = lambda _: str(fake_default)
        mock_path.__fspath__ = lambda _: str(fake_default)
        mock_path.__eq__ = lambda self, other: str(self) == str(other)
        mock_path.__hash__ = lambda _: hash(str(fake_default))

        with (
            patch("beddel_agent_kiro.adapter._DEFAULT_CLI_PATH", fake_default),
            patch(_PATCH_WHICH, return_value=None),
            patch(_PATCH_SUBPROCESS_RUN) as mock_run,
        ):
            # Make the path exist after subprocess.run is called
            def side_effect(*args: Any, **kwargs: Any) -> MagicMock:
                fake_default.touch()
                return MagicMock(returncode=0)

            mock_run.side_effect = side_effect
            result = KiroCLIAgentAdapter._discover_cli()

        assert result == fake_default
        mock_run.assert_called_once()

    def test_discovery_all_fail_raises(self, tmp_path: Path) -> None:
        """Step 4: all discovery steps fail, raises AgentError."""
        fake_default = tmp_path / "nonexistent" / "kiro-cli"
        with (
            patch("beddel_agent_kiro.adapter._DEFAULT_CLI_PATH", fake_default),
            patch(_PATCH_WHICH, return_value=None),
            patch(_PATCH_SUBPROCESS_RUN) as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            with pytest.raises(AgentError) as exc_info:
                KiroCLIAgentAdapter._discover_cli()

        assert exc_info.value.code == AGENT_EXECUTION_FAILED
        assert "kiro-cli not found" in exc_info.value.message

    def test_discovery_auto_install_timeout(self, tmp_path: Path) -> None:
        """Auto-install times out gracefully."""
        import subprocess as sp

        fake_default = tmp_path / "nonexistent" / "kiro-cli"
        with (
            patch("beddel_agent_kiro.adapter._DEFAULT_CLI_PATH", fake_default),
            patch(_PATCH_WHICH, return_value=None),
            patch(_PATCH_SUBPROCESS_RUN, side_effect=sp.TimeoutExpired(cmd="bash", timeout=60)),
        ):
            with pytest.raises(AgentError) as exc_info:
                KiroCLIAgentAdapter._discover_cli()

        assert exc_info.value.code == AGENT_EXECUTION_FAILED


# ===================================================================
# Integration Test: Headless Execute (AC 8)
# ===================================================================


class TestHeadlessIntegration:
    """Integration tests for headless mode execution."""

    @pytest.mark.asyncio
    async def test_execute_headless_no_interactive_in_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC #8: with KIRO_API_KEY set, --no-interactive is in the command."""
        monkeypatch.setenv("KIRO_API_KEY", "kiro-integration-test-key")
        adapter = KiroCLIAgentAdapter(cli_path=_DEFAULT_CLI_PATH)
        mock_proc = _make_mock_process(stdout=b"Headless result")

        with patch(_PATCH_EXEC, return_value=mock_proc) as mock_exec:
            result = await adapter.execute(_PROMPT)
            call_args = mock_exec.call_args[0]
            assert "--no-interactive" in call_args
            assert "--trust-all-tools" in call_args
            assert result.output == "Headless result"

    @pytest.mark.asyncio
    async def test_execute_headless_with_trust_tools(self) -> None:
        """Headless with explicit trust_tools produces correct flag."""
        adapter = KiroCLIAgentAdapter(
            api_key="key",
            trust_tools=["read", "write"],
            cli_path=_DEFAULT_CLI_PATH,
        )
        mock_proc = _make_mock_process(stdout=b"OK")

        with patch(_PATCH_EXEC, return_value=mock_proc) as mock_exec:
            await adapter.execute(_PROMPT)
            call_args = mock_exec.call_args[0]
            assert "--trust-tools=read,write" in call_args
            assert "--trust-all-tools" not in call_args
