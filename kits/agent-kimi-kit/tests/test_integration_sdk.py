"""Integration tests against the real installed kimi-agent-sdk==0.0.5.

These tests import the actual SDK classes (NOT mocks) to verify
API compatibility. No sessions are created, no API keys are needed.
"""

from __future__ import annotations

import inspect


class TestSessionCreateSignature:
    """Verify Session.create() signature matches what adapter expects."""

    def test_session_create_does_not_accept_sandbox_mode(self) -> None:
        """Session.create() must NOT have a sandbox_mode parameter."""
        from kimi_agent_sdk import Session

        sig = inspect.signature(Session.create)
        params = list(sig.parameters.keys())
        assert "sandbox_mode" not in params, (
            f"Session.create() should NOT accept sandbox_mode. "
            f"Found parameters: {params}"
        )

    def test_session_create_accepts_work_dir(self) -> None:
        """Session.create() must accept work_dir parameter."""
        from kimi_agent_sdk import Session

        sig = inspect.signature(Session.create)
        params = list(sig.parameters.keys())
        assert "work_dir" in params, (
            f"Session.create() should accept work_dir. Found parameters: {params}"
        )

    def test_session_create_accepts_config(self) -> None:
        """Session.create() must accept config parameter."""
        from kimi_agent_sdk import Session

        sig = inspect.signature(Session.create)
        params = list(sig.parameters.keys())
        assert "config" in params, (
            f"Session.create() should accept config. Found parameters: {params}"
        )

    def test_session_create_accepts_yolo(self) -> None:
        """Session.create() must accept yolo parameter."""
        from kimi_agent_sdk import Session

        sig = inspect.signature(Session.create)
        params = list(sig.parameters.keys())
        assert "yolo" in params, (
            f"Session.create() should accept yolo. Found parameters: {params}"
        )


class TestKaosPath:
    """Verify KaosPath is importable and constructable from string."""

    def test_kaos_path_importable(self) -> None:
        """KaosPath must be importable from kaos.path."""
        from kaos.path import KaosPath

        assert KaosPath is not None

    def test_kaos_path_from_string(self) -> None:
        """KaosPath can be constructed from a string path."""
        from kaos.path import KaosPath

        path = KaosPath(".")
        assert path is not None

    def test_kaos_path_from_absolute_string(self) -> None:
        """KaosPath can be constructed from an absolute path string."""
        from kaos.path import KaosPath

        path = KaosPath("/tmp/test-workspace")
        assert path is not None
        assert str(path) == "/tmp/test-workspace"
