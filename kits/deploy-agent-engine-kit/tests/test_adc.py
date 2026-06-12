"""Unit tests for ADC validation module."""

from __future__ import annotations

import subprocess
from unittest.mock import patch, MagicMock

from beddel_deploy_agent_engine.adc import check_adc


class TestCheckAdcSuccess:
    """Tests for the success path — ADC configured with project ID."""

    def test_returns_configured_true_with_project_id(self) -> None:
        """When both gcloud commands succeed, returns configured=True + project_id."""
        token_result = MagicMock()
        token_result.returncode = 0
        token_result.stdout = "ya29.fake-token\n"
        token_result.stderr = ""

        project_result = MagicMock()
        project_result.returncode = 0
        project_result.stdout = "my-gcp-project\n"
        project_result.stderr = ""

        with patch("beddel_deploy_agent_engine.adc.subprocess.run") as mock_run:
            mock_run.side_effect = [token_result, project_result]
            result = check_adc()

        assert result["configured"] is True
        assert result["project_id"] == "my-gcp-project"
        assert result["error"] is None

    def test_calls_gcloud_with_correct_commands(self) -> None:
        """Verifies the exact gcloud commands used (shell=False, list form)."""
        token_result = MagicMock()
        token_result.returncode = 0
        token_result.stdout = "ya29.token\n"
        token_result.stderr = ""

        project_result = MagicMock()
        project_result.returncode = 0
        project_result.stdout = "your-project-id\n"
        project_result.stderr = ""

        with patch("beddel_deploy_agent_engine.adc.subprocess.run") as mock_run:
            mock_run.side_effect = [token_result, project_result]
            check_adc()

        assert mock_run.call_count == 2
        # First call: token check
        first_call = mock_run.call_args_list[0]
        assert first_call.args[0] == [
            "gcloud", "auth", "application-default", "print-access-token"
        ]
        assert first_call.kwargs["capture_output"] is True
        assert first_call.kwargs["text"] is True
        assert first_call.kwargs["timeout"] == 10

        # Second call: project ID
        second_call = mock_run.call_args_list[1]
        assert second_call.args[0] == [
            "gcloud", "config", "get-value", "project"
        ]

    def test_empty_project_returns_none(self) -> None:
        """When project command returns empty string, project_id is None."""
        token_result = MagicMock()
        token_result.returncode = 0
        token_result.stdout = "ya29.token\n"
        token_result.stderr = ""

        project_result = MagicMock()
        project_result.returncode = 0
        project_result.stdout = "\n"
        project_result.stderr = ""

        with patch("beddel_deploy_agent_engine.adc.subprocess.run") as mock_run:
            mock_run.side_effect = [token_result, project_result]
            result = check_adc()

        assert result["configured"] is True
        assert result["project_id"] is None
        assert result["error"] is None


class TestCheckAdcFailure:
    """Tests for the failure path — ADC not configured."""

    def test_token_command_nonzero_exit(self) -> None:
        """When token command fails (exit != 0), returns configured=False with error."""
        token_result = MagicMock()
        token_result.returncode = 1
        token_result.stdout = ""
        token_result.stderr = "ERROR: (gcloud.auth.application-default.print-access-token) No credentials."

        with patch("beddel_deploy_agent_engine.adc.subprocess.run") as mock_run:
            mock_run.return_value = token_result
            result = check_adc()

        assert result["configured"] is False
        assert result["project_id"] is None
        assert "gcloud auth application-default login" in result["error"]
        # Only the token command should have been called
        assert mock_run.call_count == 1

    def test_token_command_nonzero_exit_no_stderr(self) -> None:
        """When token fails with empty stderr, error still has login instruction."""
        token_result = MagicMock()
        token_result.returncode = 1
        token_result.stdout = ""
        token_result.stderr = ""

        with patch("beddel_deploy_agent_engine.adc.subprocess.run") as mock_run:
            mock_run.return_value = token_result
            result = check_adc()

        assert result["configured"] is False
        assert "gcloud auth application-default login" in result["error"]

    def test_gcloud_not_found(self) -> None:
        """When gcloud binary is missing, returns clear error about installation."""
        with patch("beddel_deploy_agent_engine.adc.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("No such file or directory: 'gcloud'")
            result = check_adc()

        assert result["configured"] is False
        assert result["project_id"] is None
        assert "gcloud CLI not found" in result["error"]


class TestCheckAdcTimeout:
    """Tests for the timeout path — subprocess times out."""

    def test_token_command_timeout(self) -> None:
        """When token command times out, returns configured=False with timeout error."""
        with patch("beddel_deploy_agent_engine.adc.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="gcloud", timeout=10)
            result = check_adc()

        assert result["configured"] is False
        assert result["project_id"] is None
        assert "Timed out" in result["error"]

    def test_project_command_timeout(self) -> None:
        """When project command times out, ADC is configured but project_id is None."""
        token_result = MagicMock()
        token_result.returncode = 0
        token_result.stdout = "ya29.token\n"
        token_result.stderr = ""

        with patch("beddel_deploy_agent_engine.adc.subprocess.run") as mock_run:
            mock_run.side_effect = [
                token_result,
                subprocess.TimeoutExpired(cmd="gcloud", timeout=10),
            ]
            result = check_adc()

        assert result["configured"] is True
        assert result["project_id"] is None
        assert "Timed out" in result["error"]


class TestCheckAdcNeverRaises:
    """Verify that check_adc() never raises, regardless of error type."""

    def test_unexpected_exception_on_token_check(self) -> None:
        """Unexpected errors are caught and returned in the error field."""
        with patch("beddel_deploy_agent_engine.adc.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Unexpected OS error")
            result = check_adc()

        assert result["configured"] is False
        assert result["project_id"] is None
        assert "Unexpected error" in result["error"]

    def test_unexpected_exception_on_project_check(self) -> None:
        """Unexpected errors on the project command are caught."""
        token_result = MagicMock()
        token_result.returncode = 0
        token_result.stdout = "ya29.token\n"
        token_result.stderr = ""

        with patch("beddel_deploy_agent_engine.adc.subprocess.run") as mock_run:
            mock_run.side_effect = [token_result, RuntimeError("Something broke")]
            result = check_adc()

        assert result["configured"] is True
        assert result["project_id"] is None
        assert "Unexpected error" in result["error"]
