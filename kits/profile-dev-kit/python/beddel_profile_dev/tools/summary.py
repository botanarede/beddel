"""Read-only delivery cost summary assembled from persisted profile records."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import PROFILE_REPOSITORY_INVALID, ProfileError
from beddel_profile_dev._io import confined, read_confined, real_repo_root, records_root
from beddel_profile_dev.config import load_config
from beddel_profile_dev.deliver import STAGES
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.tools.deliver import _records
from beddel_profile_dev.tools.implement import _valid_story
from beddel_profile_dev.tools.ratify import TIMESTAMP_FORMAT
from beddel_profile_dev.tools.report import _validate_report_content

__all__ = ["profile_read_delivery_summary"]

_SUMMARY_STAGES = (*STAGES, "deliver")
_AGENT_STAGES = {"plan", "implement", "verify-and-fix"}
_GATE_SCHEMA = "profile-dev/attempt-gate-outcome/1"
_REPORT_ORDINAL = re.compile(r"([1-9][0-9]*)\.json")
_MISSING = "missing"
_NOT_OBSERVABLE = "not observable"


def _invalid() -> ProfileError:
    return ProfileError(PROFILE_REPOSITORY_INVALID, "repository or revision invalid")


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise _invalid()
    try:
        return datetime.strptime(value, TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        raise _invalid() from None


def _report_records(root: Path, change_id: str) -> list[tuple[int, dict[str, Any]]]:
    relative = f"changes/{change_id}/report"
    directory = confined(root, relative)
    if not directory.exists():
        return []
    if not directory.is_dir():
        raise _invalid()
    found: list[tuple[int, dict[str, Any]]] = []
    for entry in directory.iterdir():
        match = _REPORT_ORDINAL.fullmatch(entry.name)
        if match is None:
            continue
        ordinal = int(match.group(1))
        raw = read_confined(root, f"{relative}/{entry.name}")
        try:
            content = json.loads(raw) if raw is not None else None
        except (TypeError, ValueError, RecursionError):
            content = None
        found.append((ordinal, _validate_report_content(content, ordinal, change_id)))
    return sorted(found)


def _gate_codes(
    root: Path, change_id: str, report: Mapping[str, Any]
) -> dict[str, Any] | None:
    revision, attempt = report.get("revision"), report.get("attempt")
    if not isinstance(revision, str) or type(attempt) is not int or attempt < 1:
        return None
    relative = f"changes/{change_id}/revisions/{revision}/attempts/{attempt}/gate.json"
    raw = read_confined(root, relative)
    try:
        data = json.loads(raw) if raw is not None else None
    except (TypeError, ValueError, RecursionError):
        data = None
    expected = {
        "schema",
        "attempt",
        "output_attempt",
        "change_id",
        "revision",
        "inventory_version",
        "inventory_sha256",
        "status",
        "commands",
        "gate_ref",
    }
    if not isinstance(data, dict) or set(data) != expected:
        return None
    if (
        data.get("schema") != _GATE_SCHEMA
        or data.get("attempt") != attempt
        or data.get("change_id") != change_id
        or data.get("revision") != revision
        or data.get("status") != "completed"
    ):
        return None
    commands = data.get("commands")
    if not isinstance(commands, list) or not commands:
        return None
    values: dict[str, Any] = {}
    for command in commands:
        if (
            not isinstance(command, dict)
            or set(command) != {"name", "argv", "exit_code", "timed_out"}
            or not isinstance(command.get("name"), str)
            or not isinstance(command.get("argv"), list)
            or not all(isinstance(arg, str) for arg in command["argv"])
            or type(command.get("timed_out")) is not bool
        ):
            return None
        exit_code = command["exit_code"]
        if command["timed_out"]:
            values[command["name"]] = "timeout"
        elif type(exit_code) is int:
            values[command["name"]] = exit_code
        else:
            return None
    return values


def _wall_seconds(
    record: Mapping[str, Any], runs: list[tuple[int, int, list[Mapping[str, Any]]]]
) -> int | str:
    ordinal = record.get("record")
    if type(ordinal) is not int:
        return _MISSING
    for first, last, run_records in runs:
        if first <= ordinal <= last:
            position = next(
                (
                    index
                    for index, item in enumerate(run_records)
                    if item.get("record") == ordinal
                ),
                None,
            )
            if position is None or position == 0:
                return _MISSING
            previous = _timestamp(run_records[position - 1].get("recorded_at"))
            current = _timestamp(record.get("recorded_at"))
            seconds = (current - previous).total_seconds()
            return int(seconds) if seconds >= 0 and seconds.is_integer() else _MISSING
    return _MISSING


def _agent_counts(
    stage: str, records: list[Mapping[str, Any]]
) -> tuple[int | str, int | str]:
    if stage not in _AGENT_STAGES:
        return 0, 0
    totals = [0, 0]
    for record in records:
        refs = record.get("refs")
        reason = record.get("reason")
        if not isinstance(refs, Mapping):
            return _MISSING, _MISSING
        for index, key in enumerate(("hook_stop", "hook_denied")):
            if key not in refs:
                return _MISSING, _MISSING
            value = refs[key]
            if value is None:
                if reason == "hooks.missing":
                    return _MISSING, _MISSING
                continue
            if type(value) is not int or value < 0:
                return _MISSING, _MISSING
            totals[index] += value
    return totals[0], totals[1]


def _review_data(
    root: Path, records: list[Mapping[str, Any]]
) -> tuple[int | str, list[dict[str, Any]] | str]:
    change_ids: set[str] = set()
    for record in records:
        refs = record.get("refs")
        value = refs.get("change_id") if isinstance(refs, Mapping) else None
        if not isinstance(value, str) or not is_valid_id(value):
            return _MISSING, _MISSING
        change_ids.add(value)
    if not change_ids:
        return 0, []
    report_values: list[tuple[str, int, dict[str, Any]]] = []
    for change_id in sorted(change_ids):
        found = _report_records(root, change_id)
        if not found:
            return _MISSING, _MISSING
        report_values.extend((change_id, ordinal, report) for ordinal, report in found)
    reports: list[dict[str, Any]] = []
    for change_id, ordinal, report in report_values:
        codes = _gate_codes(root, change_id, report)
        if codes is None:
            return len(report_values), _MISSING
        reports.append({"report": ordinal, "commands": codes})
    reports.sort(key=lambda item: item["report"])
    return len(reports), reports


def _row(
    stage: str,
    records: list[Mapping[str, Any]],
    root: Path,
    runs: list[tuple[int, int, list[Mapping[str, Any]]]],
) -> dict[str, Any]:
    if not records:
        values: dict[str, Any] = {
            "wall_seconds": _MISSING,
            "agent_calls": _MISSING,
            "denied_calls": _MISSING,
            "review_rounds": _MISSING,
            "gate_exit_codes": _MISSING,
        }
    else:
        walls = [_wall_seconds(record, runs) for record in records]
        wall = (
            sum(value for value in walls if isinstance(value, int))
            if all(isinstance(value, int) for value in walls)
            else _MISSING
        )
        calls, denied = _agent_counts(stage, records)
        review_rounds, gates = (
            _review_data(root, records) if stage == "verify-and-fix" else (0, [])
        )
        values = {
            "wall_seconds": wall,
            "agent_calls": calls,
            "denied_calls": denied,
            "review_rounds": review_rounds,
            "gate_exit_codes": gates,
        }
    return {
        "stage": stage,
        "records": [record["record"] for record in records],
        **values,
        "kiro_credits": _NOT_OBSERVABLE,
        "tokens": _NOT_OBSERVABLE,
    }


def _total(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    fields = ("wall_seconds", "agent_calls", "denied_calls", "review_rounds")
    result: dict[str, Any] = {}
    for field in fields:
        values = [row[field] for row in rows]
        result[field] = (
            sum(values) if all(type(value) is int for value in values) else _MISSING
        )
    gates = [row["gate_exit_codes"] for row in rows]
    result["gate_exit_codes"] = (
        [item for value in gates if isinstance(value, list) for item in value]
        if all(isinstance(value, list) for value in gates)
        else _MISSING
    )
    result["kiro_credits"] = _NOT_OBSERVABLE
    result["tokens"] = _NOT_OBSERVABLE
    return result


@beddel_tool(
    name="profile_read_delivery_summary",
    description="Read a delivery cost summary from existing profile records",
    category="profile",
)
def profile_read_delivery_summary(repo_path: str, story_key: str) -> dict[str, Any]:
    """Read delivery records without creating or modifying any record."""
    if not _valid_story(story_key):
        raise ProfileError(PROFILE_REPOSITORY_INVALID, "story key invalid")
    repo = real_repo_root(repo_path)
    root = records_root(repo, load_config().records_dir)
    records = [
        record
        for record in _records(root)
        if record.get("story_key") == story_key
        and record.get("stage") in _SUMMARY_STAGES
    ]
    records.sort(key=lambda record: record["record"])
    runs: list[tuple[int, int, list[Mapping[str, Any]]]] = []
    for deliver in (record for record in records if record.get("stage") == "deliver"):
        refs = deliver.get("refs")
        first = refs.get("first_record") if isinstance(refs, Mapping) else None
        last = deliver.get("record")
        if type(first) is int and type(last) is int and first <= last:
            runs.append(
                (
                    first,
                    last,
                    [record for record in records if first <= record["record"] <= last],
                )
            )
    rows = [
        _row(
            stage,
            [record for record in records if record.get("stage") == stage],
            root,
            runs,
        )
        for stage in _SUMMARY_STAGES
    ]
    missing = [
        f"{row['stage']}.{field}"
        for row in rows
        for field in (
            "wall_seconds",
            "agent_calls",
            "denied_calls",
            "review_rounds",
            "gate_exit_codes",
        )
        if row[field] == _MISSING
    ]
    return {
        "story_key": story_key,
        "stages": rows,
        "total": _total(rows),
        "missing": missing,
    }
