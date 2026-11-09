"""Matrix tests for tools-github-kit using a scripted fake gh executable."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import time
from pathlib import Path
from typing import Any

import pytest
from beddel_tools_github import (
    GitHubToolError,
    github_pr_checks_wait,
    github_pr_create_or_reuse,
    github_pr_merge,
)
from beddel_tools_github.tools import (
    GITHUB_ARGUMENT_REFUSED,
    GITHUB_CHECKS_FAILED,
    GITHUB_CHECKS_PENDING,
    GITHUB_CLI_FAILED,
    GITHUB_CLI_MISSING,
    GITHUB_CLI_TIMEOUT,
    GITHUB_MERGE_INCOMPLETE,
    GITHUB_OUTPUT_INVALID,
    GITHUB_PR_AMBIGUOUS,
    GITHUB_PR_CONFLICT,
    GITHUB_PR_MISMATCH,
    GITHUB_PR_NOT_OPEN,
)

_SHA = "a" * 40
_SHA2 = "b" * 40


def _write_script(script_path: Path, *responses: dict[str, Any]) -> None:
    script_path.write_text(json.dumps(list(responses)))


def _read_log(log_path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log_path.read_text().splitlines()]


def _pr(*, base: str = "main", number: int = 7, state: str = "OPEN") -> dict[str, Any]:
    return {
        "number": number,
        "url": "https://github.example/pull/7",
        "headRefName": "feature/one",
        "baseRefName": base,
        "state": state,
    }


def _view(
    rollup: list[dict[str, Any]], *, number: int = 7, state: str = "OPEN"
) -> dict[str, Any]:
    return {
        "number": number,
        "state": state,
        "headRefOid": _SHA,
        "statusCheckRollup": rollup,
    }


def _success(name: str = "unit") -> dict[str, Any]:
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": "COMPLETED",
        "conclusion": "SUCCESS",
    }


def _pending(name: str = "unit") -> dict[str, Any]:
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": "IN_PROGRESS",
        "conclusion": None,
    }


def _assert_code(exc_info: pytest.ExceptionInfo[GitHubToolError], code: str) -> None:
    assert exc_info.value.code == code


@pytest.mark.asyncio
async def test_create_no_pr_creates_and_lists_again(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, log, script = fake_gh
    _write_script(
        script,
        {"stdout": "[]"},
        {"stdout": "https://github.example/pull/7\n"},
        {"stdout": json.dumps([_pr()])},
    )
    result = await github_pr_create_or_reuse(
        cwd=str(root),
        branch="feature/one",
        story_key="7-2b",
        spec_path="spec.md",
        change_id="chg-1",
        revision=_SHA,
    )
    assert result == {
        "number": 7,
        "url": "https://github.example/pull/7",
        "branch": "feature/one",
        "base": "main",
        "created": True,
    }
    assert [entry["argv"] for entry in _read_log(log)] == [
        [
            "pr",
            "list",
            "--head",
            "feature/one",
            "--state",
            "open",
            "--json",
            "number,url,headRefName,baseRefName,state",
            "--limit",
            "10",
        ],
        [
            "pr",
            "create",
            "--head",
            "feature/one",
            "--base",
            "main",
            "--title",
            "7-2b",
            "--body",
            f"Story: 7-2b\nSpec: spec.md\nChange: chg-1\nRevision: {_SHA}\n",
        ],
        [
            "pr",
            "list",
            "--head",
            "feature/one",
            "--state",
            "open",
            "--json",
            "number,url,headRefName,baseRefName,state",
            "--limit",
            "10",
        ],
    ]
    assert all(entry["cwd"] == str(root) for entry in _read_log(log))


@pytest.mark.asyncio
async def test_create_requires_one_pr_after_creation(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, _log, script = fake_gh
    _write_script(script, {"stdout": "[]"}, {"stdout": "created"}, {"stdout": "[]"})
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_create_or_reuse(
            cwd=str(root),
            branch="feature/one",
            story_key="7-2b",
            spec_path="spec.md",
            change_id="chg-1",
            revision=_SHA,
        )
    _assert_code(exc, GITHUB_OUTPUT_INVALID)


@pytest.mark.asyncio
async def test_open_pr_reused_on_rerun(fake_gh: tuple[Path, Path, Path]) -> None:
    root, log, script = fake_gh
    _write_script(
        script, {"stdout": json.dumps([_pr()])}, {"stdout": json.dumps([_pr()])}
    )
    first = await github_pr_create_or_reuse(
        cwd=str(root),
        branch="feature/one",
        story_key="7-2b",
        spec_path="spec.md",
        change_id="chg-1",
        revision=_SHA,
    )
    second = await github_pr_create_or_reuse(
        cwd=str(root),
        branch="feature/one",
        story_key="7-2b",
        spec_path="spec.md",
        change_id="chg-1",
        revision=_SHA,
    )
    assert first["created"] is False and second["created"] is False
    assert first["number"] == second["number"] == 7
    assert len(_read_log(log)) == 2


@pytest.mark.asyncio
async def test_other_base_is_conflict(fake_gh: tuple[Path, Path, Path]) -> None:
    root, _log, script = fake_gh
    _write_script(script, {"stdout": json.dumps([_pr(base="develop")])})
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_create_or_reuse(
            cwd=str(root),
            branch="feature/one",
            story_key="7-2b",
            spec_path="spec.md",
            change_id="chg-1",
            revision=_SHA,
        )
    _assert_code(exc, GITHUB_PR_CONFLICT)


@pytest.mark.asyncio
async def test_two_open_prs_are_ambiguous(fake_gh: tuple[Path, Path, Path]) -> None:
    root, _log, script = fake_gh
    _write_script(script, {"stdout": json.dumps([_pr(), _pr(number=8)])})
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_create_or_reuse(
            cwd=str(root),
            branch="feature/one",
            story_key="7-2b",
            spec_path="spec.md",
            change_id="chg-1",
            revision=_SHA,
        )
    _assert_code(exc, GITHUB_PR_AMBIGUOUS)


@pytest.mark.asyncio
async def test_invalid_reference_runs_nothing(fake_gh: tuple[Path, Path, Path]) -> None:
    root, log, script = fake_gh
    _write_script(script, {"stdout": "[]"})
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_create_or_reuse(
            cwd=str(root),
            branch="feature/one",
            story_key="7-2b",
            spec_path="a/../b",
            change_id="chg-1",
            revision=_SHA,
        )
    _assert_code(exc, GITHUB_ARGUMENT_REFUSED)
    assert not log.exists()


@pytest.mark.asyncio
async def test_checks_passed(fake_gh: tuple[Path, Path, Path]) -> None:
    root, _log, script = fake_gh
    _write_script(
        script,
        {
            "stdout": json.dumps(
                _view(
                    [
                        _success("lint"),
                        {
                            "__typename": "StatusContext",
                            "context": "ci",
                            "state": "SUCCESS",
                        },
                    ]
                )
            )
        },
    )
    result = await github_pr_checks_wait(
        cwd=str(root), number=7, interval=0.01, max_wait=1, grace=0
    )
    assert result == {
        "number": 7,
        "head_sha": _SHA,
        "passed": True,
        "no_checks": False,
        "checks": ["lint", "ci"],
    }
    entry = _read_log(_log)[0]
    assert entry["argv"] == [
        "pr",
        "view",
        "7",
        "--json",
        "number,state,headRefOid,statusCheckRollup",
    ]
    assert entry["cwd"] == str(root)


@pytest.mark.asyncio
async def test_pending_then_passed_sleeps_between_polls(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, log, script = fake_gh
    _write_script(
        script,
        {"stdout": json.dumps(_view([_pending()]))},
        {"stdout": json.dumps(_view([_success()]))},
    )
    result = await github_pr_checks_wait(
        cwd=str(root), number=7, interval=0.01, max_wait=1, grace=0
    )
    assert result["passed"] is True
    assert len(_read_log(log)) == 2


@pytest.mark.asyncio
async def test_pending_at_max_wait_is_rejected(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, _log, script = fake_gh
    _write_script(script, {"stdout": json.dumps(_view([_pending()]))})
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_checks_wait(
            cwd=str(root), number=7, interval=1, max_wait=0.01, grace=0
        )
    _assert_code(exc, GITHUB_CHECKS_PENDING)


@pytest.mark.asyncio
async def test_failed_checks_refuse_immediately(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, _log, script = fake_gh
    _write_script(
        script,
        {
            "stdout": json.dumps(
                _view(
                    [
                        {
                            "__typename": "CheckRun",
                            "name": "lint",
                            "status": "COMPLETED",
                            "conclusion": "FAILURE",
                        }
                    ]
                )
            )
        },
    )
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_checks_wait(
            cwd=str(root), number=7, interval=1, max_wait=1, grace=0
        )
    _assert_code(exc, GITHUB_CHECKS_FAILED)
    assert exc.value.details["failed"] == ["lint"]


@pytest.mark.asyncio
async def test_no_checks_waits_for_grace_then_passes(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, log, script = fake_gh
    _write_script(
        script,
        *({"stdout": json.dumps(_view([]))} for _ in range(20)),
    )
    result = await github_pr_checks_wait(
        cwd=str(root), number=7, interval=0.05, max_wait=1, grace=0.3
    )
    assert result["no_checks"] is True and result["checks"] == []
    assert len(_read_log(log)) >= 2


@pytest.mark.asyncio
async def test_no_checks_waits_full_grace_before_first_acceptance(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, log, script = fake_gh
    _write_script(
        script,
        *({"stdout": json.dumps(_view([]))} for _ in range(20)),
    )
    started = time.monotonic()
    result = await github_pr_checks_wait(
        cwd=str(root), number=7, interval=0.05, max_wait=10, grace=0.3
    )
    elapsed = time.monotonic() - started
    assert result["no_checks"] is True and result["checks"] == []
    assert elapsed >= 0.3
    assert len(_read_log(log)) >= 2


@pytest.mark.asyncio
async def test_no_checks_at_grace_equal_to_max_wait_passes(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, log, script = fake_gh
    empty = json.dumps(_view([]))
    # A slow first poll keeps a revert (grace counted from the end of the first
    # poll) from hiding behind the max_wait check.
    _write_script(
        script,
        {"mode": "sleep", "seconds": 0.2, "stdout": empty},
        *({"stdout": empty} for _ in range(20)),
    )
    result = await github_pr_checks_wait(
        cwd=str(root), number=7, interval=0.05, max_wait=0.3, grace=0.3
    )
    assert result["no_checks"] is True
    assert len(_read_log(log)) >= 2


@pytest.mark.asyncio
async def test_merge_runs_pinned_merge_and_verifies_state(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, log, script = fake_gh
    _write_script(
        script,
        {"stdout": json.dumps({**_view([_success()]), "mergeCommit": None})},
        {"stdout": ""},
        {
            "stdout": json.dumps(
                {"number": 7, "state": "MERGED", "mergeCommit": {"oid": _SHA2}}
            )
        },
    )
    result = await github_pr_merge(
        cwd=str(root), number=7, merge_method="squash", expected_head_sha=_SHA
    )
    assert result == {
        "number": 7,
        "merged": True,
        "already_merged": False,
        "merge_sha": _SHA2,
        "merge_method": "squash",
    }
    entries = _read_log(log)
    assert [entry["argv"] for entry in entries] == [
        [
            "pr",
            "view",
            "7",
            "--json",
            "number,state,headRefOid,mergeCommit,statusCheckRollup",
        ],
        [
            "pr",
            "merge",
            "7",
            "--squash",
            "--match-head-commit",
            _SHA,
        ],
        ["pr", "view", "7", "--json", "number,state,mergeCommit"],
    ]
    assert all(entry["cwd"] == str(root) for entry in entries)


@pytest.mark.asyncio
async def test_merge_rerun_returns_already_merged(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, log, script = fake_gh
    _write_script(
        script,
        {
            "stdout": json.dumps(
                {
                    "number": 7,
                    "state": "MERGED",
                    "headRefOid": _SHA,
                    "mergeCommit": {"oid": _SHA2},
                    "statusCheckRollup": [],
                }
            )
        },
    )
    result = await github_pr_merge(cwd=str(root), number=7, expected_head_sha=_SHA)
    assert result["already_merged"] is True and result["merge_sha"] == _SHA2
    assert len(_read_log(log)) == 1


@pytest.mark.asyncio
async def test_merged_pr_head_mismatch_is_rejected(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, log, script = fake_gh
    _write_script(
        script,
        {
            "stdout": json.dumps(
                {
                    "number": 7,
                    "state": "MERGED",
                    "headRefOid": _SHA,
                    "mergeCommit": {"oid": _SHA2},
                    "statusCheckRollup": [],
                }
            )
        },
    )
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_merge(cwd=str(root), number=7, expected_head_sha=_SHA2)
    _assert_code(exc, GITHUB_PR_MISMATCH)
    assert len(_read_log(log)) == 1


@pytest.mark.asyncio
async def test_merge_rejects_failed_and_pending_checks(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, log, script = fake_gh
    _write_script(
        script, {"stdout": json.dumps({**_view([_pending()]), "mergeCommit": None})}
    )
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_merge(cwd=str(root), number=7)
    _assert_code(exc, GITHUB_CHECKS_PENDING)
    assert len(_read_log(log)) == 1


@pytest.mark.asyncio
async def test_merge_rejects_not_open_and_number_mismatch(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, _log, script = fake_gh
    _write_script(
        script,
        {"stdout": json.dumps({**_view([], state="CLOSED"), "mergeCommit": None})},
    )
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_merge(cwd=str(root), number=7)
    _assert_code(exc, GITHUB_PR_NOT_OPEN)
    _write_script(
        script, {"stdout": json.dumps({**_view([], number=8), "mergeCommit": None})}
    )
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_merge(cwd=str(root), number=7)
    _assert_code(exc, GITHUB_PR_MISMATCH)


@pytest.mark.asyncio
async def test_merge_head_mismatch_and_incomplete(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, _log, script = fake_gh
    _write_script(script, {"stdout": json.dumps({**_view([]), "mergeCommit": None})})
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_merge(cwd=str(root), number=7, expected_head_sha=_SHA2)
    _assert_code(exc, GITHUB_PR_MISMATCH)
    _write_script(
        script,
        {"stdout": json.dumps({**_view([]), "mergeCommit": None})},
        {"stdout": ""},
        {"stdout": json.dumps({"number": 7, "state": "OPEN", "mergeCommit": None})},
    )
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_merge(cwd=str(root), number=7)
    _assert_code(exc, GITHUB_MERGE_INCOMPLETE)


@pytest.mark.asyncio
async def test_missing_cli_and_nonzero_are_safe(
    fake_gh: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _log, script = fake_gh
    fake_path = os.environ["PATH"]
    monkeypatch.setenv("PATH", str(root / "no-such-bin"))
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_checks_wait(cwd=str(root), number=7, grace=0, max_wait=1)
    _assert_code(exc, GITHUB_CLI_MISSING)
    monkeypatch.setenv("PATH", fake_path)
    secret = "gh" + "p_" + "A" * 36
    _write_script(script, {"exit": 1, "stderr": f"bad {secret}"})
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_checks_wait(cwd=str(root), number=7, grace=0, max_wait=1)
    _assert_code(exc, GITHUB_CLI_FAILED)
    assert secret not in str(exc.value) and "[redacted]" in exc.value.details["stderr"]


@pytest.mark.asyncio
async def test_bad_output_and_cli_shape_are_rejected(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, _log, script = fake_gh
    _write_script(script, {"stdout": "not-json"})
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_create_or_reuse(
            cwd=str(root),
            branch="feature/one",
            story_key="7-2b",
            spec_path="spec.md",
            change_id="chg-1",
            revision=_SHA,
        )
    _assert_code(exc, GITHUB_OUTPUT_INVALID)


@pytest.mark.asyncio
async def test_timeout_and_grandchild_are_bounded(
    fake_gh: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, log, script = fake_gh
    _write_script(script, {"mode": "sleep", "seconds": 60})
    started = time.monotonic()
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_checks_wait(
            cwd=str(root), number=7, timeout=0.2, grace=0, max_wait=1
        )
    assert exc.value.code == GITHUB_CLI_TIMEOUT
    assert time.monotonic() - started < 6
    pid = int(_read_log(log)[0]["pid"])
    _assert_pid_gone(pid)
    child_log = root / "child.pid"
    monkeypatch.setenv("FAKE_GH_CHILD_LOG", str(child_log))
    _write_script(script, {"mode": "grandchild", "seconds": 60})
    child_pid: int | None = None
    try:
        started = time.monotonic()
        with pytest.raises(GitHubToolError) as exc:
            await github_pr_checks_wait(
                cwd=str(root), number=7, timeout=0.2, grace=0, max_wait=1
            )
        assert exc.value.code == GITHUB_CLI_TIMEOUT
        assert time.monotonic() - started < 6
        gh_pid = int(_read_log(log)[1]["pid"])
        _assert_pid_gone(gh_pid)
        child_pid = int(child_log.read_text())
    finally:
        if child_log.exists():
            child_pid = int(child_log.read_text())
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if child_pid is not None:
            _assert_pid_gone(child_pid)


@pytest.mark.asyncio
async def test_cancellation_kills_gh_and_reraises(
    fake_gh: tuple[Path, Path, Path],
) -> None:
    root, log, script = fake_gh
    _write_script(script, {"mode": "sleep", "seconds": 60})
    task = asyncio.create_task(
        github_pr_checks_wait(cwd=str(root), number=7, grace=0, max_wait=60)
    )
    for _ in range(100):
        if log.exists():
            break
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    _assert_pid_gone(int(_read_log(log)[0]["pid"]))


def _assert_pid_gone(pid: int) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)
    raise AssertionError(f"process {pid} is still running")


@pytest.mark.asyncio
async def test_subprocess_contract_uses_closed_stdin_and_no_env(
    fake_gh: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _log, script = fake_gh
    _write_script(script, {"stdout": json.dumps(_view([]))})
    real_exec = asyncio.create_subprocess_exec
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def spy(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        calls.append((args, kwargs))
        return await real_exec(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spy)
    await github_pr_checks_wait(cwd=str(root), number=7, grace=0, max_wait=1)
    assert calls[0][0][:2] == ("gh", "pr")
    assert calls[0][1]["stdin"] is asyncio.subprocess.DEVNULL
    assert "env" not in calls[0][1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("timeout", float("nan")),
        ("timeout", float("inf")),
        ("interval", float("nan")),
        ("interval", float("inf")),
        ("max_wait", float("nan")),
        ("max_wait", float("inf")),
        ("grace", float("nan")),
        ("grace", float("inf")),
    ],
)
async def test_nonfinite_wait_values_are_refused(
    fake_gh: tuple[Path, Path, Path], argument: str, value: float
) -> None:
    root, log, _script = fake_gh
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_checks_wait(
            cwd=str(root),
            number=7,
            interval=value if argument == "interval" else 0.01,
            max_wait=value if argument == "max_wait" else 1,
            grace=value if argument == "grace" else 0,
            timeout=value if argument == "timeout" else 1,
        )
    _assert_code(exc, GITHUB_ARGUMENT_REFUSED)
    assert exc.value.details == {"argument": argument}
    assert not log.exists()


@pytest.mark.asyncio
async def test_argument_validation_never_runs(fake_gh: tuple[Path, Path, Path]) -> None:
    root, log, _script = fake_gh
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_checks_wait(cwd=str(root), number=True)
    _assert_code(exc, GITHUB_ARGUMENT_REFUSED)
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_merge(cwd=str(root), number=0, merge_method="--merge")
    _assert_code(exc, GITHUB_ARGUMENT_REFUSED)
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_create_or_reuse(
            cwd=str(root),
            branch="feature/one",
            story_key="7-2b",
            spec_path="spec.md",
            change_id="chg-1",
            revision="z" * 40,
        )
    _assert_code(exc, GITHUB_ARGUMENT_REFUSED)
    token = "gh" + "p_" + "A" * 36
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_create_or_reuse(
            cwd=str(root),
            branch=token,
            story_key="7-2b",
            spec_path="spec.md",
            change_id="chg-1",
            revision=_SHA,
        )
    _assert_code(exc, GITHUB_ARGUMENT_REFUSED)
    assert token not in str(exc.value)
    assert exc.value.details == {"argument": "branch"}
    not_a_directory = root / "not-a-directory"
    not_a_directory.write_text("file")
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_checks_wait(cwd=str(not_a_directory), number=7)
    _assert_code(exc, GITHUB_ARGUMENT_REFUSED)
    assert not log.exists()


@pytest.mark.asyncio
async def test_merge_rejects_failed_checks(fake_gh: tuple[Path, Path, Path]) -> None:
    root, log, script = fake_gh
    failed = {
        "__typename": "CheckRun",
        "name": "lint",
        "status": "COMPLETED",
        "conclusion": "FAILURE",
    }
    _write_script(
        script, {"stdout": json.dumps({**_view([failed]), "mergeCommit": None})}
    )
    with pytest.raises(GitHubToolError) as exc:
        await github_pr_merge(cwd=str(root), number=7)
    _assert_code(exc, GITHUB_CHECKS_FAILED)
    assert exc.value.details["failed"] == ["lint"]
    assert len(_read_log(log)) == 1


@pytest.mark.asyncio
async def test_merge_accepts_an_empty_rollup(fake_gh: tuple[Path, Path, Path]) -> None:
    root, log, script = fake_gh
    _write_script(
        script,
        {"stdout": json.dumps({**_view([]), "mergeCommit": None})},
        {"stdout": ""},
        {
            "stdout": json.dumps(
                {"number": 7, "state": "MERGED", "mergeCommit": {"oid": _SHA2}}
            )
        },
    )
    result = await github_pr_merge(cwd=str(root), number=7)
    assert result["merged"] is True and result["already_merged"] is False
    assert len(_read_log(log)) == 3
