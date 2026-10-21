"""Run one Gate command and capture what it did — nothing more.

The runner never interprets the command: it starts the process without a
shell, with ``GIT_*`` removed from its environment and stdin closed, waits at
most ``timeout`` seconds, and returns the exit code and the raw bytes of both
streams. A non-zero exit never raises. A command that overruns its budget is
killed together with its process group and reported as ``timed_out``. A
command that cannot be started reports ``started=False``. Whether the
executable is allowed is decided by the config, before this runs.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = ["CommandResult", "resolve_executable", "run_command"]

# After the group is killed the pipes close at once; this only bounds a
# pathological holder of an inherited pipe so the Gate can never hang.
_DRAIN_SECONDS = 5


@dataclass(frozen=True)
class CommandResult:
    """What one command did.

    ``exit_code`` is ``None`` when the command was not started or timed out.
    """

    started: bool
    exit_code: int | None
    timed_out: bool
    stdout: bytes
    stderr: bytes


def _not_started() -> CommandResult:
    return CommandResult(
        started=False, exit_code=None, timed_out=False, stdout=b"", stderr=b""
    )


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        process.kill()


def resolve_executable(name: str) -> str | None:
    """Return the absolute path ``name`` resolves to on ``PATH``, or ``None``.

    A relative result (``PATH`` holding ``.`` or an empty entry) is refused: it
    would be resolved against the repository the command runs in.
    """
    found = shutil.which(name, path=os.environ.get("PATH"))
    if found is None or not os.path.isabs(found):
        return None
    return found


def run_command(argv: Sequence[str], cwd: Path, timeout: float) -> CommandResult:
    """Run ``argv`` in ``cwd`` for at most ``timeout`` seconds, without a shell."""
    if not argv:
        return _not_started()
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    executable = resolve_executable(argv[0])
    if executable is None:
        return _not_started()
    try:
        process = subprocess.Popen(
            [executable, *argv[1:]],
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,  # own process group, so a timeout kills children too
        )
    except (OSError, ValueError):
        return _not_started()
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as expired:
        _kill_group(process)
        partial_out = expired.stdout if isinstance(expired.stdout, bytes) else b""
        partial_err = expired.stderr if isinstance(expired.stderr, bytes) else b""
        try:
            out, err = process.communicate(timeout=_DRAIN_SECONDS)
        except subprocess.TimeoutExpired:
            out, err = partial_out, partial_err
        process.wait()
        return CommandResult(
            started=True,
            exit_code=None,
            timed_out=True,
            stdout=out or partial_out,
            stderr=err or partial_err,
        )
    except BaseException:
        # An interrupt must not leave the command running unbounded in its own
        # session, out of reach of the terminal's Ctrl-C.
        _kill_group(process)
        process.wait()
        raise
    return CommandResult(
        started=True,
        exit_code=process.returncode,
        timed_out=False,
        stdout=out,
        stderr=err,
    )
