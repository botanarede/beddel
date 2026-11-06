"""AC1-AC9, AC12: the deterministic Gate records an operational outcome only.

Every command here is a fast stub (``ruff``, ``mypy`` and ``pytest`` stand-ins
on ``PATH``) or ``git``; the kit's own suite is never run.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from beddel_profile_dev import config as cfg
from beddel_profile_dev._errors import (
    PROFILE_CHANGE_INVALID,
    PROFILE_CONFIG_INVALID,
    PROFILE_GATE_COMMAND_INVALID,
    PROFILE_GATE_UNSCOPED,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev._io import records_root, resolve_revision
from beddel_profile_dev.tools.bind import profile_bind_inventory
from beddel_profile_dev.tools.change import profile_record_change
from beddel_profile_dev.tools.gate import GATE_SCHEMA, profile_run_gate
from beddel_profile_dev.tools.impact import profile_derive_impact

from ._helpers import change_fixture, git, open_attempt, stub_gate_tools

RECORDS = "changes"


def _records(repo: Path) -> Path:
    return records_root(repo, "records/profile-dev")


def _run_gate(repo: Path, rev: str, change: str = "c1") -> dict[str, Any]:
    revision_dir = _records(repo) / RECORDS / change / "revisions" / rev
    attempts = revision_dir / "attempts"
    existing = (
        sorted(
            int(p.name)
            for p in attempts.iterdir()
            if p.is_dir() and p.name.isdigit() and (p / "attempt.json").is_file()
        )
        if attempts.is_dir()
        else []
    )
    if (
        existing
        and (revision_dir / "attempts" / str(existing[-1]) / "gate.json").exists()
    ):
        attempt = open_attempt(repo, rev, change)
    elif existing:
        attempt = existing[-1]
    else:
        attempt = open_attempt(repo, rev, change)
    return profile_run_gate(str(repo), change, rev, attempt)


DEFAULT_ARGV = [
    ["ruff", "check", "."],
    ["ruff", "format", "--check", "."],
    ["mypy", "."],
    ["pytest", "-q"],
]
RESULT_KEYS = {
    "ok",
    "change_id",
    "revision",
    "gate",
    "gate_ref",
    "attempt",
    "output_attempt",
    "status",
    "commands",
    "timed_out",
}
OUTCOME_KEYS = {
    "schema",
    "change_id",
    "revision",
    "inventory_version",
    "inventory_sha256",
    "status",
    "commands",
    "gate_ref",
}
COMMAND_KEYS = {"name", "argv", "exit_code", "timed_out"}
FORBIDDEN = (
    "passed",
    "failed",
    "pendency",
    "finding",
    "verdict",
    "classification",
    "evidence",
)


def _touch_api(repo: Path) -> None:
    (repo / "src" / "api.py").write_text("x = 2\n")


def _prepare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, impact: bool = True
) -> tuple[Path, str]:
    """A ratified repo with a Change; the impact record is derived on demand."""
    repo, base, rev = change_fixture(tmp_path, _touch_api)
    monkeypatch.setenv("PATH", stub_gate_tools(tmp_path))
    if impact:
        profile_record_change(str(repo), "c1", base, rev)
        profile_bind_inventory(str(repo), rev, "v1")
        profile_derive_impact(str(repo), "c1", rev)
        open_attempt(repo, rev)
    return repo, rev


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    commands: list[list[str]] | None = None,
    *,
    per_command: int | None = None,
    total: int | None | str = "keep",
    executables: tuple[str, ...] | None = None,
) -> None:
    if commands is not None:
        monkeypatch.setattr(cfg, "GATE_COMMANDS", tuple(tuple(c) for c in commands))
    if per_command is not None:
        monkeypatch.setattr(cfg, "GATE_TIMEOUT_SECONDS", per_command)
    if total != "keep":
        monkeypatch.setattr(cfg, "GATE_TOTAL_TIMEOUT_SECONDS", total)
    if executables is not None:
        monkeypatch.setattr(cfg, "GATE_EXECUTABLES", executables)


def _revision_dir(repo: Path, rev: str, change: str = "c1") -> Path:
    return _records(repo) / RECORDS / change / "revisions" / rev


def _gate(repo: Path, rev: str) -> dict[str, Any]:
    data = json.loads((_revision_dir(repo, rev) / "gate.json").read_text())
    assert isinstance(data, dict)
    return data


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _nothing_written(repo: Path, rev: str) -> None:
    assert not (_revision_dir(repo, rev) / "gate.json").exists()
    assert not (_revision_dir(repo, rev) / "gate-output").exists()


def _refused(repo: Path, rev: str, change: str = "c1") -> ProfileError:
    lookup = "c1" if change != "c1" else change
    attempts = _revision_dir(repo, rev, lookup) / "attempts"
    existing = (
        sorted(
            int(p.name)
            for p in attempts.iterdir()
            if p.is_dir() and p.name.isdigit() and (p / "attempt.json").is_file()
        )
        if attempts.is_dir()
        else []
    )
    attempt = existing[-1] if existing else 1
    with pytest.raises(ProfileError) as info:
        profile_run_gate(str(repo), change, rev, attempt)
    return info.value


# --- AC 3, 8: what the record is -------------------------------------------


def test_default_commands_are_recorded_as_an_operational_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    result = _run_gate(repo, rev)
    impact = json.loads((_revision_dir(repo, rev) / "impact.json").read_text())

    assert set(result) == RESULT_KEYS
    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["attempt"] == 1
    assert result["output_attempt"] == 1
    assert result["commands"] == 4
    assert result["timed_out"] == 0

    gate = _gate(repo, rev)
    assert set(gate) == OUTCOME_KEYS
    assert gate["schema"] == GATE_SCHEMA == "profile-dev/gate-outcome/1"
    assert gate["change_id"] == "c1"
    assert gate["revision"] == rev
    assert gate["inventory_version"] == impact["inventory_version"]
    assert gate["inventory_sha256"] == impact["inventory_sha256"]
    assert gate["status"] == "completed"
    assert gate["gate_ref"] == f"{RECORDS}/c1/revisions/{rev}/gate-output/1"
    assert [c["name"] for c in gate["commands"]] == [
        "01-ruff",
        "02-ruff",
        "03-mypy",
        "04-pytest",
    ]
    assert [c["argv"] for c in gate["commands"]] == DEFAULT_ARGV
    bound = json.loads(
        (_revision_dir(repo, rev) / "attempts" / "1" / "gate.json").read_text()
    )
    assert set(bound) == OUTCOME_KEYS | {"attempt", "output_attempt"}
    assert bound["attempt"] == 1
    assert bound["output_attempt"] == 1
    assert bound["gate_ref"].endswith("/gate-output/1")


def test_raw_streams_are_stored_per_attempt_and_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    _run_gate(repo, rev)
    attempt = _revision_dir(repo, rev) / "gate-output" / "1"
    assert sorted(p.name for p in attempt.iterdir()) == sorted(
        f"{name}.{stream}.txt"
        for name in ("01-ruff", "02-ruff", "03-mypy", "04-pytest")
        for stream in ("stdout", "stderr")
    )
    assert (attempt / "01-ruff.stdout.txt").read_text() == "stub check .\n"
    assert (attempt / "04-pytest.stdout.txt").read_text() == "stub -q\n"
    assert (attempt / "04-pytest.stderr.txt").read_text() == ""


def test_the_record_is_canonical_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    _run_gate(repo, rev)
    raw = (_revision_dir(repo, rev) / "gate.json").read_bytes()
    expected = (
        json.dumps(json.loads(raw), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("ascii")
    assert raw == expected


def test_a_non_zero_exit_is_a_recorded_exit_code_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    monkeypatch.setenv("STUB_EXIT_PYTEST", "3")
    monkeypatch.setenv("STUB_EXIT_MYPY", "1")
    result = _run_gate(repo, rev)
    assert result["status"] == "completed"
    codes = {c["name"]: c["exit_code"] for c in _gate(repo, rev)["commands"]}
    assert codes == {"01-ruff": 0, "02-ruff": 0, "03-mypy": 1, "04-pytest": 3}


def test_the_outcome_carries_no_judgement_vocabulary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    monkeypatch.setenv("STUB_EXIT_PYTEST", "1")
    result = _run_gate(repo, rev)
    text = (
        (_revision_dir(repo, rev) / "gate.json").read_text() + json.dumps(result)
    ).lower()
    for word in FORBIDDEN:
        assert word not in text
    assert "pass" not in set(_gate(repo, rev)) | set(result)
    assert "required_evidence" not in _gate(repo, rev)


# --- AC 4: the Gate's own budget -------------------------------------------


def test_a_timed_out_command_is_recorded_and_does_not_abort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    _configure(monkeypatch, per_command=1)
    monkeypatch.setenv("STUB_SLEEP_MYPY", "30")
    result = _run_gate(repo, rev)
    assert result["status"] == "completed"
    assert result["timed_out"] == 1
    entries = {c["name"]: c for c in _gate(repo, rev)["commands"]}
    assert entries["03-mypy"]["timed_out"] is True
    assert entries["03-mypy"]["exit_code"] is None
    assert entries["04-pytest"]["timed_out"] is False  # the step went on
    assert entries["04-pytest"]["exit_code"] == 0
    out = _revision_dir(repo, rev) / "gate-output" / "1" / "03-mypy.stdout.txt"
    assert out.read_text() == "stub .\n"  # what it wrote before the budget ran out


def test_the_total_budget_records_the_remaining_commands_as_timed_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    _configure(monkeypatch, per_command=30, total=1)
    monkeypatch.setenv("STUB_SLEEP_RUFF", "30")
    result = _run_gate(repo, rev)
    assert result["status"] == "completed"
    assert result["timed_out"] == 4
    gate = _gate(repo, rev)
    assert gate["status"] == "completed"
    assert [(c["exit_code"], c["timed_out"]) for c in gate["commands"]] == [
        (None, True)
    ] * 4
    # Every command still has its (empty, for the unrun ones) output files.
    attempt = _revision_dir(repo, rev) / "gate-output" / "1"
    assert (attempt / "04-pytest.stdout.txt").read_bytes() == b""


def test_an_unset_total_budget_never_cuts_a_command_short(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    _configure(monkeypatch, total=None)
    _run_gate(repo, rev)
    assert all(c["exit_code"] == 0 for c in _gate(repo, rev)["commands"])


def test_a_command_that_cannot_start_refuses_the_whole_step_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    absent = "definitely-absent-gate-tool"
    _configure(
        monkeypatch,
        [["ruff", "check", "."], [absent, "--x"], ["pytest", "-q"]],
        executables=("git", "pytest", "ruff", "mypy", absent),
    )
    error = _refused(repo, rev)
    assert error.code == PROFILE_GATE_COMMAND_INVALID
    assert error.details == {"index": 1}
    assert absent not in f"{error} {error.message} {error.details!r}"
    _nothing_written(repo, rev)  # the first, startable command did not run either


def test_a_command_that_resolves_but_cannot_be_executed_leaves_nothing_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    broken = tmp_path / "gate-bin" / "brokentool"
    broken.write_text("#!/nonexistent/interpreter\n")  # a stale venv, say
    broken.chmod(0o755)
    _configure(
        monkeypatch,
        [["ruff", "check", "."], ["brokentool"], ["pytest", "-q"]],
        executables=("git", "pytest", "ruff", "mypy", "brokentool"),
    )
    error = _refused(repo, rev)
    assert error.code == PROFILE_GATE_COMMAND_INVALID
    assert error.details == {"index": 1}
    _nothing_written(repo, rev)  # not even the streams of the first command


def test_a_tracked_edit_hidden_by_assume_unchanged_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    git(repo, "update-index", "--assume-unchanged", "src/api.py")
    (repo / "src" / "api.py").write_text("x = 3\n")
    assert _refused(repo, rev).code == PROFILE_GATE_UNSCOPED
    _nothing_written(repo, rev)


def test_a_command_that_modifies_a_tracked_file_leaves_nothing_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    fixer = tmp_path / "gate-bin" / "fixer"
    fixer.write_text(f"#!{sys.executable}\nopen('src/api.py', 'w').write('x = 9\\n')\n")
    fixer.chmod(0o755)
    _configure(
        monkeypatch,
        [["ruff", "check", "."], ["fixer"]],
        executables=("git", "pytest", "ruff", "mypy", "fixer"),
    )
    assert _refused(repo, rev).code == PROFILE_GATE_UNSCOPED
    _nothing_written(repo, rev)


def test_a_gate_output_that_is_a_file_is_refused_before_any_command_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    (_revision_dir(repo, rev) / "gate-output").write_text("not a directory")
    assert _refused(repo, rev).code == PROFILE_REPOSITORY_INVALID


def test_a_relative_path_entry_never_resolves_an_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    (repo / "ruff").write_text("#!/bin/sh\nexit 0\n")
    (repo / "ruff").chmod(0o755)
    monkeypatch.setenv("PATH", f".{os.pathsep}{os.environ['PATH']}")
    monkeypatch.chdir(repo)
    _configure(monkeypatch, [["ruff", "check", "."]], executables=("git", "ruff"))
    (tmp_path / "gate-bin" / "ruff").unlink()  # only the in-repo, relative one is left
    error = _refused(repo, rev)
    assert error.code == PROFILE_GATE_COMMAND_INVALID
    _nothing_written(repo, rev)


# --- AC 6: the commands run over the Analyzed revision -----------------------


def test_a_work_tree_that_is_not_the_analyzed_revision_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    git(repo, "checkout", "--detach", "HEAD~1")
    error = _refused(repo, rev)
    assert error.code == PROFILE_GATE_UNSCOPED
    _nothing_written(repo, rev)


def test_a_modified_tracked_file_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    (repo / "src" / "api.py").write_text("x = 3\n")  # not committed
    error = _refused(repo, rev)
    assert error.code == PROFILE_GATE_UNSCOPED
    _nothing_written(repo, rev)


def test_a_staged_change_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    (repo / "src" / "api.py").write_text("x = 3\n")
    git(repo, "add", "src/api.py")
    assert _refused(repo, rev).code == PROFILE_GATE_UNSCOPED
    _nothing_written(repo, rev)


def test_an_untracked_file_does_not_block_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    (repo / "scratch.txt").write_text("untracked\n")
    _run_gate(repo, rev)
    _run_gate(repo, rev)  # the kit's own records are untracked too
    assert _gate(repo, rev)["gate_ref"].endswith("/gate-output/2")


def test_a_gate_json_that_is_a_directory_is_refused_before_any_command_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    (_revision_dir(repo, rev) / "gate.json").mkdir()
    assert _refused(repo, rev).code == PROFILE_REPOSITORY_INVALID
    assert not (_revision_dir(repo, rev) / "gate-output").exists()


# --- AC 1: scope comes from impact.json only --------------------------------


def test_scope_changes_after_attempt_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    path = _revision_dir(repo, rev) / "impact.json"
    impact = json.loads(path.read_text())
    impact["inventory_version"] = "v9"
    impact["inventory_sha256"] = "ab" * 32
    impact["footprint"] = ["not/derived/here.py"]
    path.write_text(json.dumps(impact))
    assert _refused(repo, rev).code == PROFILE_GATE_UNSCOPED
    _nothing_written(repo, rev)


def test_the_gate_reads_the_impact_record_and_never_rewrites_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    before = _tree(_records(repo) / RECORDS)
    _run_gate(repo, rev)
    _run_gate(repo, rev)
    after = _tree(_records(repo) / RECORDS)
    gate_prefix = f"c1/revisions/{rev}/gate"
    for name, data in before.items():
        assert after[name] == data, name  # every earlier record is byte-identical
    assert {n for n in after if n not in before}.issuperset({f"{gate_prefix}.json"})
    assert all(
        n.startswith((gate_prefix, f"c1/revisions/{rev}/attempts/"))
        for n in after
        if n not in before
    )


def test_no_impact_record_stops_with_unscoped_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch, impact=False)
    assert _refused(repo, rev).code == PROFILE_GATE_UNSCOPED
    assert not (_records(repo) / RECORDS).exists()


def test_an_impact_record_of_another_change_is_not_a_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    assert _refused(repo, rev, change="c2").code == PROFILE_GATE_UNSCOPED
    assert not (_records(repo) / RECORDS / "c2").exists()
    _nothing_written(repo, rev)


def test_an_impact_record_of_another_revision_is_not_a_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    other = resolve_revision(repo, f"{rev}~1")
    assert _refused(repo, other).code == PROFILE_GATE_UNSCOPED
    _nothing_written(repo, rev)


_IDENTITY_BREAKS: dict[str, Callable[[dict[str, Any]], object]] = {
    "wrong_change": lambda d: d.update(change_id="other"),
    "wrong_revision": lambda d: d.update(revision="0" * 40),
    "wrong_schema": lambda d: d.update(schema="profile-dev/impact/2"),
    "extra_key": lambda d: d.update(verdict="x"),
    "missing_key": lambda d: d.pop("footprint"),
    "bad_digest": lambda d: d.update(inventory_sha256="abc"),
    "bad_version": lambda d: d.update(inventory_version="Bad Version"),
    "non_string_version": lambda d: d.update(inventory_version=1),
    "bad_base": lambda d: d.update(base="main"),
}


@pytest.mark.parametrize("name", sorted(_IDENTITY_BREAKS))
def test_an_inconsistent_impact_record_is_unscoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    path = _revision_dir(repo, rev) / "impact.json"
    impact = json.loads(path.read_text())
    _IDENTITY_BREAKS[name](impact)
    path.write_text(json.dumps(impact))
    assert _refused(repo, rev).code == PROFILE_GATE_UNSCOPED
    _nothing_written(repo, rev)


@pytest.mark.parametrize("content", ["", "{", "[]", "null", '"text"', "123"])
def test_an_unreadable_impact_record_is_unscoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    (_revision_dir(repo, rev) / "impact.json").write_text(content)
    assert _refused(repo, rev).code == PROFILE_GATE_UNSCOPED
    _nothing_written(repo, rev)


# --- AC 2: commands come from config, fail closed ---------------------------


def test_a_command_outside_the_allowlist_refuses_the_whole_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    _configure(
        monkeypatch,
        [["ruff", "check", "."], ["curl", "--token", "S3CR3T-VALUE"]],
    )
    error = _refused(repo, rev)
    assert error.code == PROFILE_GATE_COMMAND_INVALID
    assert error.details == {"index": 1}
    leaked = f"{error} {error.message} {error.details!r}"
    assert "S3CR3T-VALUE" not in leaked
    assert "curl" not in leaked
    _nothing_written(repo, rev)  # not even the allowed first command ran


@pytest.mark.parametrize(
    "executable", ["/usr/bin/ruff", "..\\ruff", "./ruff", "bin/ruff"]
)
def test_a_path_form_executable_is_outside_the_allowlist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executable: str
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", ((executable, "check"),))
    error = _refused(repo, rev)
    assert error.code == PROFILE_GATE_COMMAND_INVALID
    assert error.details == {"index": 0}
    _nothing_written(repo, rev)


@pytest.mark.parametrize(
    "commands",
    [[], [[]], [[""]], [["ruff", 1]], "ruff check"],
)
def test_a_malformed_command_list_refuses_the_whole_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, commands: Any
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", commands)
    assert _refused(repo, rev).code == PROFILE_CONFIG_INVALID
    _nothing_written(repo, rev)


def test_commands_run_in_the_repository_root_with_git_env_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    _configure(monkeypatch, [["git", "rev-parse", "--show-toplevel"]])
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "elsewhere"))
    _run_gate(repo, rev)
    out = _revision_dir(repo, rev) / "gate-output" / "1" / "01-git.stdout.txt"
    assert Path(out.read_text().strip()) == repo.resolve()
    assert _gate(repo, rev)["commands"][0]["exit_code"] == 0


def test_scope_and_command_list_are_identical_across_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    _run_gate(repo, rev)
    first = _gate(repo, rev)
    monkeypatch.setenv("STUB_EXIT_PYTEST", "2")  # exit codes may differ
    _run_gate(repo, rev)
    second = _gate(repo, rev)
    for key in ("schema", "change_id", "revision", "inventory_version"):
        assert first[key] == second[key]
    assert first["inventory_sha256"] == second["inventory_sha256"]
    assert [(c["name"], c["argv"]) for c in first["commands"]] == [
        (c["name"], c["argv"]) for c in second["commands"]
    ]


# --- AC 5, 8: results are retained, attempts are append-only ------------------


def test_attempts_are_append_only_and_gate_json_names_the_latest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    output = _revision_dir(repo, rev) / "gate-output"

    first = _run_gate(repo, rev)
    attempt_one = _tree(output / "1")
    assert first["output_attempt"] == 1

    monkeypatch.setenv("STUB_EXIT_PYTEST", "3")
    second = _run_gate(repo, rev)
    assert second["output_attempt"] == 2
    assert _tree(output / "1") == attempt_one  # a prior attempt is never rewritten
    gate = _gate(repo, rev)
    assert gate["gate_ref"].endswith("/gate-output/2")
    assert gate["commands"][3]["exit_code"] == 3

    monkeypatch.setenv("STUB_EXIT_PYTEST", "4")
    third = _run_gate(repo, rev)
    assert third["output_attempt"] == 3
    assert sorted(p.name for p in output.iterdir()) == ["1", "2", "3"]
    assert _tree(output / "1") == attempt_one
    assert (output / "2" / "04-pytest.stdout.txt").read_text() == "stub -q\n"
    gate = _gate(repo, rev)
    assert gate["gate_ref"].endswith("/gate-output/3")
    assert gate["commands"][3]["exit_code"] == 4


def test_attempt_numbering_continues_past_existing_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    output = _revision_dir(repo, rev) / "gate-output"
    (output / "7").mkdir(parents=True)
    (output / "notes").mkdir()
    (output / "0").mkdir()
    result = _run_gate(repo, rev)
    assert result["output_attempt"] == 8

    assert list((output / "7").iterdir()) == []


def test_a_refused_rerun_leaves_the_previous_outcome_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    _run_gate(repo, rev)
    before = _tree(_records(repo) / RECORDS)
    monkeypatch.setattr(cfg, "GATE_COMMANDS", (("curl", "x"),))
    assert _refused(repo, rev).code == PROFILE_GATE_COMMAND_INVALID
    assert _tree(_records(repo) / RECORDS) == before


# --- AC 9: confinement and inputs ---------------------------------------------


def test_a_bound_gate_symlink_that_escapes_the_records_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    outside = tmp_path / "outside-gate.json"
    outside.write_text("untouched")
    (_revision_dir(repo, rev) / "attempts" / "1" / "gate.json").symlink_to(outside)
    error = _refused(repo, rev)
    assert error.code == PROFILE_REPOSITORY_INVALID
    assert outside.read_text() == "untouched"


def test_a_gate_output_symlink_that_escapes_the_repository_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (_revision_dir(repo, rev) / "gate-output").symlink_to(outside)
    assert _refused(repo, rev).code == PROFILE_REPOSITORY_INVALID
    assert list(outside.iterdir()) == []
    assert not (_revision_dir(repo, rev) / "gate.json").exists()


def test_a_gate_json_symlink_that_escapes_the_repository_is_not_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    outside = tmp_path / "outside.json"
    outside.write_text("untouched")
    (_revision_dir(repo, rev) / "gate.json").symlink_to(outside)
    assert _refused(repo, rev).code == PROFILE_REPOSITORY_INVALID
    assert outside.read_text() == "untouched"


@pytest.mark.parametrize("change_id", ["", "../c1", "C1", "a b", "x" * 80])
def test_an_invalid_change_id_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change_id: str
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    assert _refused(repo, rev, change=change_id).code == PROFILE_CHANGE_INVALID
    _nothing_written(repo, rev)


def test_a_path_that_is_not_the_repository_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _prepare(tmp_path, monkeypatch)
    with pytest.raises(ProfileError) as info:
        profile_run_gate(str(repo / "src"), "c1", rev, 1)
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    with pytest.raises(ProfileError) as info:
        profile_run_gate(str(repo), "c1", "no-such-revision", 1)
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    _nothing_written(repo, rev)
