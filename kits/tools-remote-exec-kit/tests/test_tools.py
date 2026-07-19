"""Tests for beddel_tools_remote.tools — all async, no Multipass daemon required."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from beddel_tools_remote.tools import (
    MAX_OUTPUT_BYTES,
    RemoteToolError,
    VMNotFoundError,
    _truncate,
    _validate_backend,
    remote_exec,
    remote_file_read,
    remote_health_check,
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
# Helper Tests
# ---------------------------------------------------------------------------


class TestValidateBackend:
    def test_multipass_accepted(self) -> None:
        _validate_backend("multipass")  # No raise

    def test_ssh_raises(self) -> None:
        with pytest.raises(NotImplementedError, match="ssh"):
            _validate_backend("ssh")

    def test_docker_raises(self) -> None:
        with pytest.raises(NotImplementedError, match="docker"):
            _validate_backend("docker")


class TestTruncate:
    def test_short_text_unchanged(self) -> None:
        text = "hello world"
        assert _truncate(text) == text

    def test_exact_limit_unchanged(self) -> None:
        text = "x" * MAX_OUTPUT_BYTES
        assert _truncate(text) == text

    def test_over_limit_tail_preserved(self) -> None:
        # Create text that exceeds limit
        text = "A" * 50_000 + "B" * MAX_OUTPUT_BYTES
        result = _truncate(text)
        assert result.startswith("[truncated]\n")
        # Last MAX_OUTPUT_BYTES characters preserved
        assert result.endswith("B" * MAX_OUTPUT_BYTES)


# ---------------------------------------------------------------------------
# remote_exec
# ---------------------------------------------------------------------------


class TestRemoteExec:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock_proc = MockProcess(
            returncode=0, stdout=b"hello world\n", stderr=b""
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await remote_exec("test-vm", "echo hello world")

        assert result["exit_code"] == 0
        assert result["stdout"] == "hello world\n"
        assert result["stderr"] == ""
        assert result["vm"] == "test-vm"
        assert result["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_non_zero_exit_no_raise(self) -> None:
        mock_proc = MockProcess(
            returncode=1, stdout=b"", stderr=b"command not found"
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await remote_exec("test-vm", "invalid_cmd")

        # Does NOT raise — returns structured result
        assert result["exit_code"] == 1
        assert "command not found" in result["stderr"]

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self) -> None:
        mock_proc = MockProcess(returncode=0)

        async def _communicate_timeout() -> tuple[bytes, bytes]:
            raise asyncio.TimeoutError

        mock_proc.communicate = _communicate_timeout  # type: ignore[assignment]

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RemoteToolError) as exc_info:
                await remote_exec("test-vm", "sleep 9999", timeout=1)

        assert exc_info.value.exit_code == -1
        assert "timeout" in exc_info.value.stderr
        assert mock_proc.killed

    @pytest.mark.asyncio
    async def test_vm_not_found(self) -> None:
        mock_proc = MockProcess(
            returncode=2,
            stderr=b"instance does not exist: no-such-vm",
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(VMNotFoundError) as exc_info:
                await remote_exec("no-such-vm", "echo hi")

        assert exc_info.value.vm == "no-such-vm"

    @pytest.mark.asyncio
    async def test_output_truncation(self) -> None:
        large_output = b"x" * 200_000  # 200KB > 100KB limit
        mock_proc = MockProcess(returncode=0, stdout=large_output)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await remote_exec("test-vm", "cat bigfile")

        assert result["stdout"].startswith("[truncated]\n")
        # Prefix "[truncated]\n" is 12 chars, tail is MAX_OUTPUT_BYTES
        assert len(result["stdout"]) <= MAX_OUTPUT_BYTES + 12

    @pytest.mark.asyncio
    async def test_backend_validation(self) -> None:
        with pytest.raises(NotImplementedError, match="ssh"):
            await remote_exec("test-vm", "echo hi", backend="ssh")

    @pytest.mark.asyncio
    async def test_workdir_passed(self) -> None:
        mock_proc = MockProcess(returncode=0, stdout=b"ok")
        captured_args: list[str] = []

        async def _mock_exec(*args: str, **kwargs: object) -> MockProcess:
            captured_args.extend(args)
            return mock_proc

        with patch("asyncio.create_subprocess_exec", side_effect=_mock_exec):
            await remote_exec("test-vm", "ls", workdir="/home/ubuntu")

        assert "--working-directory" in captured_args
        assert "/home/ubuntu" in captured_args


# ---------------------------------------------------------------------------
# remote_health_check
# ---------------------------------------------------------------------------


class TestRemoteHealthCheck:
    @pytest.mark.asyncio
    async def test_running_vm_no_files(self) -> None:
        info_json = b'{"info":{"test-vm":{"state":"Running"}}}'
        mock_proc = MockProcess(returncode=0, stdout=info_json)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await remote_health_check("test-vm")

        assert result["reachable"] is True
        assert result["vm_status"] == "Running"
        assert result["files_readable"] == []
        assert result["files_missing"] == []

    @pytest.mark.asyncio
    async def test_stopped_vm_skips_file_tests(self) -> None:
        info_json = b'{"info":{"test-vm":{"state":"Stopped"}}}'
        mock_proc = MockProcess(returncode=0, stdout=info_json)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await remote_health_check(
                "test-vm", test_files=["/etc/hosts"]
            )

        assert result["reachable"] is False
        assert result["vm_status"] == "Stopped"
        assert result["files_missing"] == ["/etc/hosts"]

    @pytest.mark.asyncio
    async def test_file_exists(self) -> None:
        info_json = b'{"info":{"test-vm":{"state":"Running"}}}'
        info_proc = MockProcess(returncode=0, stdout=info_json)
        file_proc = MockProcess(returncode=0)  # test -r succeeds

        call_count = 0

        async def _mock_exec(*args: str, **kwargs: object) -> MockProcess:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return info_proc
            return file_proc

        with patch("asyncio.create_subprocess_exec", side_effect=_mock_exec):
            result = await remote_health_check(
                "test-vm", test_files=["/etc/hosts"]
            )

        assert result["reachable"] is True
        assert "/etc/hosts" in result["files_readable"]
        assert result["files_missing"] == []

    @pytest.mark.asyncio
    async def test_file_missing(self) -> None:
        info_json = b'{"info":{"test-vm":{"state":"Running"}}}'
        info_proc = MockProcess(returncode=0, stdout=info_json)
        file_proc = MockProcess(returncode=1)  # test -r fails

        call_count = 0

        async def _mock_exec(*args: str, **kwargs: object) -> MockProcess:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return info_proc
            return file_proc

        with patch("asyncio.create_subprocess_exec", side_effect=_mock_exec):
            result = await remote_health_check(
                "test-vm", test_files=["/no/such/file"]
            )

        assert result["reachable"] is True
        assert result["files_readable"] == []
        assert "/no/such/file" in result["files_missing"]

    @pytest.mark.asyncio
    async def test_vm_not_found(self) -> None:
        mock_proc = MockProcess(
            returncode=2,
            stderr=b"instance does not exist: ghost",
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(VMNotFoundError):
                await remote_health_check("ghost")

    @pytest.mark.asyncio
    async def test_backend_validation(self) -> None:
        with pytest.raises(NotImplementedError, match="docker"):
            await remote_health_check("test-vm", backend="docker")


# ---------------------------------------------------------------------------
# remote_file_read
# ---------------------------------------------------------------------------


class TestRemoteFileRead:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        content = b"file content here\n"
        mock_proc = MockProcess(returncode=0, stdout=content)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await remote_file_read("test-vm", "/etc/hostname")

        assert result["content"] == "file content here\n"
        assert result["path"] == "/etc/hostname"
        assert result["size_bytes"] == len(content)
        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_file_not_found_raises(self) -> None:
        mock_proc = MockProcess(
            returncode=1, stderr=b"No such file or directory"
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RemoteToolError) as exc_info:
                await remote_file_read("test-vm", "/no/such/file")

        assert exc_info.value.exit_code == 1

    @pytest.mark.asyncio
    async def test_truncation_detected(self) -> None:
        # Return exactly max_bytes of content → truncated = True
        max_bytes = 1024
        content = b"x" * max_bytes
        mock_proc = MockProcess(returncode=0, stdout=content)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await remote_file_read(
                "test-vm", "/big/file", max_bytes=max_bytes
            )

        assert result["truncated"] is True
        assert result["size_bytes"] == max_bytes

    @pytest.mark.asyncio
    async def test_no_truncation_when_small(self) -> None:
        content = b"small"
        mock_proc = MockProcess(returncode=0, stdout=content)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await remote_file_read(
                "test-vm", "/small/file", max_bytes=65536
            )

        assert result["truncated"] is False
        assert result["size_bytes"] == 5

    @pytest.mark.asyncio
    async def test_vm_not_found(self) -> None:
        mock_proc = MockProcess(
            returncode=2,
            stderr=b"instance does not exist: ghost",
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(VMNotFoundError):
                await remote_file_read("ghost", "/etc/hosts")

    @pytest.mark.asyncio
    async def test_backend_validation(self) -> None:
        with pytest.raises(NotImplementedError, match="ssh"):
            await remote_file_read("test-vm", "/etc/hosts", backend="ssh")
