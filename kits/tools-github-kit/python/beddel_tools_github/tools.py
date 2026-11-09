"""Async GitHub pull request tools backed by the machine's ``gh`` login."""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
import os
import re
import subprocess
import time
from collections.abc import Mapping
from typing import Any, NoReturn

from beddel.domain.errors import BeddelError
from beddel.tools import beddel_tool

__all__ = [
    "GITHUB_ARGUMENT_REFUSED",
    "GITHUB_CHECKS_FAILED",
    "GITHUB_CHECKS_PENDING",
    "GITHUB_CLI_FAILED",
    "GITHUB_CLI_MISSING",
    "GITHUB_CLI_TIMEOUT",
    "GITHUB_MERGE_INCOMPLETE",
    "GITHUB_OUTPUT_INVALID",
    "GITHUB_PR_AMBIGUOUS",
    "GITHUB_PR_CONFLICT",
    "GITHUB_PR_MISMATCH",
    "GITHUB_PR_NOT_OPEN",
    "GitHubCLI",
    "GitHubToolError",
    "github_pr_checks_wait",
    "github_pr_create_or_reuse",
    "github_pr_merge",
]

GITHUB_ARGUMENT_REFUSED = "GITHUB_ARGUMENT_REFUSED"
GITHUB_CHECKS_FAILED = "GITHUB_CHECKS_FAILED"
GITHUB_CHECKS_PENDING = "GITHUB_CHECKS_PENDING"
GITHUB_CLI_FAILED = "GITHUB_CLI_FAILED"
GITHUB_CLI_MISSING = "GITHUB_CLI_MISSING"
GITHUB_CLI_TIMEOUT = "GITHUB_CLI_TIMEOUT"
GITHUB_MERGE_INCOMPLETE = "GITHUB_MERGE_INCOMPLETE"
GITHUB_OUTPUT_INVALID = "GITHUB_OUTPUT_INVALID"
GITHUB_PR_AMBIGUOUS = "GITHUB_PR_AMBIGUOUS"
GITHUB_PR_CONFLICT = "GITHUB_PR_CONFLICT"
GITHUB_PR_MISMATCH = "GITHUB_PR_MISMATCH"
GITHUB_PR_NOT_OPEN = "GITHUB_PR_NOT_OPEN"

_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_.-]{0,254}$")
_STORY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_CHANGE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SPEC_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,254}$")
_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SENSITIVE_RE = re.compile(r"gh[pousr]_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{10,}")
_REAP_GRACE_SECONDS = 2.0


class GitHubToolError(BeddelError):
    """Kit-local error with a stable code and secret-free message."""

    def __init__(
        self, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(code, message, details)


def _refuse(argument: str) -> NoReturn:
    raise GitHubToolError(
        GITHUB_ARGUMENT_REFUSED,
        "Invalid GitHub argument.",
        {"argument": argument},
    )


def _validate_string(value: object, argument: str) -> str:
    if (
        not isinstance(value, str)
        or value.startswith("-")
        or _SENSITIVE_RE.search(value)
    ):
        _refuse(argument)
    return value


def _validate_pattern(value: object, argument: str, pattern: re.Pattern[str]) -> str:
    value = _validate_string(value, argument)
    if pattern.fullmatch(value) is None:
        _refuse(argument)
    return value


def _validate_cwd(cwd: object) -> str:
    cwd_value = _validate_string(cwd, "cwd")
    if not os.path.isdir(cwd_value):
        _refuse("cwd")
    return cwd_value


def _validate_number(number: object) -> int:
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        _refuse("number")
    return number


def _validate_positive(value: object, argument: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        _refuse(argument)
    return float(value)


def _validate_wait_values(
    interval: object, max_wait: object, grace: object
) -> tuple[float, float, float]:
    interval_value = _validate_positive(interval, "interval")
    max_wait_value = _validate_positive(max_wait, "max_wait")
    if (
        isinstance(grace, bool)
        or not isinstance(grace, (int, float))
        or not math.isfinite(grace)
    ):
        _refuse("grace")
    grace_value = float(grace)
    if grace_value < 0 or grace_value > max_wait_value:
        _refuse("grace")
    return interval_value, max_wait_value, grace_value


def _validate_timeout(timeout: object) -> float:
    return _validate_positive(timeout, "timeout")


def _validate_spec_path(value: object) -> str:
    spec_path = _validate_string(value, "spec_path")
    if any(segment in {"", ".", ".."} for segment in spec_path.split("/")):
        _refuse("spec_path")
    if _SPEC_RE.fullmatch(spec_path) is None:
        _refuse("spec_path")
    return spec_path


def _validate_sha(value: object, argument: str) -> str:
    return _validate_pattern(value, argument, _SHA_RE)


def _redact(text: str) -> str:
    return _SENSITIVE_RE.sub("[redacted]", text)


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    """Kill a process and bound the wait for a child holding its pipes."""
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    with contextlib.suppress(TimeoutError):
        async with asyncio.timeout(_REAP_GRACE_SECONDS):
            await proc.wait()


def _command_name(argv: tuple[str, ...]) -> str:
    return "gh " + " ".join(argv[:2])


def _invalid_output(command: str) -> GitHubToolError:
    return GitHubToolError(
        GITHUB_OUTPUT_INVALID,
        "GitHub CLI output is invalid.",
        {"command": command},
    )


class GitHubCLI:
    """Run explicit ``gh`` argv in a repository with inherited login state."""

    def __init__(self, *, timeout: float = 120) -> None:
        self._timeout = timeout

    async def run(self, *argv: str, cwd: str) -> str:
        """Run ``gh`` and return stdout, converting process failures to kit errors."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "gh",
                *argv,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise GitHubToolError(
                GITHUB_CLI_MISSING,
                "The gh CLI is not installed.",
            ) from exc

        try:
            async with asyncio.timeout(self._timeout):
                stdout_bytes, stderr_bytes = await proc.communicate()
        except TimeoutError as exc:
            await _terminate(proc)
            raise GitHubToolError(
                GITHUB_CLI_TIMEOUT,
                "The gh command timed out.",
                {"timeout": self._timeout},
            ) from exc
        except asyncio.CancelledError:
            await _terminate(proc)
            raise

        if proc.returncode != 0:
            stderr = _redact(stderr_bytes.decode(errors="replace"))[-500:]
            raise GitHubToolError(
                GITHUB_CLI_FAILED,
                "The gh command failed.",
                {
                    "command": _command_name(argv),
                    "exit_code": proc.returncode,
                    "stderr": stderr,
                },
            )
        return stdout_bytes.decode(errors="replace")


def _load_json(text: str, command: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise _invalid_output(command) from exc


def _as_mapping(value: Any, command: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _invalid_output(command)
    return value


def _pr_list(value: Any, command: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise _invalid_output(command)
    result: list[Mapping[str, Any]] = []
    for item in value:
        item_map = _as_mapping(item, command)
        if (
            isinstance(item_map.get("number"), bool)
            or not isinstance(item_map.get("number"), int)
            or not isinstance(item_map.get("url"), str)
            or not isinstance(item_map.get("headRefName"), str)
            or not isinstance(item_map.get("baseRefName"), str)
            or not isinstance(item_map.get("state"), str)
        ):
            raise _invalid_output(command)
        result.append(item_map)
    return result


def _pr_view(value: Any, command: str) -> Mapping[str, Any]:
    view = _as_mapping(value, command)
    if (
        isinstance(view.get("number"), bool)
        or not isinstance(view.get("number"), int)
        or not isinstance(view.get("state"), str)
        or not isinstance(view.get("headRefOid"), str)
        or not isinstance(view.get("statusCheckRollup"), list)
    ):
        raise _invalid_output(command)
    return view


def _check_name(item: Mapping[str, Any], check_type: str, command: str) -> str:
    key = "name" if check_type == "CheckRun" else "context"
    name = item.get(key)
    if not isinstance(name, str):
        raise _invalid_output(command)
    return name


def _rollup_status(rollup: list[Any], command: str) -> tuple[str, list[str], list[str]]:
    """Return status, all names, and failed names for a rollup."""
    if not rollup:
        return "empty", [], []
    names: list[str] = []
    failed: list[str] = []
    pending = False
    for raw_item in rollup:
        item = _as_mapping(raw_item, command)
        check_type = item.get("__typename")
        if not isinstance(check_type, str):
            raise _invalid_output(command)
        if check_type == "CheckRun":
            name = _check_name(item, check_type, command)
            names.append(name)
            status = item.get("status")
            conclusion = item.get("conclusion")
            if not isinstance(status, str) or status != "COMPLETED":
                pending = True
            elif conclusion not in {"SUCCESS", "NEUTRAL", "SKIPPED"}:
                failed.append(name)
        elif check_type == "StatusContext":
            name = _check_name(item, check_type, command)
            names.append(name)
            state = item.get("state")
            if state in {"PENDING", "EXPECTED"}:
                pending = True
            elif state != "SUCCESS":
                failed.append(name)
        else:
            failed.append(str(item.get("name", item.get("context", "unknown"))))
    if failed:
        return "failed", names, failed
    if pending:
        return "pending", names, []
    return "passed", names, []


def _check_failure(status: str, failed: list[str]) -> GitHubToolError:
    if status == "pending":
        return GitHubToolError(GITHUB_CHECKS_PENDING, "Checks are still pending.")
    return GitHubToolError(
        GITHUB_CHECKS_FAILED,
        "Checks failed.",
        {"failed": failed},
    )


def _validate_create_args(
    cwd: object,
    branch: object,
    base: object,
    story_key: object,
    spec_path: object,
    change_id: object,
    revision: object,
    timeout: object,
) -> tuple[str, str, str, str, str, str, str, float]:
    return (
        _validate_cwd(cwd),
        _validate_pattern(branch, "branch", _BRANCH_RE),
        _validate_pattern(base, "base", _BRANCH_RE),
        _validate_pattern(story_key, "story_key", _STORY_RE),
        _validate_spec_path(spec_path),
        _validate_pattern(change_id, "change_id", _CHANGE_RE),
        _validate_sha(revision, "revision"),
        _validate_timeout(timeout),
    )


@beddel_tool(
    name="github_pr_create_or_reuse",
    description="Create or reuse one open GitHub pull request",
    category="github",
)
async def github_pr_create_or_reuse(
    *,
    cwd: str,
    branch: str,
    base: str = "main",
    story_key: str,
    spec_path: str,
    change_id: str,
    revision: str,
    timeout: float = 120,
) -> dict[str, Any]:
    """Create one pull request or return the sole matching open request."""
    (
        cwd_value,
        branch_value,
        base_value,
        story_value,
        spec_value,
        change_value,
        revision_value,
        timeout_value,
    ) = _validate_create_args(
        cwd, branch, base, story_key, spec_path, change_id, revision, timeout
    )
    list_args = (
        "pr",
        "list",
        "--head",
        branch_value,
        "--state",
        "open",
        "--json",
        "number,url,headRefName,baseRefName,state",
        "--limit",
        "10",
    )
    cli = GitHubCLI(timeout=timeout_value)
    listed = _pr_list(
        _load_json(await cli.run(*list_args, cwd=cwd_value), "gh pr list"),
        "gh pr list",
    )
    if len(listed) > 1:
        raise GitHubToolError(
            GITHUB_PR_AMBIGUOUS,
            "More than one open pull request matches the branch.",
        )
    body = (
        f"Story: {story_value}\n"
        f"Spec: {spec_value}\n"
        f"Change: {change_value}\n"
        f"Revision: {revision_value}\n"
    )
    if listed:
        pull_request = listed[0]
        if pull_request["baseRefName"] != base_value:
            raise GitHubToolError(
                GITHUB_PR_CONFLICT,
                "An open pull request targets another base branch.",
            )
        created = False
    else:
        create_args = (
            "pr",
            "create",
            "--head",
            branch_value,
            "--base",
            base_value,
            "--title",
            story_value,
            "--body",
            body,
        )
        await cli.run(*create_args, cwd=cwd_value)
        listed = _pr_list(
            _load_json(await cli.run(*list_args, cwd=cwd_value), "gh pr list"),
            "gh pr list",
        )
        if len(listed) != 1:
            raise GitHubToolError(
                GITHUB_OUTPUT_INVALID,
                "GitHub CLI output is invalid.",
                {"command": "gh pr list"},
            )
        pull_request = listed[0]
        if pull_request["baseRefName"] != base_value:
            raise GitHubToolError(
                GITHUB_PR_CONFLICT,
                "An open pull request targets another base branch.",
            )
        created = True
    return {
        "number": pull_request["number"],
        "url": pull_request["url"],
        "branch": pull_request["headRefName"],
        "base": pull_request["baseRefName"],
        "created": created,
    }


async def _read_checks(
    cli: GitHubCLI, cwd: str, number: int
) -> tuple[Mapping[str, Any], list[Any], str]:
    command = "gh pr view"
    text = await cli.run(
        "pr",
        "view",
        str(number),
        "--json",
        "number,state,headRefOid,statusCheckRollup",
        cwd=cwd,
    )
    view = _pr_view(_load_json(text, command), command)
    if view["number"] != number:
        raise GitHubToolError(
            GITHUB_PR_MISMATCH,
            "The pull request does not match the requested number or head.",
        )
    if view["state"] != "OPEN":
        raise GitHubToolError(GITHUB_PR_NOT_OPEN, "The pull request is not open.")
    return view, view["statusCheckRollup"], command


@beddel_tool(
    name="github_pr_checks_wait",
    description="Wait for configured GitHub pull request checks",
    category="github",
)
async def github_pr_checks_wait(
    *,
    cwd: str,
    number: int,
    interval: float = 10,
    max_wait: float = 1800,
    grace: float = 30,
    timeout: float = 120,
) -> dict[str, Any]:
    """Poll the pull request rollup until it passes, fails, or times out."""
    cwd_value = _validate_cwd(cwd)
    number_value = _validate_number(number)
    interval_value, max_wait_value, grace_value = _validate_wait_values(
        interval, max_wait, grace
    )
    timeout_value = _validate_timeout(timeout)
    cli = GitHubCLI(timeout=timeout_value)
    started = time.monotonic()
    empty_since: float | None = None
    first_poll = True
    while True:
        view, rollup, command = await _read_checks(cli, cwd_value, number_value)
        status, names, failed = _rollup_status(rollup, command)
        now = time.monotonic()
        if status == "empty":
            if empty_since is None:
                empty_since = started if first_poll else now
            if now - empty_since >= grace_value:
                return {
                    "number": number_value,
                    "head_sha": view["headRefOid"],
                    "passed": True,
                    "no_checks": True,
                    "checks": [],
                }
        else:
            empty_since = None
            if status == "passed":
                return {
                    "number": number_value,
                    "head_sha": view["headRefOid"],
                    "passed": True,
                    "no_checks": False,
                    "checks": names,
                }
            if status == "failed":
                raise _check_failure(status, failed)
        first_poll = False
        elapsed = now - started
        if elapsed >= max_wait_value:
            raise GitHubToolError(GITHUB_CHECKS_PENDING, "Checks are still pending.")
        delay = min(interval_value, max_wait_value - elapsed)
        if status == "empty" and empty_since is not None:
            delay = min(delay, max(0.0, grace_value - (now - empty_since)))
        await asyncio.sleep(delay)


def _validate_merge_args(
    cwd: object,
    number: object,
    merge_method: object,
    expected_head_sha: object,
    timeout: object,
) -> tuple[str, int, str, str | None, float]:
    cwd_value = _validate_cwd(cwd)
    number_value = _validate_number(number)
    method_value = _validate_string(merge_method, "merge_method")
    if method_value not in {"merge", "squash", "rebase"}:
        _refuse("merge_method")
    if expected_head_sha is None:
        expected_value = None
    else:
        expected_value = _validate_sha(expected_head_sha, "expected_head_sha")
    return (
        cwd_value,
        number_value,
        method_value,
        expected_value,
        _validate_timeout(timeout),
    )


@beddel_tool(
    name="github_pr_merge",
    description="Merge one checked GitHub pull request",
    category="github",
)
async def github_pr_merge(
    *,
    cwd: str,
    number: int,
    merge_method: str = "merge",
    expected_head_sha: str | None = None,
    timeout: float = 120,
) -> dict[str, Any]:
    """Merge exactly one open pull request after its rollup passes."""
    cwd_value, number_value, method_value, expected_value, timeout_value = (
        _validate_merge_args(cwd, number, merge_method, expected_head_sha, timeout)
    )
    cli = GitHubCLI(timeout=timeout_value)
    command = "gh pr view"
    first_text = await cli.run(
        "pr",
        "view",
        str(number_value),
        "--json",
        "number,state,headRefOid,mergeCommit,statusCheckRollup",
        cwd=cwd_value,
    )
    first_view = _as_mapping(_load_json(first_text, command), command)
    if (
        isinstance(first_view.get("number"), bool)
        or not isinstance(first_view.get("number"), int)
        or not isinstance(first_view.get("state"), str)
        or not isinstance(first_view.get("headRefOid"), str)
        or not isinstance(first_view.get("statusCheckRollup"), list)
    ):
        raise _invalid_output(command)
    if first_view["number"] != number_value:
        raise GitHubToolError(
            GITHUB_PR_MISMATCH,
            "The pull request does not match the requested number or head.",
        )
    head_sha = first_view["headRefOid"]
    if expected_value is not None and head_sha != expected_value:
        raise GitHubToolError(
            GITHUB_PR_MISMATCH,
            "The pull request does not match the requested number or head.",
        )
    if first_view["state"] == "MERGED":
        merge_commit = _as_mapping(first_view.get("mergeCommit"), command)
        merge_sha = merge_commit.get("oid")
        if not isinstance(merge_sha, str):
            raise _invalid_output(command)
        return {
            "number": number_value,
            "merged": True,
            "already_merged": True,
            "merge_sha": merge_sha,
            "merge_method": method_value,
        }
    if first_view["state"] != "OPEN":
        raise GitHubToolError(GITHUB_PR_NOT_OPEN, "The pull request is not open.")
    head_sha = first_view["headRefOid"]
    if expected_value is not None and head_sha != expected_value:
        raise GitHubToolError(
            GITHUB_PR_MISMATCH,
            "The pull request does not match the requested number or head.",
        )
    status, _names, failed = _rollup_status(first_view["statusCheckRollup"], command)
    if status in {"pending", "failed"}:
        raise _check_failure(status, failed)
    await cli.run(
        "pr",
        "merge",
        str(number_value),
        f"--{method_value}",
        "--match-head-commit",
        head_sha,
        cwd=cwd_value,
    )
    after_text = await cli.run(
        "pr",
        "view",
        str(number_value),
        "--json",
        "number,state,mergeCommit",
        cwd=cwd_value,
    )
    after = _as_mapping(_load_json(after_text, "gh pr view"), "gh pr view")
    if isinstance(after.get("number"), bool) or not isinstance(
        after.get("number"), int
    ):
        raise _invalid_output("gh pr view")
    if after["number"] != number_value:
        raise GitHubToolError(
            GITHUB_PR_MISMATCH,
            "The pull request does not match the requested number or head.",
        )
    if after.get("state") != "MERGED":
        raise GitHubToolError(
            GITHUB_MERGE_INCOMPLETE,
            "The pull request did not merge.",
        )
    merge_commit = _as_mapping(after.get("mergeCommit"), "gh pr view")
    merge_sha = merge_commit.get("oid")
    if not isinstance(merge_sha, str):
        raise _invalid_output("gh pr view")
    return {
        "number": number_value,
        "merged": True,
        "already_merged": False,
        "merge_sha": merge_sha,
        "merge_method": method_value,
    }
