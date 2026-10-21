"""AC4-AC6, AC8, AC11: the impact record, determinism, conflicts and discharge."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from beddel_profile_dev._errors import (
    PROFILE_IMPACT_CONFLICT,
    PROFILE_IMPACT_UNBOUND,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev.tools.bind import profile_bind_inventory
from beddel_profile_dev.tools.change import profile_record_change
from beddel_profile_dev.tools.impact import profile_derive_impact
from beddel_profile_dev.tools.ratify import profile_ratify_inventory

from ._helpers import change_fixture, commit_all, good, write_version

RECORDS = ".beddel-profile/records"


def _impact_path(repo: Path, rev: str, change: str = "c1") -> Path:
    return repo / RECORDS / "changes" / change / "revisions" / rev / "impact.json"


def _run_all(repo: Path, base: str, rev: str, version: str = "v1") -> dict[str, Any]:
    profile_record_change(str(repo), "c1", base, rev)
    profile_bind_inventory(str(repo), rev, version)
    return profile_derive_impact(str(repo), "c1", rev)


def _delete_contract(repo: Path) -> None:
    (repo / "src" / "contracts.yaml").unlink()


def _fails(repo: Path, rev: str, change: str = "c1") -> ProfileError:
    with pytest.raises(ProfileError) as info:
        profile_derive_impact(str(repo), change, rev)
    return info.value


def test_record_has_exactly_the_documented_fields_and_counts(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path, _delete_contract)
    result = _run_all(repo, base, rev)
    impact = json.loads(_impact_path(repo, rev).read_text())
    assert set(impact) == {
        "schema",
        "change_id",
        "base",
        "revision",
        "inventory_version",
        "inventory_sha256",
        "footprint",
        "affected_points",
        "required_evidence",
    }
    assert impact["schema"] == "profile-dev/impact/1"
    assert impact["footprint"] == ["src/contracts.yaml"]
    assert impact["affected_points"] == [
        {
            "id": "contracts",
            "kind": "shared_contract",
            "path": "src/contracts.yaml",
            "target_present": False,
        }
    ]
    keys = [
        (o["class"], o["affected_point"], o["criterion"])
        for o in impact["required_evidence"]
    ]
    assert keys == [
        ("gate-unit", "api", "tests-pass"),
        ("gate-unit", "contracts", "tests-pass"),
        ("review-arch", "api", "arch-ok"),
    ]
    contracts = impact["required_evidence"][1]
    assert contracts["target_present"] is False
    assert contracts["basis"] == ["affected_point"]
    assert contracts["kind"] == "gate"
    assert result == {
        "ok": True,
        "change_id": "c1",
        "revision": rev,
        "impact": f"{RECORDS}/changes/c1/revisions/{rev}/impact.json",
        "affected_points": 1,
        "required_evidence": 3,
        "targets_absent": 1,
    }
    text = _impact_path(repo, rev).read_text()
    assert str(repo) not in text


def test_untouched_shared_contract_is_not_required_evidence(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(
        tmp_path, lambda r: (r / "src" / "api.py").write_text("x = 9\n")
    )
    _run_all(repo, base, rev)
    impact = json.loads(_impact_path(repo, rev).read_text())
    points = {o["affected_point"] for o in impact["required_evidence"]}
    assert points == {"api"}
    assert all(
        o["basis"] == ["active_component", "affected_point"]
        for o in impact["required_evidence"]
    )


def test_untouched_absent_component_is_out_and_touched_one_is_in(
    tmp_path: Path,
) -> None:
    data = good()
    data["components"].append(
        {"id": "ghost", "kind": "component", "path": "src/ghost.py"}
    )
    data["obligations"].append(
        {"class": "gate-unit", "affected_point": "ghost", "criterion": "tests-pass"}
    )
    repo, base, rev = change_fixture(
        tmp_path, lambda r: (r / "src" / "api.py").write_text("x = 9\n"), data
    )
    _run_all(repo, base, rev)
    impact = json.loads(_impact_path(repo, rev).read_text())
    assert "ghost" not in {o["affected_point"] for o in impact["required_evidence"]}


def test_rerun_rederives_identical_bytes(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path, _delete_contract)
    _run_all(repo, base, rev)
    first = _impact_path(repo, rev).read_bytes()
    profile_derive_impact(str(repo), "c1", rev)
    assert _impact_path(repo, rev).read_bytes() == first


def test_stored_record_that_differs_conflicts_and_is_untouched(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path, _delete_contract)
    _run_all(repo, base, rev)
    path = _impact_path(repo, rev)
    path.write_text("{}\n")
    assert _fails(repo, rev).code == PROFILE_IMPACT_CONFLICT
    assert path.read_text() == "{}\n"


def test_without_a_change_record_it_is_unbound_and_writes_nothing(
    tmp_path: Path,
) -> None:
    repo, _, rev = change_fixture(tmp_path)
    profile_bind_inventory(str(repo), rev, "v1")
    assert _fails(repo, rev).code == PROFILE_IMPACT_UNBOUND
    assert not (repo / RECORDS / "changes").exists()


def test_without_a_binding_it_is_unbound(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path)
    profile_record_change(str(repo), "c1", base, rev)
    assert _fails(repo, rev).code == PROFILE_IMPACT_UNBOUND
    assert not _impact_path(repo, rev).exists()


@pytest.mark.parametrize("field", ["inventory_version", "inventory_sha256", "revision"])
def test_binding_that_disagrees_with_the_snapshot_is_unbound(
    tmp_path: Path, field: str
) -> None:
    repo, base, rev = change_fixture(tmp_path)
    _run_all(repo, base, rev)
    _impact_path(repo, rev).unlink()
    binding = repo / RECORDS / "revisions" / rev / "binding.json"
    data = json.loads(binding.read_text())
    data[field] = "other"
    binding.write_text(json.dumps(data))
    assert _fails(repo, rev).code == PROFILE_IMPACT_UNBOUND
    assert not _impact_path(repo, rev).exists()


def test_malformed_snapshot_is_unbound(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path)
    _run_all(repo, base, rev)
    _impact_path(repo, rev).unlink()
    snapshot = repo / RECORDS / "revisions" / rev / "snapshot.json"
    data = json.loads(snapshot.read_text())
    data["obligations"][0]["affected_point"] = "missing"
    snapshot.write_text(json.dumps(data))
    assert _fails(repo, rev).code == PROFILE_IMPACT_UNBOUND


def test_work_tree_edits_and_the_environment_do_not_change_the_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base, rev = change_fixture(tmp_path, _delete_contract)
    _run_all(repo, base, rev)
    first = _impact_path(repo, rev).read_bytes()
    _impact_path(repo, rev).unlink()
    (repo / "src" / "api.py").write_text("dirty\n")
    (repo / "src" / "contracts.yaml").write_text("restored\n")
    monkeypatch.setenv("GIT_DIR", str(tmp_path))
    profile_derive_impact(str(repo), "c1", rev)
    assert _impact_path(repo, rev).read_bytes() == first


def test_symlinked_impact_dir_escaping_the_repo_is_refused(tmp_path: Path) -> None:
    repo, base, rev = change_fixture(tmp_path)
    profile_record_change(str(repo), "c1", base, rev)
    profile_bind_inventory(str(repo), rev, "v1")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = repo / RECORDS / "changes" / "c1" / "revisions" / rev
    for child in link.iterdir():
        child.unlink()
    link.rmdir()
    os.symlink(outside, link)
    err = _fails(repo, rev)
    assert err.code in (PROFILE_IMPACT_UNBOUND, PROFILE_REPOSITORY_INVALID)
    assert list(outside.iterdir()) == []


# --- discharge by a new Analyzed revision (AC6) -------------------------------


def _blocked_then_fixed(tmp_path: Path) -> tuple[Path, str, str, str]:
    broken = good()
    broken["obligations"][0]["class"] = "ghost"
    repo, base, first = change_fixture(
        tmp_path, lambda r: (r / "src" / "api.py").write_text("x = 2\n"), broken
    )
    profile_record_change(str(repo), "c1", base, first)
    with pytest.raises(ProfileError):
        profile_bind_inventory(str(repo), first, "v1")
    write_version(repo, "v2", good("v2"))
    profile_ratify_inventory(str(repo), "v2", "tester")
    second = commit_all(repo, "fix")
    return repo, base, first, second


def test_new_revision_discharges_the_earlier_block_once(tmp_path: Path) -> None:
    repo, base, first, second = _blocked_then_fixed(tmp_path)
    _run_all(repo, base, second, "v2")
    blocks = repo / RECORDS / "revisions" / first / "integrity-blocks"
    discharged = list(blocks.glob("*.discharged.json"))
    assert len(discharged) == 1
    record = json.loads(discharged[0].read_text())
    assert set(record) == {
        "schema",
        "revision",
        "block",
        "change_id",
        "resolved_by_revision",
        "resolved_by_version",
        "resolved_by_sha256",
    }
    assert record["revision"] == first and record["resolved_by_revision"] == second
    assert record["change_id"] == "c1" and record["resolved_by_version"] == "v2"
    block = blocks / record["block"]
    assert block.is_file()
    # the blocked revision stays blocked for binding
    with pytest.raises(ProfileError):
        profile_bind_inventory(str(repo), first, "v1")
    before = discharged[0].read_bytes()
    profile_derive_impact(str(repo), "c1", second)
    assert discharged[0].read_bytes() == before


def test_block_already_discharged_by_version_is_left_untouched(tmp_path: Path) -> None:
    repo, base, first, second = _blocked_then_fixed(tmp_path)
    blocks = repo / RECORDS / "revisions" / first / "integrity-blocks"
    block = next(blocks.glob("*.json"))
    name = block.name[: -len(".json")] + ".discharged.json"
    marker = b'{"schema": "profile-dev/integrity-discharge/1"}\n'
    (blocks / name).write_bytes(marker)
    _run_all(repo, base, second, "v2")
    assert (blocks / name).read_bytes() == marker
    assert len(list(blocks.glob("*.discharged.json"))) == 1


def test_discharge_by_version_skips_a_block_already_discharged_by_revision(
    tmp_path: Path,
) -> None:
    broken = good()
    broken["obligations"][0]["class"] = "ghost"

    def add_v2(repo: Path) -> None:
        write_version(repo, "v2", good("v2"))
        profile_ratify_inventory(str(repo), "v2", "tester")

    repo, _base, first = change_fixture(tmp_path, add_v2, broken)
    with pytest.raises(ProfileError):
        profile_bind_inventory(str(repo), first, "v1")
    blocks = repo / RECORDS / "revisions" / first / "integrity-blocks"
    block = next(blocks.glob("*.json"))
    name = block.name[: -len(".json")] + ".discharged.json"
    marker = b'{"schema": "profile-dev/integrity-discharge-by-revision/1"}\n'
    (blocks / name).write_bytes(marker)
    # binding v2 at the same revision would discharge the block by version
    profile_bind_inventory(str(repo), first, "v2")
    assert (blocks / name).read_bytes() == marker


def test_blocks_of_revisions_linked_only_to_other_changes_are_untouched(
    tmp_path: Path,
) -> None:
    repo, base, first, second = _blocked_then_fixed(tmp_path)
    # drop the c1 link of the blocked revision: it is now only a revision of c0
    link_dir = repo / RECORDS / "changes" / "c1" / "revisions" / first
    for child in link_dir.iterdir():
        child.unlink()
    link_dir.rmdir()
    profile_record_change(str(repo), "c0", base, first)
    _run_all(repo, base, second, "v2")
    blocks = repo / RECORDS / "revisions" / first / "integrity-blocks"
    assert list(blocks.glob("*.discharged.json")) == []


def test_determinations_do_not_change_the_impact_bytes(tmp_path: Path) -> None:
    from beddel_profile_dev.tools.determine import profile_declare_non_applicability

    repo, base, rev = change_fixture(tmp_path, _delete_contract)
    _run_all(repo, base, rev)
    path = _impact_path(repo, rev)
    before = path.read_bytes()
    state = {
        p: p.read_bytes()
        for p in (repo / RECORDS / "revisions" / rev).rglob("*")
        if p.is_file()
    }
    profile_declare_non_applicability(
        str(repo), rev, "gate-unit", "contracts", "tests-pass", "tester"
    )
    path.unlink()
    profile_derive_impact(str(repo), "c1", rev)
    assert path.read_bytes() == before
    for file, data in state.items():
        assert file.read_bytes() == data


@pytest.mark.parametrize("base", ["--output=../escaped", "HEAD~1", "nope", 7])
def test_a_tampered_base_in_the_change_record_is_unbound_and_writes_nothing(
    tmp_path: Path, base: object
) -> None:
    repo, b, rev = change_fixture(tmp_path, _delete_contract)
    profile_record_change(str(repo), "c1", b, rev)
    profile_bind_inventory(str(repo), rev, "v1")
    for name in ("change.json", f"revisions/{rev}/revision.json"):
        path = repo / RECORDS / "changes" / "c1" / name
        data = json.loads(path.read_text())
        data["base"] = base
        path.write_text(json.dumps(data))
    with pytest.raises(ProfileError) as info:
        profile_derive_impact(str(repo), "c1", rev)
    assert info.value.code == PROFILE_IMPACT_UNBOUND
    assert not _impact_path(repo, rev).exists()
    assert not (tmp_path / "escaped").exists()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("class", ["x"]),
        ("affected_point", {"a": 1}),
        ("criterion", 5),
        ("criterion", None),
    ],
)
def test_obligation_fields_of_a_snapshot_must_be_strings(
    tmp_path: Path, key: str, value: object
) -> None:
    repo, base, rev = change_fixture(tmp_path)
    _run_all(repo, base, rev)
    _impact_path(repo, rev).unlink()
    path = repo / RECORDS / "revisions" / rev / "snapshot.json"
    data = json.loads(path.read_text())
    data["obligations"][0][key] = value
    path.write_text(json.dumps(data))
    assert _fails(repo, rev).code == PROFILE_IMPACT_UNBOUND
    assert not _impact_path(repo, rev).exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("inventory_version", None),
        ("inventory_sha256", None),
        ("inventory_sha256", "short"),
    ],
)
def test_snapshot_identity_fields_must_be_well_formed(
    tmp_path: Path, field: str, value: object
) -> None:
    repo, base, rev = change_fixture(tmp_path)
    _run_all(repo, base, rev)
    _impact_path(repo, rev).unlink()
    for name in ("binding.json", "snapshot.json"):
        path = repo / RECORDS / "revisions" / rev / name
        data = json.loads(path.read_text())
        data[field] = value
        path.write_text(json.dumps(data))
    assert _fails(repo, rev).code == PROFILE_IMPACT_UNBOUND
