"""Tests for deploy_site + provision_firebase tools — Firebase/gcloud CLI wrapping."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from beddel_solution_cms._errors import (
    CMS_DEPLOY_FAILED,
    CMS_PROVISION_FAILED,
    CMSError,
)
from beddel_solution_cms.tools.deploy import deploy_site, provision_firebase
from beddel.utils.subprocess import SubprocessResult


def _success_result(**kwargs) -> SubprocessResult:
    """Create a successful subprocess result."""
    return SubprocessResult(
        exit_code=0,
        stdout=kwargs.get(
            "stdout", "Deploy complete\nHosting URL: https://my-project.web.app"
        ),
        stderr=kwargs.get("stderr", ""),
        timed_out=False,
        truncated=False,
    )


def _failure_result(**kwargs) -> SubprocessResult:
    """Create a failed subprocess result."""
    return SubprocessResult(
        exit_code=kwargs.get("exit_code", 1),
        stdout=kwargs.get("stdout", ""),
        stderr=kwargs.get("stderr", "Error: Not authorized"),
        timed_out=False,
        truncated=False,
    )


def _timeout_result() -> SubprocessResult:
    """Create a timed-out subprocess result."""
    return SubprocessResult(
        exit_code=-1,
        stdout="",
        stderr="",
        timed_out=True,
        truncated=False,
    )


class TestDeploySiteSuccess:
    """Tests for successful deploy scenarios."""

    def test_successful_deploy_returns_success_dict(self, tmp_path) -> None:
        """AC1: Successful deploy returns dict with success=True, url, deploy_log."""
        with (
            patch(
                "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
                return_value=_success_result(
                    stdout="Deploying...\nHosting URL: https://my-proj.web.app\nDone"
                ),
            ),
            patch(
                "beddel_solution_cms.tools.deploy.get_kit_root",
                return_value=tmp_path,
            ),
        ):
            result = deploy_site("my-tenant", "my-proj")

        assert result["success"] is True
        assert result["url"] == "https://my-proj.web.app"
        assert "Deploying" in result["deploy_log"]

    def test_deploy_default_hosting_target_is_tenant_id(self, tmp_path) -> None:
        """AC4 (inverse): Default hosting_target is tenant_id."""
        calls: list = []

        def mock_run(command, **kwargs):
            calls.append((command, kwargs))
            return _success_result()

        with (
            patch(
                "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
                side_effect=mock_run,
            ),
            patch(
                "beddel_solution_cms.tools.deploy.get_kit_root",
                return_value=tmp_path,
            ),
        ):
            deploy_site("my-tenant", "my-proj")

        assert "hosting:my-tenant" in calls[0][0]

    def test_deploy_custom_hosting_target(self, tmp_path) -> None:
        """AC4: Custom hosting_target is used in command."""
        calls: list = []

        def mock_run(command, **kwargs):
            calls.append((command, kwargs))
            return _success_result()

        with (
            patch(
                "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
                side_effect=mock_run,
            ),
            patch(
                "beddel_solution_cms.tools.deploy.get_kit_root",
                return_value=tmp_path,
            ),
        ):
            deploy_site("my-tenant", "my-proj", hosting_target="custom-target")

        assert "hosting:custom-target" in calls[0][0]

    def test_deploy_url_fallback_when_no_hosting_url_in_output(self, tmp_path) -> None:
        """AC1: When no Hosting URL in stdout, fallback to project_id.web.app."""
        with (
            patch(
                "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
                return_value=_success_result(stdout="Deploy complete. No URL line."),
            ),
            patch(
                "beddel_solution_cms.tools.deploy.get_kit_root",
                return_value=tmp_path,
            ),
        ):
            result = deploy_site("my-tenant", "my-proj")

        assert result["success"] is True
        assert result["url"] == "https://my-proj.web.app"


class TestDeploySiteFailure:
    """Tests for deploy failure scenarios."""

    def test_failed_deploy_returns_failure_dict(self, tmp_path) -> None:
        """AC2: Failed deploy (exit_code≠0) returns failure dict with log."""
        with (
            patch(
                "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
                return_value=_failure_result(
                    stdout="Starting...", stderr="Error: Not authorized"
                ),
            ),
            patch(
                "beddel_solution_cms.tools.deploy.get_kit_root",
                return_value=tmp_path,
            ),
        ):
            result = deploy_site("my-tenant", "my-proj")

        assert result["success"] is False
        assert result["url"] == ""
        assert "Error: Not authorized" in result["deploy_log"]

    def test_deploy_firebase_cli_missing_raises_cms_deploy_failed(
        self, tmp_path
    ) -> None:
        """AC3: FileNotFoundError raises CMSError with CMS_DEPLOY_FAILED."""
        with (
            patch(
                "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
                side_effect=FileNotFoundError("firebase: not found"),
            ),
            patch(
                "beddel_solution_cms.tools.deploy.get_kit_root",
                return_value=tmp_path,
            ),
        ):
            with pytest.raises(CMSError) as exc_info:
                deploy_site("my-tenant", "my-proj")

        assert exc_info.value.code == CMS_DEPLOY_FAILED
        assert "firebase CLI not found" in exc_info.value.message

    def test_deploy_timeout_returns_failure_dict(self, tmp_path) -> None:
        """AC5: Timeout returns failure dict with timeout message."""
        with (
            patch(
                "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
                return_value=_timeout_result(),
            ),
            patch(
                "beddel_solution_cms.tools.deploy.get_kit_root",
                return_value=tmp_path,
            ),
        ):
            result = deploy_site("my-tenant", "my-proj")

        assert result["success"] is False
        assert result["url"] == ""
        assert "timed out" in result["deploy_log"]
        assert "120" in result["deploy_log"]


class TestProvisionFirebaseSuccess:
    """Tests for successful provisioning scenarios."""

    def test_provision_all_commands_succeed(self) -> None:
        """AC6: All gcloud commands succeed → returns success dict."""
        with patch(
            "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
            return_value=_success_result(stdout="Created project"),
        ):
            result = provision_firebase("my-proj", "My Project")

        assert result["success"] is True
        assert result["project_id"] == "my-proj"
        assert result["hosting_url"] == "https://my-proj.web.app"

    def test_provision_custom_region(self) -> None:
        """AC9: Custom region is accepted (region parameter exists and is passed)."""
        calls: list = []

        def mock_run(command, **kwargs):
            calls.append((command, kwargs))
            return _success_result(stdout="OK")

        with patch(
            "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
            side_effect=mock_run,
        ):
            result = provision_firebase("my-proj", "My Project", region="us-central1")

        assert result["success"] is True
        # All 5 commands executed
        assert len(calls) == 5


class TestProvisionFirebaseFailure:
    """Tests for provisioning failure scenarios."""

    def test_provision_command_failure_returns_failure_dict(self) -> None:
        """AC7: Command failure returns failure dict."""
        call_count = [0]

        def mock_run(command, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                return _failure_result(stderr="Permission denied")
            return _success_result(stdout="OK")

        with patch(
            "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
            side_effect=mock_run,
        ):
            result = provision_firebase("my-proj", "My Project")

        assert result["success"] is False
        assert result["project_id"] == "my-proj"
        assert result["hosting_url"] == ""

    def test_provision_gcloud_cli_missing_raises_cms_provision_failed(self) -> None:
        """AC8: FileNotFoundError raises CMSError with CMS_PROVISION_FAILED."""
        with patch(
            "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
            side_effect=FileNotFoundError("gcloud: not found"),
        ):
            with pytest.raises(CMSError) as exc_info:
                provision_firebase("my-proj", "My Project")

        assert exc_info.value.code == CMS_PROVISION_FAILED
        assert "gcloud CLI not found" in exc_info.value.message

    def test_provision_firebase_cli_missing_raises_cms_provision_failed(self) -> None:
        """AC8: FileNotFoundError on firebase command also raises CMS_PROVISION_FAILED."""
        call_count = [0]

        def mock_run(command, **kwargs):
            call_count[0] += 1
            # First 4 commands (gcloud) succeed, 5th (firebase) raises
            if call_count[0] == 5:
                raise FileNotFoundError("firebase: not found")
            return _success_result(stdout="OK")

        with patch(
            "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
            side_effect=mock_run,
        ):
            with pytest.raises(CMSError) as exc_info:
                provision_firebase("my-proj", "My Project")

        assert exc_info.value.code == CMS_PROVISION_FAILED
        assert "firebase" in exc_info.value.message.lower()

    def test_provision_timeout_returns_failure_dict(self) -> None:
        """AC7 (timeout variant): Timeout returns failure dict."""
        call_count = [0]

        def mock_run(command, **kwargs):
            call_count[0] += 1
            if call_count[0] == 3:
                return _timeout_result()
            return _success_result(stdout="OK")

        with patch(
            "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
            side_effect=mock_run,
        ):
            result = provision_firebase("my-proj", "My Project")

        assert result["success"] is False
        assert result["hosting_url"] == ""

    def test_provision_stops_at_first_failure(self) -> None:
        """AC7: Provisioning stops at first failed command (doesn't continue)."""
        calls: list = []

        def mock_run(command, **kwargs):
            calls.append(command)
            if len(calls) == 1:
                return _failure_result(stderr="Already exists")
            return _success_result(stdout="OK")

        with patch(
            "beddel_solution_cms.tools.deploy.SafeSubprocessRunner.run",
            side_effect=mock_run,
        ):
            result = provision_firebase("my-proj", "My Project")

        # Should stop after first failure — only 1 call made
        assert len(calls) == 1
        assert result["success"] is False


class TestErrorCodes:
    """Tests for error code registration."""

    def test_cms_deploy_failed_resolves(self) -> None:
        """AC10: CMS_DEPLOY_FAILED resolves to the string 'CMS_DEPLOY_FAILED'."""
        from beddel_solution_cms._errors import CMS_DEPLOY_FAILED as imported

        assert imported == "CMS_DEPLOY_FAILED"

    def test_cms_provision_failed_resolves(self) -> None:
        """AC10: CMS_PROVISION_FAILED resolves to the string 'CMS_PROVISION_FAILED'."""
        from beddel_solution_cms._errors import CMS_PROVISION_FAILED as imported

        assert imported == "CMS_PROVISION_FAILED"

    def test_error_codes_in_all(self) -> None:
        """AC10: Both codes are in _errors.__all__."""
        import beddel_solution_cms._errors as errors_mod

        assert "CMS_DEPLOY_FAILED" in errors_mod.__all__
        assert "CMS_PROVISION_FAILED" in errors_mod.__all__
