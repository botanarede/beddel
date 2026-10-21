"""AC7, AC8, AC11: the determination of non-applicability is a recorded human act."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pytest
from beddel_profile_dev._errors import (
    PROFILE_DETERMINATION_REFUSED,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev.tools.bind import profile_bind_inventory
from beddel_profile_dev.tools.determine import profile_declare_non_applicability

from ._helpers import change_fixture

RECORDS = ".beddel-profile/records"


def _bound(tmp_path: Path) -> tuple[Path, str]:
    repo, _, rev = change_fixture(
        tmp_path, lambda r: (r / "src" / "contracts.yaml").unlink()
    )
    profile_bind_inventory(str(repo), rev, "v1")
    return repo, rev


def _dir(repo: Path, rev: str) -> Path:
    return repo / RECORDS / "revisions" / rev / "non-applicability"


def _declare(
    repo: Path,
    rev: str,
    point: str = "contracts",
    actor: str = "tester",
    cls: str = "gate-unit",
    crit: str = "tests-pass",
) -> dict[str, object]:
    return profile_declare_non_applicability(str(repo), rev, cls, point, crit, actor)


def _refused(repo: Path, rev: str, reason: str, **kwargs: str) -> None:
    before = {p for p in (repo / RECORDS).rglob("*")}
    with pytest.raises(ProfileError) as info:
        _declare(repo, rev, **kwargs)
    assert info.value.code == PROFILE_DETERMINATION_REFUSED
    assert info.value.details == {"reason": reason}
    assert info.value.message == (
        f"determination of non-applicability refused: {reason}"
    )
    assert {p for p in (repo / RECORDS).rglob("*")} == before


def test_writes_exactly_the_record_for_the_ratifying_actor(tmp_path: Path) -> None:
    repo, rev = _bound(tmp_path)
    result = _declare(repo, rev)
    assert result["ok"] is True
    path = _dir(repo, rev) / "gate-unit+contracts+tests-pass.json"
    record = json.loads(path.read_text())
    binding = json.loads(
        (repo / RECORDS / "revisions" / rev / "binding.json").read_text()
    )
    assert set(record) == {
        "schema",
        "revision",
        "inventory_version",
        "inventory_sha256",
        "class",
        "affected_point",
        "criterion",
        "determined_by",
        "determined_at",
    }
    assert record["schema"] == "profile-dev/non-applicability/1"
    assert record["revision"] == rev
    assert record["inventory_sha256"] == binding["inventory_sha256"]
    assert record["determined_by"] == "tester"
    datetime.strptime(record["determined_at"], "%Y-%m-%dT%H:%M:%SZ")


def test_actor_is_never_taken_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev = _bound(tmp_path)
    monkeypatch.setenv("USER", "someone-else")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "someone-else")
    _declare(repo, rev, actor="tester")
    record = json.loads(
        (_dir(repo, rev) / "gate-unit+contracts+tests-pass.json").read_text()
    )
    assert record["determined_by"] == "tester"


def test_only_the_ratifying_actor_may_determine(tmp_path: Path) -> None:
    repo, rev = _bound(tmp_path)
    _refused(repo, rev, "actor.not_ratifier", actor="Tester")
    _refused(repo, rev, "actor.not_ratifier", actor="someone else")


@pytest.mark.parametrize("actor", ["", "   ", "a\x00b", "x" * 201])
def test_invalid_actor(tmp_path: Path, actor: str) -> None:
    repo, rev = _bound(tmp_path)
    _refused(repo, rev, "actor.invalid", actor=actor)


@pytest.mark.parametrize("field", ["cls", "point", "crit"])
def test_invalid_ids(tmp_path: Path, field: str) -> None:
    repo, rev = _bound(tmp_path)
    _refused(repo, rev, "id.invalid", **{field: "Bad Id"})


def test_unknown_obligation(tmp_path: Path) -> None:
    repo, rev = _bound(tmp_path)
    _refused(repo, rev, "obligation.unknown", cls="review-arch", point="contracts")
    _refused(repo, rev, "obligation.unknown", crit="nope")


def test_present_target_is_refused(tmp_path: Path) -> None:
    repo, rev = _bound(tmp_path)
    _refused(repo, rev, "target.present", point="api")


def test_no_binding_is_refused(tmp_path: Path) -> None:
    repo, _, rev = change_fixture(tmp_path)
    (repo / RECORDS).mkdir(parents=True)
    _refused(repo, rev, "binding.absent")


def test_second_determination_is_refused_and_the_first_is_unchanged(
    tmp_path: Path,
) -> None:
    repo, rev = _bound(tmp_path)
    _declare(repo, rev)
    path = _dir(repo, rev) / "gate-unit+contracts+tests-pass.json"
    first = path.read_bytes()
    _refused(repo, rev, "determination.exists")
    assert path.read_bytes() == first


def test_binding_digest_that_does_not_match_the_tree_is_refused(
    tmp_path: Path,
) -> None:
    repo, rev = _bound(tmp_path)
    binding = repo / RECORDS / "revisions" / rev / "binding.json"
    data = json.loads(binding.read_text())
    data["inventory_sha256"] = "0" * 64
    binding.write_text(json.dumps(data))
    _refused(repo, rev, "version.unratified")


def test_a_work_tree_ratification_edit_is_not_trusted(tmp_path: Path) -> None:
    repo, rev = _bound(tmp_path)
    record = repo / ".beddel-profile" / "inventory" / "v1.ratification.yaml"
    record.write_text(record.read_text().replace("tester", "intruder"))
    _declare(repo, rev, actor="tester")  # the committed record decides
    _refused_actor = "intruder"
    with pytest.raises(ProfileError):
        _declare(repo, rev, point="contracts", actor=_refused_actor)


def test_scoped_to_one_revision_and_never_carried_over(tmp_path: Path) -> None:
    repo, rev = _bound(tmp_path)
    _declare(repo, rev)
    assert list((repo / RECORDS / "revisions").iterdir()) == [
        repo / RECORDS / "revisions" / rev
    ]
    other = repo / RECORDS / "revisions" / ("f" * 40)
    assert not (other / "non-applicability").exists()


def test_symlinked_determination_dir_escaping_the_repo_is_refused(
    tmp_path: Path,
) -> None:
    repo, rev = _bound(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(outside, _dir(repo, rev))
    with pytest.raises(ProfileError) as info:
        _declare(repo, rev)
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert list(outside.iterdir()) == []


def test_nothing_in_the_runtime_writes_a_determination_by_itself(
    tmp_path: Path,
) -> None:
    repo, rev = _bound(tmp_path)
    from beddel_profile_dev.tools.change import profile_record_change
    from beddel_profile_dev.tools.impact import profile_derive_impact

    profile_record_change(str(repo), "c1", "HEAD~1", rev)
    profile_derive_impact(str(repo), "c1", rev)
    assert not _dir(repo, rev).exists()
