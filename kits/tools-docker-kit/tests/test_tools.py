"""Tests for beddel_tools_docker.tools — all async, no Docker daemon required."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from beddel_tools_docker.tools import (
    DockerToolError,
    MAX_OUTPUT_BYTES,
    docker_compose_build,
    docker_compose_down,
    docker_compose_run,
    docker_compose_up,
)


# ---------------------------------------------------------------------------
# Mock Process
# ---------------------------------------------------------------------------


class MockProcess:
    """Fake asyncio.subprocess.Process for testing."""

    def __init__(
        self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""
    ) -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def compose_file(tmp_path):
    """Create a temporary compose file."""
    f = tmp_path / "docker-compose.yml"
    f.touch()
    return str(f)


# ---------------------------------------------------------------------------
# docker_compose_build
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docker_compose_build_success(compose_file):
    mock_proc = MockProcess(
        returncode=0, stdout=b"Building web\nsha256:abc123def456 done\n"
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await docker_compose_build(compose_file, "web")

    assert result["service"] == "web"
    assert "image_id" in result
    assert result["build_time_ms"] > 0


@pytest.mark.asyncio
async def test_docker_compose_build_missing_file():
    with pytest.raises(FileNotFoundError):
        await docker_compose_build("/nonexistent/docker-compose.yml", "web")


@pytest.mark.asyncio
async def test_docker_compose_build_failure(compose_file):
    mock_proc = MockProcess(returncode=1, stderr=b"build failed")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(DockerToolError) as exc_info:
            await docker_compose_build(compose_file, "web")

    assert exc_info.value.exit_code == 1


# ---------------------------------------------------------------------------
# docker_compose_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docker_compose_run_success(compose_file):
    mock_proc = MockProcess(returncode=0, stdout=b"test output", stderr=b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await docker_compose_run(compose_file, "web", "echo hello")

    assert result["exit_code"] == 0
    assert result["stdout"] == "test output"
    assert result["stderr"] == ""
    assert result["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_docker_compose_run_non_zero_exit_no_raise(compose_file):
    mock_proc = MockProcess(returncode=1, stderr=b"error")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await docker_compose_run(compose_file, "web", "false")

    # Does NOT raise — returns structured dict
    assert result["exit_code"] == 1
    assert "error" in result["stderr"]


@pytest.mark.asyncio
async def test_docker_compose_run_timeout(compose_file):
    mock_proc = MockProcess(returncode=0)

    async def _communicate_timeout():
        raise asyncio.TimeoutError

    mock_proc.communicate = _communicate_timeout  # type: ignore[assignment]

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await docker_compose_run(
            compose_file, "web", "sleep 9999", timeout=1
        )

    assert result["exit_code"] == -1
    assert "timeout" in result["stderr"]
    assert mock_proc.killed


@pytest.mark.asyncio
async def test_docker_compose_run_env_injection(compose_file):
    mock_proc = MockProcess(returncode=0, stdout=b"ok")
    captured_args: list[str] = []

    async def _mock_exec(*args, **kwargs):
        captured_args.extend(args)
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=_mock_exec):
        await docker_compose_run(
            compose_file, "web", "env", env={"FOO": "bar", "BAZ": "qux"}
        )

    # Verify -e flags are present
    assert "-e" in captured_args
    assert "FOO=bar" in captured_args
    assert "BAZ=qux" in captured_args


@pytest.mark.asyncio
async def test_docker_compose_run_output_truncation(compose_file):
    large_output = b"x" * 200_000  # 200KB
    mock_proc = MockProcess(returncode=0, stdout=large_output)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await docker_compose_run(compose_file, "web", "cat bigfile")

    assert result["stdout"].startswith("[truncated]\n")
    # Prefix "[truncated]\n" is 12 chars, tail is MAX_OUTPUT_BYTES
    assert len(result["stdout"]) <= MAX_OUTPUT_BYTES + 12


@pytest.mark.asyncio
async def test_docker_compose_run_sh_c(compose_file):
    mock_proc = MockProcess(returncode=0, stdout=b"ok")
    captured_args: list[str] = []

    async def _mock_exec(*args, **kwargs):
        captured_args.extend(args)
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=_mock_exec):
        await docker_compose_run(compose_file, "web", "pytest tests/ -v")

    # Command passed via sh -c, NOT bash
    assert "sh" in captured_args
    assert "-c" in captured_args
    assert "pytest tests/ -v" in captured_args


@pytest.mark.asyncio
async def test_docker_compose_run_missing_file():
    with pytest.raises(FileNotFoundError):
        await docker_compose_run("/nonexistent/docker-compose.yml", "web", "echo hi")


# ---------------------------------------------------------------------------
# docker_compose_up
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docker_compose_up_success(compose_file):
    mock_proc = MockProcess(
        returncode=0,
        stderr=b"Container project-web-1  Started\nContainer project-db-1  Running",
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await docker_compose_up(compose_file)

    assert len(result["services_started"]) > 0
    assert len(result["already_running"]) > 0


@pytest.mark.asyncio
async def test_docker_compose_up_failure(compose_file):
    mock_proc = MockProcess(returncode=1, stderr=b"service failed")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(DockerToolError):
            await docker_compose_up(compose_file)


# ---------------------------------------------------------------------------
# docker_compose_down
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_docker_compose_down_success(compose_file):
    mock_proc = MockProcess(
        returncode=0,
        stderr=b"Container project-web-1  Stopped\nContainer project-web-1  Removed",
    )

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await docker_compose_down(compose_file)

    assert len(result["services_stopped"]) > 0


@pytest.mark.asyncio
async def test_docker_compose_down_with_volumes(compose_file):
    mock_proc = MockProcess(returncode=0, stderr=b"Container x  Stopped")
    captured_args: list[str] = []

    async def _mock_exec(*args, **kwargs):
        captured_args.extend(args)
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=_mock_exec):
        await docker_compose_down(compose_file, remove_volumes=True)

    assert "--volumes" in captured_args
