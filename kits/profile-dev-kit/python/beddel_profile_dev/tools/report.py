"""Persistence and retrieval of Story 4.1 Verification Reports."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import (
    PROFILE_CHANGE_INVALID,
    PROFILE_IMPACT_UNBOUND,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev._io import (
    canonical_json,
    confined,
    is_ancestor,
    read_confined,
    real_repo_root,
    records_root,
    resolve_revision,
    write_create_only,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.inventory import is_valid_id
from beddel_profile_dev.report import REPORT_SCHEMA, build_items
from beddel_profile_dev.tools.bind import BINDING_SCHEMA, SNAPSHOT_SCHEMA
from beddel_profile_dev.tools.change import CHANGE_REVISION_SCHEMA, CHANGE_SCHEMA
from beddel_profile_dev.tools.evidence import EVIDENCE_SCHEMA
from beddel_profile_dev.tools.evidence import _attempt as validate_attempt
from beddel_profile_dev.tools.impact import IMPACT_SCHEMA, _bound_snapshot
from beddel_profile_dev.tools.review import _read_scope

__all__ = ["REPORT_SCHEMA", "profile_read_report", "profile_record_report"]

_FULL_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_ORDINAL = re.compile(r"([1-9][0-9]*)")
_REPORT_ORDINAL = re.compile(r"([1-9][0-9]*)\.json")


class _Reader:
    """Read records while retaining the references and digests used by a report."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.reads: dict[str, str] = {}

    def read(self, relative: str) -> bytes | None:
        raw = read_confined(self.root, relative)
        if raw is not None:
            self.reads[relative] = hashlib.sha256(raw).hexdigest()
        return raw

    def json(self, relative: str) -> dict[str, Any] | None:
        raw = self.read(relative)
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def result(self) -> list[dict[str, str]]:
        return [{"ref": ref, "sha256": self.reads[ref]} for ref in sorted(self.reads)]


def _unbound() -> ProfileError:
    return ProfileError(
        PROFILE_IMPACT_UNBOUND,
        "report needs a recorded Change, binding and impact at the analyzed revision",
    )


def _invalid_repo() -> ProfileError:
    return ProfileError(PROFILE_REPOSITORY_INVALID, "repository or revision invalid")


def _valid_change(data: Mapping[str, Any] | None, change_id: str) -> bool:
    if data is None:
        return False
    base = data.get("base")
    return (
        set(data) == {"schema", "change_id", "base"}
        and data.get("schema") == CHANGE_SCHEMA
        and data.get("change_id") == change_id
        and isinstance(base, str)
        and _FULL_SHA.fullmatch(base) is not None
    )


def _load_change(
    reader: _Reader, repo: Path, change_id: str, sha: str
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    change = reader.json(f"changes/{change_id}/change.json")
    link = reader.json(f"changes/{change_id}/revisions/{sha}/revision.json")
    base = change.get("base") if change is not None else None
    if (
        not _valid_change(change, change_id)
        or link is None
        or set(link) != {"schema", "change_id", "base", "revision"}
        or link.get("schema") != CHANGE_REVISION_SCHEMA
        or link.get("change_id") != change_id
        or link.get("base") != base
        or link.get("revision") != sha
    ):
        raise _unbound()
    assert change is not None
    try:
        if resolve_revision(repo, base) != base or not is_ancestor(repo, base, sha):
            raise _unbound()
    except ProfileError:
        raise _unbound() from None
    return base, change, link


def _load_scope(
    reader: _Reader, repo: Path, change_id: str, sha: str
) -> tuple[str, dict[str, Any], dict[str, Any], bytes, dict[str, Any], bytes]:
    base, _, _ = _load_change(reader, repo, change_id, sha)
    binding_rel = f"revisions/{sha}/binding.json"
    snapshot_rel = f"revisions/{sha}/snapshot.json"
    impact_rel = f"changes/{change_id}/revisions/{sha}/impact.json"
    binding = reader.json(binding_rel)
    snapshot_raw = reader.read(snapshot_rel)
    impact_raw = reader.read(impact_rel)
    try:
        snapshot = json.loads(snapshot_raw) if snapshot_raw is not None else None
    except (TypeError, ValueError):
        snapshot = None
    try:
        impact = json.loads(impact_raw) if impact_raw is not None else None
    except (TypeError, ValueError):
        impact = None
    try:
        _bound_snapshot(reader.root, sha, snapshot_raw=snapshot_raw)
    except ProfileError as error:
        if error.code == PROFILE_REPOSITORY_INVALID:
            raise
        raise _unbound() from None
    if (
        binding is None
        or snapshot is None
        or impact is None
        or not isinstance(impact, dict)
        or set(binding)
        != {
            "schema",
            "revision",
            "inventory_version",
            "inventory_sha256",
            "snapshot",
        }
        or binding.get("schema") != BINDING_SCHEMA
        or binding.get("revision") != sha
        or binding.get("snapshot") != snapshot_rel
        or not isinstance(snapshot, dict)
        or snapshot.get("schema") != SNAPSHOT_SCHEMA
        or snapshot.get("revision") != sha
        or snapshot.get("inventory_version") != binding.get("inventory_version")
        or snapshot.get("inventory_sha256") != binding.get("inventory_sha256")
        or not isinstance(snapshot.get("criteria"), list)
        or not all(
            isinstance(item, dict)
            and set(item) == {"id", "description"}
            and isinstance(item["id"], str)
            and isinstance(item["description"], str)
            for item in snapshot["criteria"]
        )
        or impact_raw is None
        or impact.get("schema") != IMPACT_SCHEMA
    ):
        raise _unbound()
    try:
        scope = _read_scope(reader.root, impact_rel, change_id, sha, raw=impact_raw)
    except ProfileError as error:
        if error.code == PROFILE_REPOSITORY_INVALID:
            raise
        raise _unbound() from None
    if (
        impact.get("base") != base
        or impact.get("inventory_version") != binding.get("inventory_version")
        or impact.get("inventory_sha256") != binding.get("inventory_sha256")
    ):
        raise _unbound()
    return base, snapshot, impact, impact_raw, scope, snapshot_raw or b""


def _latest_attempt(records: Path, revision_rel: str) -> int | None:
    directory = confined(records, f"{revision_rel}/attempts")
    if not directory.exists():
        return None
    if not directory.is_dir():
        raise _invalid_repo()
    values = [
        int(match.group(1))
        for entry in directory.iterdir()
        if entry.is_dir() and (match := _ORDINAL.fullmatch(entry.name)) is not None
    ]
    return max(values) if values else None


def _valid_outcome(
    reader: _Reader,
    relative: str,
    requirement: Mapping[str, Any],
    attempt: int,
    change_id: str,
    revision: str,
    inventory_version: str,
    inventory_sha256: str,
) -> tuple[dict[str, Any], bytes] | None:
    raw = reader.read(relative)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    kind = requirement.get("kind")
    if kind == "gate":
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
        if (
            set(data) != expected
            or data.get("schema") != "profile-dev/attempt-gate-outcome/1"
        ):
            return None
    else:
        expected = {
            "schema",
            "attempt",
            "output_attempt",
            "change_id",
            "revision",
            "inventory_version",
            "inventory_sha256",
            "agent",
            "model",
            "status",
            "review_ref",
        }
        if (
            set(data) not in (expected, expected | {"error_code"})
            or data.get("schema") != "profile-dev/attempt-review-outcome/1"
        ):
            return None
    if (
        type(data.get("attempt")) is not int
        or data.get("attempt") != attempt
        or data.get("change_id") != change_id
        or data.get("revision") != revision
        or data.get("inventory_version") != inventory_version
        or data.get("inventory_sha256") != inventory_sha256
        or data.get("status") != "completed"
    ):
        return None
    if kind == "gate":
        commands = data.get("commands")
        gate_ref = data.get("gate_ref")
        expected_gate_ref = (
            relative.rsplit(f"/attempts/{attempt}/", 1)[0]
            + f"/gate-output/{data.get('output_attempt')}"
        )
        if (
            not isinstance(commands, list)
            or not commands
            or not isinstance(gate_ref, str)
            or not isinstance(data.get("output_attempt"), int)
            or isinstance(data.get("output_attempt"), bool)
            or data.get("output_attempt", 0) < 1
            or gate_ref != expected_gate_ref
        ):
            return None
        for command in commands:
            if (
                not isinstance(command, dict)
                or set(command) != {"name", "argv", "exit_code", "timed_out"}
                or not isinstance(command["name"], str)
                or not isinstance(command["argv"], list)
                or not all(isinstance(arg, str) for arg in command["argv"])
                or not isinstance(command["timed_out"], bool)
                or (
                    command["exit_code"] is not None
                    and (
                        isinstance(command["exit_code"], bool)
                        or not isinstance(command["exit_code"], int)
                    )
                )
            ):
                return None
        return data, raw
    review_ref = data.get("review_ref")
    prefix = relative.rsplit(f"/attempts/{attempt}/", 1)[0] + "/review-output/"
    if (
        not isinstance(data.get("output_attempt"), int)
        or isinstance(data.get("output_attempt"), bool)
        or data.get("output_attempt", 0) < 1
        or not isinstance(data.get("agent"), str)
        or not isinstance(data.get("model"), str)
        or not isinstance(review_ref, str)
        or not review_ref.startswith(prefix)
        or not re.fullmatch(re.escape(prefix) + r"[1-9][0-9]*\.txt", review_ref)
        or not review_ref.endswith(f"/{data.get('output_attempt')}.txt")
    ):
        return None
    output = reader.read(review_ref)
    if output is None or not output.decode("utf-8", "replace").strip():
        return None
    return data, raw


def _validated_evidence(
    reader: _Reader,
    revision_rel: str,
    requirement: Mapping[str, Any],
    attempt: int,
    change_id: str,
    revision: str,
    inventory_version: str,
    inventory_sha256: str,
) -> dict[str, Any] | None:
    filename = (
        f"{requirement['class']}+{requirement['affected_point']}+"
        f"{requirement['criterion']}.json"
    )
    relative = f"{revision_rel}/attempts/{attempt}/evidence/{filename}"
    raw = reader.read(relative)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    expected = {
        "schema",
        "attempt",
        "change_id",
        "revision",
        "class",
        "affected_point",
        "criterion",
        "kind",
        "outcome_ref",
        "outcome_sha256",
        "result",
    }
    outcome_ref = f"{revision_rel}/attempts/{attempt}/{requirement['kind']}.json"
    if (
        not isinstance(data, dict)
        or set(data) != expected
        or data.get("schema") != EVIDENCE_SCHEMA
        or type(data.get("attempt")) is not int
        or data.get("attempt") != attempt
        or data.get("change_id") != change_id
        or data.get("revision") != revision
        or data.get("class") != requirement.get("class")
        or data.get("affected_point") != requirement.get("affected_point")
        or data.get("criterion") != requirement.get("criterion")
        or data.get("kind") != requirement.get("kind")
        or data.get("outcome_ref") != outcome_ref
        or not isinstance(data.get("outcome_sha256"), str)
        or not _DIGEST.fullmatch(data["outcome_sha256"])
    ):
        return None
    outcome = _valid_outcome(
        reader,
        outcome_ref,
        requirement,
        attempt,
        change_id,
        revision,
        inventory_version,
        inventory_sha256,
    )
    if outcome is None:
        return None
    outcome_data, outcome_raw = outcome
    if data["outcome_sha256"] != hashlib.sha256(outcome_raw).hexdigest():
        return None
    if requirement["kind"] == "gate":
        expected_result = {
            "commands": outcome_data["commands"],
            "gate_ref": outcome_data["gate_ref"],
        }
    else:
        output = reader.read(outcome_data["review_ref"])
        if output is None:
            return None
        expected_result = {
            "agent": outcome_data["agent"],
            "model": outcome_data["model"],
            "review_ref": outcome_data["review_ref"],
            "review_sha256": hashlib.sha256(output).hexdigest(),
        }
    if data.get("result") != expected_result:
        return None
    return {"ref": relative, "sha256": hashlib.sha256(raw).hexdigest(), "record": data}


def _validated_determinations(
    reader: _Reader,
    revision: str,
    requirements: Sequence[Mapping[str, Any]],
    inventory_version: str,
    inventory_sha256: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for requirement in requirements:
        relative = (
            f"revisions/{revision}/non-applicability/"
            f"{requirement['class']}+{requirement['affected_point']}+"
            f"{requirement['criterion']}.json"
        )
        raw = reader.read(relative)
        if raw is None:
            continue
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if (
            not isinstance(data, dict)
            or data.get("schema") != "profile-dev/non-applicability/1"
            or data.get("revision") != revision
            or data.get("inventory_version") != inventory_version
            or data.get("inventory_sha256") != inventory_sha256
            or any(
                data.get(key) != requirement.get(key)
                for key in ("class", "affected_point", "criterion")
            )
        ):
            continue
        result.append(
            {
                **{
                    key: requirement[key]
                    for key in ("class", "affected_point", "criterion")
                },
                "ref": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return result


def _next_report(records: Path, report_rel: str) -> int:
    directory = confined(records, report_rel)
    if not directory.exists():
        return 1
    if not directory.is_dir():
        raise _invalid_repo()
    values = [
        int(match.group(1))
        for entry in directory.iterdir()
        if (match := _REPORT_ORDINAL.fullmatch(entry.name)) is not None
    ]
    return max(values, default=0) + 1


@beddel_tool(
    name="profile_record_report",
    description="Build and persist one append-only Verification Report for a Change",
    category="profile",
)
def profile_record_report(
    repo_path: str, change_id: str, revision: str
) -> dict[str, Any]:
    """Build and append a Report for the designated attempt of a revision."""
    config = load_config()
    if not is_valid_id(change_id):
        raise ProfileError(PROFILE_CHANGE_INVALID, "change id invalid")
    repo = real_repo_root(repo_path)
    sha = resolve_revision(repo, revision)
    records = records_root(repo, config.records_dir)
    reader = _Reader(records)
    revision_rel = f"changes/{change_id}/revisions/{sha}"
    base, snapshot, impact, impact_raw, _, _ = _load_scope(reader, repo, change_id, sha)
    attempt = _latest_attempt(records, revision_rel)
    attempt_state = "none"
    attempt_record: dict[str, Any] | None = None
    if attempt is not None:
        reader.read(f"{revision_rel}/attempts/{attempt}/attempt.json")
        try:
            attempt_record = validate_attempt(
                records, revision_rel, attempt, change_id, sha, impact_raw
            )
            attempt_state = "valid"
        except ProfileError as error:
            if error.code == PROFILE_REPOSITORY_INVALID:
                raise
            attempt_state = "indeterminate"
    requirements = [
        item for item in impact.get("required_evidence", []) if isinstance(item, dict)
    ]
    validated: list[dict[str, Any]] = []
    if attempt_record is not None and attempt is not None:
        for requirement in attempt_record["requirements"]:
            evidence = _validated_evidence(
                reader,
                revision_rel,
                requirement,
                attempt,
                change_id,
                sha,
                attempt_record["inventory_version"],
                attempt_record["inventory_sha256"],
            )
            if evidence is not None:
                validated.append({**requirement, **evidence})
    determinations = _validated_determinations(
        reader,
        sha,
        requirements,
        str(snapshot["inventory_version"]),
        str(snapshot["inventory_sha256"]),
    )
    items = build_items(impact, snapshot, attempt_state, validated, determinations)
    report_without_ordinal = {
        "schema": REPORT_SCHEMA,
        "record": 0,
        "change_id": change_id,
        "base": base,
        "revision": sha,
        "attempt": attempt,
        "attempt_state": attempt_state,
        "reads": reader.result(),
        "items": items,
    }
    report_rel = f"changes/{change_id}/report"
    ordinal = _next_report(records, report_rel)
    for _ in range(100):
        report = {**report_without_ordinal, "record": ordinal}
        data = canonical_json(report)
        if write_create_only(records, f"{report_rel}/{ordinal}.json", data):
            return {
                "ok": True,
                "change_id": change_id,
                "revision": sha,
                "record": ordinal,
                "report": f"{report_rel}/{ordinal}.json",
                "attempt": attempt,
                "attempt_state": attempt_state,
            }
        ordinal += 1
    raise _invalid_repo()


@beddel_tool(
    name="profile_read_report",
    description="Read the latest persisted Verification Report and its append-only history",
    category="profile",
)
def profile_read_report(repo_path: str, change_id: str) -> dict[str, Any]:
    """Read Reports without running verification or writing records."""
    config = load_config()
    if not is_valid_id(change_id):
        raise ProfileError(PROFILE_CHANGE_INVALID, "change id invalid")
    repo = real_repo_root(repo_path)
    records = records_root(repo, config.records_dir)
    reader = _Reader(records)
    change = reader.json(f"changes/{change_id}/change.json")
    if not _valid_change(change, change_id):
        raise _unbound()
    report_rel = f"changes/{change_id}/report"
    directory = confined(records, report_rel)
    if not directory.exists():
        return {"ok": True, "change_id": change_id, "report": None, "history": []}
    if not directory.is_dir():
        raise _invalid_repo()
    entries: list[tuple[int, str]] = []
    for entry in directory.iterdir():
        match = _REPORT_ORDINAL.fullmatch(entry.name)
        if match is not None:
            entries.append((int(match.group(1)), entry.name))
    history: list[dict[str, Any]] = []
    for ordinal, name in sorted(entries):
        relative = f"{report_rel}/{name}"
        raw = reader.read(relative)
        try:
            content = json.loads(raw) if raw is not None else None
        except (TypeError, ValueError):
            content = None
        if (
            not isinstance(content, dict)
            or content.get("schema") != REPORT_SCHEMA
            or type(content.get("record")) is not int
            or content.get("record") != ordinal
            or content.get("change_id") != change_id
        ):
            raise _invalid_repo()
        history.append(
            {
                "ref": relative,
                "sha256": hashlib.sha256(raw or b"").hexdigest(),
                "content": content,
            }
        )
    return {
        "ok": True,
        "change_id": change_id,
        "report": history[-1]["content"] if history else None,
        "history": history,
    }
