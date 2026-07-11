"""Tests for preview_site and stop_preview tools.

All tests mock subprocess.Popen and os.kill — no real processes are spawned.
"""

from __future__ import annotations

import os
import signal
from unittest.mock import MagicMock, patch

import pytest

from beddel_bonar_cms._errors import CMS_INVALID_TENANT_ID, CMS_PREVIEW_FAILED, CMSError
from beddel_bonar_cms.tools.preview import preview_site, stop_preview


# ---------------------------------------------------------------------------
# preview_site tests
# ---------------------------------------------------------------------------


class TestPreviewSite:
    """Tests for the preview_site tool."""

    @patch("beddel_bonar_cms.tools.preview.subprocess.Popen")
    def test_preview_site_success_default_port(self, mock_popen: MagicMock) -> None:
        """AC1: Returns success dict with url on port 3000 and pid."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        result = preview_site("my-tenant")

        assert result == {
            "success": True,
            "url": "http://localhost:3000",
            "pid": 12345,
        }

    @patch("beddel_bonar_cms.tools.preview.subprocess.Popen")
    def test_preview_site_custom_port(self, mock_popen: MagicMock) -> None:
        """AC2: Custom port appears in command and url."""
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_popen.return_value = mock_proc

        result = preview_site("my-tenant", port=4000)

        # Verify the command includes the custom port
        call_args = mock_popen.call_args
        command = call_args[0][0]
        assert "-p" in command
        port_index = command.index("-p")
        assert command[port_index + 1] == "4000"

        assert result["url"] == "http://localhost:4000"
        assert result["pid"] == 99999

    @patch("beddel_bonar_cms.tools.preview.subprocess.Popen")
    def test_preview_site_sets_correct_env_and_cwd(self, mock_popen: MagicMock) -> None:
        """AC3, AC4: Correct env vars (EXPORT_TENANT_ID, PATH) and cwd."""
        mock_proc = MagicMock()
        mock_proc.pid = 1000
        mock_popen.return_value = mock_proc

        preview_site("test-site")

        call_kwargs = mock_popen.call_args[1]

        # Check env
        env = call_kwargs["env"]
        assert env["EXPORT_TENANT_ID"] == "test-site"
        assert "PATH" in env
        assert env["PATH"] == os.environ.get("PATH", "/usr/bin:/bin")

        # Check cwd ends with the studio app path
        cwd = call_kwargs["cwd"]
        assert cwd.endswith("node/apps/bonar-creator-studio")

    @patch("beddel_bonar_cms.tools.preview.subprocess.Popen")
    def test_preview_site_invalid_tenant_id_raises(self, mock_popen: MagicMock) -> None:
        """Invalid tenant_id raises CMSError(CMS_INVALID_TENANT_ID)."""
        with pytest.raises(CMSError) as exc_info:
            preview_site("INVALID_ID")

        assert exc_info.value.code == CMS_INVALID_TENANT_ID
        mock_popen.assert_not_called()

    @patch("beddel_bonar_cms.tools.preview.subprocess.Popen")
    def test_preview_site_oserror_raises_cms_preview_failed(
        self, mock_popen: MagicMock
    ) -> None:
        """OSError during Popen raises CMSError(CMS_PREVIEW_FAILED)."""
        mock_popen.side_effect = OSError("No such file or directory")

        with pytest.raises(CMSError) as exc_info:
            preview_site("my-tenant")

        assert exc_info.value.code == CMS_PREVIEW_FAILED
        assert "Failed to start dev server" in exc_info.value.message


# ---------------------------------------------------------------------------
# stop_preview tests
# ---------------------------------------------------------------------------


class TestStopPreview:
    """Tests for the stop_preview tool."""

    @patch("beddel_bonar_cms.tools.preview.os.kill")
    def test_stop_preview_success(self, mock_kill: MagicMock) -> None:
        """AC5: Successful SIGTERM returns success dict."""
        mock_kill.return_value = None

        result = stop_preview(12345)

        assert result == {
            "success": True,
            "message": "Process 12345 terminated",
        }
        mock_kill.assert_called_once_with(12345, signal.SIGTERM)

    @patch("beddel_bonar_cms.tools.preview.os.kill")
    def test_stop_preview_process_not_found(self, mock_kill: MagicMock) -> None:
        """AC6: ProcessLookupError returns failure dict without raising."""
        mock_kill.side_effect = ProcessLookupError("No such process")

        result = stop_preview(99999)

        assert result == {
            "success": False,
            "message": "Process not found",
        }

    @patch("beddel_bonar_cms.tools.preview.os.kill")
    def test_stop_preview_oserror(self, mock_kill: MagicMock) -> None:
        """AC6: OSError (e.g. permission denied) returns failure dict."""
        mock_kill.side_effect = OSError("Operation not permitted")

        result = stop_preview(1)

        assert result == {
            "success": False,
            "message": "Process not found",
        }


# ---------------------------------------------------------------------------
# Error code tests
# ---------------------------------------------------------------------------


class TestErrorCodes:
    """Tests for CMS_PREVIEW_FAILED error code."""

    def test_cms_preview_failed_resolves(self) -> None:
        """AC7: CMS_PREVIEW_FAILED resolves to its string name."""
        assert CMS_PREVIEW_FAILED == "CMS_PREVIEW_FAILED"

    def test_error_code_in_all(self) -> None:
        """AC7: CMS_PREVIEW_FAILED appears in _errors.__all__."""
        import beddel_bonar_cms._errors as errors_mod

        assert "CMS_PREVIEW_FAILED" in errors_mod.__all__
