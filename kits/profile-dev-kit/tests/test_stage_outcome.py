"""Append-only Stage outcome record validation and persistence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from beddel_profile_dev._errors import PROFILE_STAGE_OUTCOME_REFUSED, ProfileError
from beddel_profile_dev._io import records_root
from beddel_profile_dev.tools import stage_outcome
from beddel_profile_dev.tools.stage_outcome import profile_record_stage_outcome

from ._helpers import commit_all, init_repo


def repo_fixture(tmp_path: Path) -> Path:
    repo = init_repo(tmp_path / "repo")
    (repo / "story.md").write_text("story")
    commit_all(repo)
    return repo


def record_root(tmp_path: Path, repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return records_root(repo, "records/profile-dev")


def test_ordinals_are_append_only_and_outside_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_fixture(tmp_path)
    root = record_root(tmp_path, repo, monkeypatch)
    first = profile_record_stage_outcome(
        str(repo), "story-1", "plan", "succeeded", "spec.created", {"out_of_scope": 0}
    )
    second = profile_record_stage_outcome(
        str(repo), "story-1", "plan", "succeeded", "spec.reused", {"out_of_scope": 0}
    )
    first_path = root / str(first["path"])
    assert first_path.exists()
    assert second["record"] == 2
    assert root / "stage-outcomes" == root / Path(str(first["path"])).parent
    assert (root / "stage-outcomes").is_relative_to(tmp_path / "home")
    assert not (repo / "stage-outcomes").exists()
    assert not list(repo.glob("stage-outcomes/*"))
    stored = json.loads((root / "stage-outcomes/2.json").read_text())
    assert stored["schema"] == "profile-dev/stage-outcome/1"
    assert stored["recorded_at"].endswith("Z")


def test_preexisting_and_racing_files_stay_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_fixture(tmp_path)
    root = record_root(tmp_path, repo, monkeypatch)
    directory = root / "stage-outcomes"
    directory.mkdir(parents=True)
    existing = b"existing\n"
    (directory / "1.json").write_bytes(existing)
    result = profile_record_stage_outcome(
        str(repo), "story-1", "plan", "succeeded", "spec.created", {}
    )
    assert result["record"] == 2
    assert (directory / "1.json").read_bytes() == existing

    original = stage_outcome.write_create_only
    calls = 0

    def racing(root_path: Path, relative: str, data: bytes) -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            path = root_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"racer\n")
        return original(root_path, relative, data)

    monkeypatch.setattr(stage_outcome, "write_create_only", racing)
    third = profile_record_stage_outcome(
        str(repo), "story-1", "plan", "succeeded", "spec.created", {}
    )
    assert third["record"] == 4
    assert (directory / "3.json").read_bytes() == b"racer\n"


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"stage": "Bad Stage"}, "stage.invalid"),
        ({"outcome": "unknown"}, "outcome.invalid"),
        ({"reason": "Bad reason"}, "reason.invalid"),
        ({"story_key": "BAD"}, "story_key.invalid"),
        ({"story_key": None, "outcome": "failed"}, "story_key.required"),
        ({"refs": {"Bad": 1}}, "refs.invalid"),
        ({"refs": {"count": -1}}, "refs.invalid"),
    ],
)
def test_bad_fields_write_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kwargs: dict[str, object],
    reason: str,
) -> None:
    repo = repo_fixture(tmp_path)
    root = record_root(tmp_path, repo, monkeypatch)
    values: dict[str, object] = {
        "repo_path": str(repo),
        "story_key": "story-1",
        "stage": "plan",
        "outcome": "succeeded",
        "reason": "spec.created",
        "refs": {},
    }
    values.update(kwargs)
    with pytest.raises(ProfileError) as exc_info:
        profile_record_stage_outcome(**values)
    assert exc_info.value.code == PROFILE_STAGE_OUTCOME_REFUSED
    assert exc_info.value.details["reason"] == reason
    assert not (root / ".config" / "beddel" / "records").exists()


def test_token_and_control_values_are_rejected_without_echoing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repo_fixture(tmp_path)
    root = record_root(tmp_path, repo, monkeypatch)
    token = "gh" + "p_" + "A" * 36
    for value in (token, "safe\nvalue"):
        with pytest.raises(ProfileError) as exc_info:
            profile_record_stage_outcome(
                str(repo),
                "story-1",
                "plan",
                "succeeded",
                "spec.created",
                {"ref": value},
            )
        assert exc_info.value.code == PROFILE_STAGE_OUTCOME_REFUSED
    assert not (root / ".config" / "beddel" / "records").exists()


def test_invalid_repository_does_not_create_a_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "home"
    monkeypatch.setenv("HOME", str(root))
    with pytest.raises(ProfileError):
        profile_record_stage_outcome(
            str(tmp_path / "missing"),
            "story-1",
            "plan",
            "succeeded",
            "spec.created",
            {},
        )
    assert not (root / ".config" / "beddel" / "records").exists()


def test_stage_outcomes_term_is_isolated_to_its_tool() -> None:
    module_root = Path(__file__).resolve().parents[1] / "python" / "beddel_profile_dev"
    matches = {
        path.name
        for path in module_root.rglob("*.py")
        if "stage-outcomes" in path.read_text()
    }
    assert matches == {"stage_outcome.py"}
