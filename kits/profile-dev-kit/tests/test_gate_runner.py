"""The Gate command runner (Story 3.1, Task 2): no shell, bounded, never raises."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from beddel_profile_dev.tools._subprocess import run_command

PY = sys.executable


def test_captures_exit_code_and_raw_streams(tmp_path: Path) -> None:
    result = run_command(
        [
            PY,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)",
        ],
        tmp_path,
        timeout=20,
    )
    assert result.started and not result.timed_out
    assert result.exit_code == 3  # a non-zero exit is an outcome, not an error
    assert result.stdout == b"out\n"
    assert result.stderr == b"err\n"


def test_zero_exit_is_reported_as_is(tmp_path: Path) -> None:
    result = run_command([PY, "-c", "pass"], tmp_path, timeout=20)
    assert (result.started, result.exit_code, result.timed_out) == (True, 0, False)


def test_runs_in_the_given_directory(tmp_path: Path) -> None:
    result = run_command([PY, "-c", "import os; print(os.getcwd())"], tmp_path, 20)
    assert Path(result.stdout.decode().strip()).resolve() == tmp_path.resolve()


def test_there_is_no_shell(tmp_path: Path) -> None:
    result = run_command(
        [PY, "-c", "import sys; print(sys.argv[1])", "a; echo b"], tmp_path, 20
    )
    assert result.stdout == b"a; echo b\n"  # metacharacters are plain arguments


def test_stdin_is_closed(tmp_path: Path) -> None:
    result = run_command(
        [PY, "-c", "import sys; print(repr(sys.stdin.read()))"], tmp_path, 20
    )
    assert result.exit_code == 0
    assert result.stdout == b"''\n"


def test_git_environment_is_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GIT_DIR", "/nonexistent")
    monkeypatch.setenv("KEEP_ME", "yes")
    code = "import os; print(sorted(k for k in os.environ if k.startswith('GIT_'))); print(os.environ.get('KEEP_ME'))"
    result = run_command([PY, "-c", code], tmp_path, 20)
    assert result.stdout == b"[]\nyes\n"


def test_timeout_is_reported_and_the_command_is_killed(tmp_path: Path) -> None:
    started = time.monotonic()
    result = run_command(
        [PY, "-c", "import sys,time; print('partial', flush=True); time.sleep(60)"],
        tmp_path,
        timeout=1,
    )
    assert time.monotonic() - started < 30
    assert (result.started, result.exit_code, result.timed_out) == (True, None, True)
    assert result.stdout == b"partial\n"  # what it wrote before the budget ran out


def test_timeout_kills_the_children_too(tmp_path: Path) -> None:
    marker = tmp_path / "child-survived"
    child = f"import time, pathlib; time.sleep(3); pathlib.Path({str(marker)!r}).write_text('x')"
    parent = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(60)"
    )
    result = run_command([PY, "-c", parent], tmp_path, timeout=1)
    assert result.timed_out
    time.sleep(4)
    assert not marker.exists()


def test_an_interrupt_kills_the_command_instead_of_leaving_it_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = tmp_path / "pid"
    code = (
        "import os, pathlib, time; "
        f"pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(60)"
    )

    def interrupted(self: subprocess.Popen[bytes], *args: object, **kwargs: object):
        deadline = time.monotonic() + 20
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess.Popen, "communicate", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_command([PY, "-c", code], tmp_path, timeout=30)
    assert pid_file.exists()
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)  # gone, and reaped


def test_missing_executable_is_not_started_and_does_not_raise(tmp_path: Path) -> None:
    result = run_command(["definitely-not-an-executable-xyz"], tmp_path, timeout=5)
    assert (result.started, result.exit_code, result.timed_out) == (False, None, False)
    assert (result.stdout, result.stderr) == (b"", b"")


def test_empty_argv_is_not_started(tmp_path: Path) -> None:
    assert not run_command([], tmp_path, timeout=5).started


def test_missing_working_directory_is_not_started(tmp_path: Path) -> None:
    assert not run_command([PY, "-c", "pass"], tmp_path / "nope", timeout=5).started
