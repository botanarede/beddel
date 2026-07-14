"""Unit tests for validate_tenant tool (mocked subprocess — no Node.js required)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from beddel_solution_cms._errors import (
    CMS_NODE_NOT_FOUND,
    CMS_SUBPROCESS_TIMEOUT,
    CMS_VALIDATION_ERROR,
    CMSError,
)
from beddel_solution_cms.tools.validation import validate_tenant

_PATCH_TARGET = "beddel_solution_cms.tools.validation.SafeSubprocessRunner"


def _make_result(
    *,
    exit_code: int = 0,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
) -> MagicMock:
    """Create a mock SubprocessResult."""
    result = MagicMock()
    result.exit_code = exit_code
    result.stdout = stdout
    result.stderr = stderr
    result.timed_out = timed_out
    return result


class TestValidateTenantHappyPath:
    """Tests for successful validation scenarios."""

    @patch(_PATCH_TARGET)
    def test_valid_tenant_dict(self, mock_runner_cls: MagicMock) -> None:
        """Dict input: writes tempfile, calls script, returns valid result."""
        mock_runner_cls.run.return_value = _make_result(
            stdout='{"valid": true, "errors": [], "warnings": []}'
        )

        result = validate_tenant({"metadata": {"name": "test"}})

        assert result == {"valid": True, "errors": [], "warnings": []}
        mock_runner_cls.run.assert_called_once()
        # Verify command includes "node" and the script path
        call_args = mock_runner_cls.run.call_args
        command = call_args[0][0]
        assert command[0] == "node"
        assert "validate-schema.mjs" in command[1]

    @patch(_PATCH_TARGET)
    def test_invalid_tenant_dict(self, mock_runner_cls: MagicMock) -> None:
        """Invalid tenant returns errors (not an exception — valid result)."""
        mock_runner_cls.run.return_value = _make_result(
            stdout='{"valid": false, "errors": ["metadata: Required"], "warnings": []}'
        )

        result = validate_tenant({"incomplete": True})

        assert result["valid"] is False
        assert "metadata: Required" in result["errors"]

    @patch(_PATCH_TARGET)
    def test_file_path_input(self, mock_runner_cls: MagicMock, tmp_path: Path) -> None:
        """String input (existing file): passes path directly, no tempfile."""
        tenant_file = tmp_path / "tenant.json"
        tenant_file.write_text('{"test": true}')

        mock_runner_cls.run.return_value = _make_result(
            stdout='{"valid": true, "errors": [], "warnings": []}'
        )

        result = validate_tenant(str(tenant_file))

        assert result["valid"] is True
        # Verify the actual file path was passed (not a tempfile)
        command = mock_runner_cls.run.call_args[0][0]
        assert str(tenant_file) in command


class TestValidateTenantErrors:
    """Tests for error scenarios."""

    @patch(_PATCH_TARGET)
    def test_nonexistent_file_path(self, mock_runner_cls: MagicMock) -> None:
        """Non-existent file path raises CMSError before subprocess."""
        with pytest.raises(CMSError) as exc_info:
            validate_tenant("/nonexistent/path/tenant.json")

        assert exc_info.value.code == CMS_VALIDATION_ERROR
        assert "not found" in exc_info.value.message.lower()
        mock_runner_cls.run.assert_not_called()

    @patch(_PATCH_TARGET)
    def test_subprocess_nonzero_exit(self, mock_runner_cls: MagicMock) -> None:
        """Non-zero exit raises CMSError with stderr."""
        mock_runner_cls.run.return_value = _make_result(
            exit_code=1, stderr="SyntaxError: Unexpected token"
        )

        with pytest.raises(CMSError) as exc_info:
            validate_tenant({"test": True})

        assert exc_info.value.code == CMS_VALIDATION_ERROR
        assert exc_info.value.details["exit_code"] == 1

    @patch(_PATCH_TARGET)
    def test_subprocess_timeout(self, mock_runner_cls: MagicMock) -> None:
        """Timeout raises CMSError with CMS_SUBPROCESS_TIMEOUT."""
        mock_runner_cls.run.return_value = _make_result(timed_out=True)

        with pytest.raises(CMSError) as exc_info:
            validate_tenant({"test": True})

        assert exc_info.value.code == CMS_SUBPROCESS_TIMEOUT

    @patch(_PATCH_TARGET)
    def test_node_not_found(self, mock_runner_cls: MagicMock) -> None:
        """FileNotFoundError (node missing) raises CMS_NODE_NOT_FOUND."""
        mock_runner_cls.run.side_effect = FileNotFoundError("node: not found")

        with pytest.raises(CMSError) as exc_info:
            validate_tenant({"test": True})

        assert exc_info.value.code == CMS_NODE_NOT_FOUND

    @patch(_PATCH_TARGET)
    def test_malformed_stdout(self, mock_runner_cls: MagicMock) -> None:
        """Malformed JSON stdout raises CMS_VALIDATION_ERROR."""
        mock_runner_cls.run.return_value = _make_result(stdout="not json at all")

        with pytest.raises(CMSError) as exc_info:
            validate_tenant({"test": True})

        assert exc_info.value.code == CMS_VALIDATION_ERROR
        assert "malformed" in exc_info.value.message.lower()
