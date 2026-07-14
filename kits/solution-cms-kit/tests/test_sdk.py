"""Tests for SDK tools — init_firebase_app, sync_tenant_cache, clear_cache.

All tests mock SafeSubprocessRunner — no actual Node.js calls.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from beddel_solution_cms._errors import (
    CMS_NODE_NOT_FOUND,
    CMS_SDK_ERROR,
    CMS_SUBPROCESS_TIMEOUT,
    CMSError,
)
from beddel_solution_cms.tools.sdk import clear_cache, init_firebase_app, sync_tenant_cache


_PATCH_TARGET = "beddel_solution_cms.tools.sdk.SafeSubprocessRunner"


class _FakeResult:
    """Minimal subprocess result mock."""

    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        timed_out: bool = False,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.timed_out = timed_out


class TestInitFirebaseApp:
    """Tests for init_firebase_app."""

    def test_success(self) -> None:
        fake_output = (
            '{"success": true, "project_id": "my-project", "initialized": true}'
        )
        with patch(
            f"{_PATCH_TARGET}.run", return_value=_FakeResult(stdout=fake_output)
        ):
            result = init_firebase_app(project_id="my-project")

        assert result["success"] is True
        assert result["project_id"] == "my-project"
        assert result["initialized"] is True

    def test_script_failure_raises(self) -> None:
        fake_output = '{"success": false, "error": "Invalid project"}'
        with patch(
            f"{_PATCH_TARGET}.run",
            return_value=_FakeResult(stdout=fake_output, exit_code=1),
        ):
            with pytest.raises(CMSError) as exc_info:
                init_firebase_app(project_id="bad-project")
            assert exc_info.value.code == CMS_SDK_ERROR
            assert "Invalid project" in exc_info.value.message

    def test_node_not_found_raises(self) -> None:
        with patch(
            f"{_PATCH_TARGET}.run",
            side_effect=FileNotFoundError("node not found"),
        ):
            with pytest.raises(CMSError) as exc_info:
                init_firebase_app(project_id="my-project")
            assert exc_info.value.code == CMS_NODE_NOT_FOUND

    def test_timeout_raises(self) -> None:
        with patch(
            f"{_PATCH_TARGET}.run",
            return_value=_FakeResult(timed_out=True),
        ):
            with pytest.raises(CMSError) as exc_info:
                init_firebase_app(project_id="my-project")
            assert exc_info.value.code == CMS_SUBPROCESS_TIMEOUT

    def test_malformed_output_raises(self) -> None:
        with patch(
            f"{_PATCH_TARGET}.run",
            return_value=_FakeResult(stdout="not json at all"),
        ):
            with pytest.raises(CMSError) as exc_info:
                init_firebase_app(project_id="my-project")
            assert exc_info.value.code == CMS_SDK_ERROR
            assert "Malformed" in exc_info.value.message


class TestSyncTenantCache:
    """Tests for sync_tenant_cache."""

    def test_success(self) -> None:
        fake_output = (
            '{"success": true, "tenant_id": "acme", '
            '"cached_files": ["/cache/acme/config.json", "/cache/acme/users.json"]}'
        )
        with patch(
            f"{_PATCH_TARGET}.run", return_value=_FakeResult(stdout=fake_output)
        ):
            result = sync_tenant_cache(tenant_id="acme")

        assert result["success"] is True
        assert result["tenant_id"] == "acme"
        assert len(result["cached_files"]) == 2

    def test_tenant_not_found_raises(self) -> None:
        fake_output = '{"success": false, "error": "Tenant not found: nonexistent"}'
        with patch(
            f"{_PATCH_TARGET}.run",
            return_value=_FakeResult(stdout=fake_output, exit_code=1),
        ):
            with pytest.raises(CMSError) as exc_info:
                sync_tenant_cache(tenant_id="nonexistent")
            assert exc_info.value.code == CMS_SDK_ERROR
            assert "Tenant not found" in exc_info.value.message

    def test_timeout_raises(self) -> None:
        with patch(
            f"{_PATCH_TARGET}.run",
            return_value=_FakeResult(timed_out=True),
        ):
            with pytest.raises(CMSError) as exc_info:
                sync_tenant_cache(tenant_id="acme")
            assert exc_info.value.code == CMS_SUBPROCESS_TIMEOUT


class TestClearCache:
    """Tests for clear_cache."""

    def test_clear_specific_tenant(self) -> None:
        fake_output = '{"success": true, "cleared_count": 3}'
        with patch(
            f"{_PATCH_TARGET}.run", return_value=_FakeResult(stdout=fake_output)
        ) as mock_run:
            result = clear_cache(tenant_id="acme")

        assert result["success"] is True
        assert result["cleared_count"] == 3
        # Verify tenant_id was passed as argument
        call_args = mock_run.call_args[0][0]
        assert "acme" in call_args

    def test_clear_all(self) -> None:
        fake_output = '{"success": true, "cleared_count": 5}'
        with patch(
            f"{_PATCH_TARGET}.run", return_value=_FakeResult(stdout=fake_output)
        ) as mock_run:
            result = clear_cache()

        assert result["success"] is True
        assert result["cleared_count"] == 5
        # Verify no tenant_id was passed
        call_args = mock_run.call_args[0][0]
        assert call_args == ["node", "scripts/sdk-clear-cache.mjs"]

    def test_clear_empty_cache(self) -> None:
        fake_output = '{"success": true, "cleared_count": 0}'
        with patch(
            f"{_PATCH_TARGET}.run", return_value=_FakeResult(stdout=fake_output)
        ):
            result = clear_cache(tenant_id="empty-tenant")

        assert result["success"] is True
        assert result["cleared_count"] == 0

    def test_script_failure_raises(self) -> None:
        with patch(
            f"{_PATCH_TARGET}.run",
            return_value=_FakeResult(stderr="Permission denied", exit_code=1),
        ):
            with pytest.raises(CMSError) as exc_info:
                clear_cache()
            assert exc_info.value.code == CMS_SDK_ERROR
