"""Tests for build_site tool — Next.js static export via SafeSubprocessRunner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from beddel_bonar_cms._errors import CMS_BUILD_FAILED, CMSError
from beddel_bonar_cms.tools.build import build_site
from beddel.utils.subprocess import SubprocessResult


@pytest.fixture
def mock_studio_path(tmp_path: Path) -> Path:
    """Create a fake studio app directory."""
    studio = tmp_path / "apps" / "bonar-creator-studio"
    studio.mkdir(parents=True)
    return studio


@pytest.fixture
def mock_kit_root(tmp_path: Path, mock_studio_path: Path) -> Path:
    """Create a fake kit root with studio app present."""
    # tmp_path acts as kit_root/node, so kit_root = tmp_path.parent? No.
    # We need to control get_kit_root() return value.
    # The studio path is already created, we'll pass it explicitly.
    return tmp_path


def _success_result(**kwargs) -> SubprocessResult:
    """Create a successful subprocess result."""
    return SubprocessResult(
        exit_code=0,
        stdout=kwargs.get("stdout", "Build completed successfully"),
        stderr=kwargs.get("stderr", ""),
        timed_out=False,
        truncated=False,
    )


def _failure_result(**kwargs) -> SubprocessResult:
    """Create a failed subprocess result."""
    return SubprocessResult(
        exit_code=kwargs.get("exit_code", 1),
        stdout=kwargs.get("stdout", ""),
        stderr=kwargs.get("stderr", "Error: Module not found"),
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


class TestBuildSiteSuccess:
    """Tests for successful build scenarios."""

    def test_successful_build_returns_success_dict(
        self, mock_studio_path: Path
    ) -> None:
        """AC1: Successful build returns dict with success=True, output_dir, build_log."""
        with (
            patch(
                "beddel_bonar_cms.tools.build.SafeSubprocessRunner.run",
                return_value=_success_result(stdout="Route / 200\nBuild complete"),
            ),
            patch(
                "beddel_bonar_cms.tools.build.get_kit_root",
                return_value=mock_studio_path.parent.parent,
            ),
        ):
            result = build_site("my-tenant", studio_path=mock_studio_path)

        assert result["success"] is True
        assert "my-tenant" in result["output_dir"]
        assert "Build complete" in result["build_log"]

    def test_custom_studio_path_used(self, tmp_path: Path) -> None:
        """AC4: Custom studio_path is used for build working directory."""
        custom_path = tmp_path / "custom" / "studio"
        custom_path.mkdir(parents=True)

        calls: list = []

        def mock_run(command, **kwargs):
            calls.append((command, kwargs))
            return _success_result()

        with (
            patch(
                "beddel_bonar_cms.tools.build.SafeSubprocessRunner.run",
                side_effect=mock_run,
            ),
            patch(
                "beddel_bonar_cms.tools.build.get_kit_root",
                return_value=tmp_path,
            ),
        ):
            # Ensure no copy-tenant-assets.sh exists
            result = build_site("test-site", studio_path=custom_path)

        assert result["success"] is True
        # The build command should use custom_path as cwd
        build_call = calls[-1]
        assert build_call[1]["cwd"] == str(custom_path)

    def test_node_env_passed_to_subprocess(self, mock_studio_path: Path) -> None:
        """AC5: node_env is passed as NODE_ENV in subprocess environment."""
        calls: list = []

        def mock_run(command, **kwargs):
            calls.append((command, kwargs))
            return _success_result()

        with (
            patch(
                "beddel_bonar_cms.tools.build.SafeSubprocessRunner.run",
                side_effect=mock_run,
            ),
            patch(
                "beddel_bonar_cms.tools.build.get_kit_root",
                return_value=mock_studio_path.parent.parent,
            ),
        ):
            build_site(
                "my-tenant", node_env="development", studio_path=mock_studio_path
            )

        # Last call is the next build call
        build_call = calls[-1]
        assert build_call[1]["env"]["NODE_ENV"] == "development"

    def test_default_node_env_is_production(self, mock_studio_path: Path) -> None:
        """AC5: Default NODE_ENV is 'production'."""
        calls: list = []

        def mock_run(command, **kwargs):
            calls.append((command, kwargs))
            return _success_result()

        with (
            patch(
                "beddel_bonar_cms.tools.build.SafeSubprocessRunner.run",
                side_effect=mock_run,
            ),
            patch(
                "beddel_bonar_cms.tools.build.get_kit_root",
                return_value=mock_studio_path.parent.parent,
            ),
        ):
            build_site("my-tenant", studio_path=mock_studio_path)

        build_call = calls[-1]
        assert build_call[1]["env"]["NODE_ENV"] == "production"


class TestBuildSiteFailure:
    """Tests for build failure scenarios."""

    def test_failed_build_returns_failure_dict(self, mock_studio_path: Path) -> None:
        """AC2: Failed build (exit_code≠0) returns failure dict with log."""
        with (
            patch(
                "beddel_bonar_cms.tools.build.SafeSubprocessRunner.run",
                return_value=_failure_result(
                    stdout="Compiling...", stderr="Error: Module not found"
                ),
            ),
            patch(
                "beddel_bonar_cms.tools.build.get_kit_root",
                return_value=mock_studio_path.parent.parent,
            ),
        ):
            result = build_site("my-tenant", studio_path=mock_studio_path)

        assert result["success"] is False
        assert result["output_dir"] == ""
        assert "Error: Module not found" in result["build_log"]

    def test_studio_path_missing_raises_cms_build_failed(self, tmp_path: Path) -> None:
        """AC3: Missing studio path raises CMSError with CMS_BUILD_FAILED."""
        missing_path = tmp_path / "nonexistent" / "studio"

        with pytest.raises(CMSError) as exc_info:
            build_site("my-tenant", studio_path=missing_path)

        assert exc_info.value.code == CMS_BUILD_FAILED
        assert "does not exist" in exc_info.value.message

    def test_timeout_returns_failure_dict(self, mock_studio_path: Path) -> None:
        """AC8: Timeout returns failure dict with timeout message."""
        with (
            patch(
                "beddel_bonar_cms.tools.build.SafeSubprocessRunner.run",
                return_value=_timeout_result(),
            ),
            patch(
                "beddel_bonar_cms.tools.build.get_kit_root",
                return_value=mock_studio_path.parent.parent,
            ),
        ):
            result = build_site("my-tenant", studio_path=mock_studio_path)

        assert result["success"] is False
        assert result["output_dir"] == ""
        assert "timed out" in result["build_log"]
        assert "120" in result["build_log"]


class TestCopyTenantAssets:
    """Tests for the copy-tenant-assets.sh pre-build step."""

    def test_assets_script_called_when_present(self, tmp_path: Path) -> None:
        """AC6: copy-tenant-assets.sh is called before build when it exists."""
        # Set up kit root structure
        scripts_dir = tmp_path / "node" / "scripts"
        scripts_dir.mkdir(parents=True)
        assets_script = scripts_dir / "copy-tenant-assets.sh"
        assets_script.write_text("#!/bin/bash\necho done")

        studio = tmp_path / "node" / "apps" / "bonar-creator-studio"
        studio.mkdir(parents=True)

        calls: list = []

        def mock_run(command, **kwargs):
            calls.append((command, kwargs))
            return _success_result()

        with (
            patch(
                "beddel_bonar_cms.tools.build.SafeSubprocessRunner.run",
                side_effect=mock_run,
            ),
            patch(
                "beddel_bonar_cms.tools.build.get_kit_root",
                return_value=tmp_path,
            ),
        ):
            build_site("my-tenant", studio_path=studio)

        # Should have 2 calls: copy-tenant-assets + next build
        assert len(calls) == 2
        # First call is the assets script
        assert "copy-tenant-assets.sh" in calls[0][0][1]

    def test_assets_script_skipped_when_absent(self, tmp_path: Path) -> None:
        """AC7: Build proceeds without error when copy-tenant-assets.sh doesn't exist."""
        studio = tmp_path / "node" / "apps" / "bonar-creator-studio"
        studio.mkdir(parents=True)
        # No scripts dir — no copy-tenant-assets.sh

        calls: list = []

        def mock_run(command, **kwargs):
            calls.append((command, kwargs))
            return _success_result()

        with (
            patch(
                "beddel_bonar_cms.tools.build.SafeSubprocessRunner.run",
                side_effect=mock_run,
            ),
            patch(
                "beddel_bonar_cms.tools.build.get_kit_root",
                return_value=tmp_path,
            ),
        ):
            result = build_site("my-tenant", studio_path=studio)

        # Only 1 call: next build (no assets script)
        assert len(calls) == 1
        assert result["success"] is True


class TestErrorCode:
    """Tests for error code registration."""

    def test_cms_build_failed_resolves(self) -> None:
        """AC9: CMS_BUILD_FAILED resolves to the string 'CMS_BUILD_FAILED'."""
        from beddel_bonar_cms._errors import CMS_BUILD_FAILED as imported

        assert imported == "CMS_BUILD_FAILED"

    def test_cms_build_failed_in_all(self) -> None:
        """AC9: CMS_BUILD_FAILED is in _errors.__all__."""
        import beddel_bonar_cms._errors as errors_mod

        assert "CMS_BUILD_FAILED" in errors_mod.__all__
