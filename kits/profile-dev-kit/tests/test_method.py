from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from beddel_profile_dev._errors import ProfileError
from beddel_profile_dev.method import load_method, render, valid_instruction
from beddel_profile_dev.tools.method import (
    profile_deliver_derive,
    profile_deliver_method,
    profile_stage_instruction,
)
from beddel_profile_dev.tools.stage_outcome import profile_record_stage_outcome

from ._helpers import commit_all, good, init_repo, write_version

STORY = "8-3b-method-fixture"


def _method() -> dict[str, object]:
    return {
        "schema": "profile-dev/method/1",
        "inputs": {
            "story_path": "stories/{story_key}.md",
            "guide_path": "AGENTS.md",
            "spec_path": "specs/{story_key}.md",
            "status_path": "",
            "branch": "feat/story-{story_key}",
            "remote": "origin",
            "base_branch": "main",
        },
        "methods": {
            "alpha": {
                "plan": "Plan this story.",
                "implement": "Implement this unit.",
                "fix": "Fix these findings.",
            }
        },
    }


def test_load_method_accepts_schema_and_refuses_each_violation() -> None:
    data = yaml.safe_dump(_method(), sort_keys=False).encode()
    assert load_method(data) is not None
    assert render("specs/{story_key}.md", STORY) == f"specs/{STORY}.md"
    cases = [
        {**_method(), "schema": "wrong"},
        {**_method(), "inputs": {}},
        {**_method(), "extra": True},
        {
            **_method(),
            "methods": {"native": {"plan": "x", "implement": "x", "fix": "x"}},
        },
        {
            **_method(),
            "methods": {"alpha": {"plan": "x", "implement": "x", "review": "x"}},
        },
    ]
    for instruction in ("a$b", "a\x07b", "ghp_1234567890"):
        value = _method()
        value["methods"] = {
            "alpha": {
                "plan": instruction,
                "implement": "x",
                "fix": "x",
            }
        }
        cases.append(value)
    invalid_template = _method()
    invalid_template["inputs"] = {**invalid_template["inputs"], "guide_path": "{x}"}
    cases.append(invalid_template)
    for value in cases:
        assert load_method(yaml.safe_dump(value).encode()) is None
    too_long = _method()
    too_long["methods"] = {"alpha": {"plan": "x" * 2001, "implement": "x", "fix": "x"}}
    assert load_method(yaml.safe_dump(too_long).encode()) is None
    assert load_method(yaml.safe_dump(_method()).encode() + b"\x00") is None


def test_stage_instruction_validates_text() -> None:
    assert valid_instruction("use the declared paths")
    assert not valid_instruction("")
    assert not valid_instruction("contains $ resolver syntax")
    assert not valid_instruction("ghp_12345678901")
    with pytest.raises(ProfileError):
        profile_stage_instruction("review", "use the declared paths")
    with pytest.raises(ProfileError):
        profile_stage_instruction("plan", "a$b")
    result = profile_stage_instruction("plan", "use the declared paths")
    assert result["stage"] == "plan" and result["instruction_sha256"]


def test_deliver_method_reads_head_and_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_repo(tmp_path / "repo")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    method_path = repo / ".beddel-profile" / "method.yaml"
    native = profile_deliver_method(str(repo), "native")
    assert native == {
        "method": "native",
        "method_sha256": None,
        "plan": "",
        "implement": "",
        "fix": "",
    }
    method_path.parent.mkdir(parents=True)
    method_path.write_text(yaml.safe_dump(_method(), sort_keys=False))
    with pytest.raises(ProfileError) as absent:
        profile_deliver_method(str(repo), "alpha")
    assert absent.value.details == {"reason": "method.absent"}

    commit_all(repo, "method")
    selected = profile_deliver_method(str(repo), "alpha")
    assert selected["plan"] == "Plan this story."
    assert selected["method_sha256"]

    method_path.write_text("schema: wrong\n")
    selected_again = profile_deliver_method(str(repo), "alpha")
    assert selected_again["plan"] == "Plan this story."

    with pytest.raises(ProfileError) as unknown:
        profile_deliver_method(str(repo), "unknown")
    assert unknown.value.details == {"reason": "method.unknown"}
    with pytest.raises(ProfileError) as malformed:
        profile_deliver_method(str(repo), "../bad")
    assert malformed.value.details == {"reason": "method.invalid"}

    commit_all(repo, "invalid method")
    with pytest.raises(ProfileError) as invalid:
        profile_deliver_method(str(repo), "alpha")
    assert invalid.value.details == {"reason": "method.invalid"}


def test_derive_native_and_named_method_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_repo(tmp_path / "repo")
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Fixture"], check=True
    )
    (repo / "AGENTS.md").write_text("guide\n")
    (repo / "stories").mkdir()
    (repo / "specs").mkdir()
    write_version(repo, "v1", good())
    (repo / ".beddel-profile" / "inventory" / "v1.ratification.yaml").write_text(
        "ratified\n"
    )
    approval = repo / ".beddel-profile" / "approvals" / STORY
    approval.mkdir(parents=True)
    for number, owner in (("1", "owner-one"), ("2", "owner-two"), ("10", "owner-ten")):
        (approval / f"{number}.yaml").write_text(f"approved_by: {owner}\n")
    method_path = repo / ".beddel-profile" / "method.yaml"
    method_path.parent.mkdir(parents=True, exist_ok=True)
    method_path.write_text(yaml.safe_dump(_method(), sort_keys=False))
    base = commit_all(repo, "base")
    tip = commit_all(repo, "tip")
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", tip],
        check=True,
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    profile_record_stage_outcome(
        str(repo), STORY, "implement", "succeeded", "unit.committed", {"base": base}
    )
    native = profile_deliver_derive(str(repo), STORY, "native")
    named = profile_deliver_derive(str(repo), STORY, "alpha")
    assert native["ok"] and named["ok"]
    assert native["method"] == "native" and named["method"] == "alpha"
    assert native["inputs"]["method"] == "native" and native["inputs"]["stage"] == "all"
    empty = profile_deliver_derive(str(repo), STORY, "")
    assert empty["ok"] and empty["method"] == "native"
    values = named["inputs"]
    assert values["base_ref"] == base != tip
    assert values["actor"] == "owner-ten"
    assert values["inventory_version"] == "v1"
    assert values["spec_path"] == f"specs/{STORY}.md"
    assert values["parent_path"] == "" and values["parent_branch"] == ""
    selected = profile_deliver_method(str(repo), "alpha")
    assert selected["plan"] == "Plan this story."


def test_derive_refusals_name_their_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = init_repo(tmp_path / "repo")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    def reason(story: str, method: str) -> object:
        return profile_deliver_derive(str(repo), story, method)["reason"]

    path = repo / ".beddel-profile" / "method.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    assert reason("../x", "native") == "story_key.invalid"
    assert reason(STORY, "native") == "method.absent"
    path.write_text("schema: wrong\n")
    commit_all(repo, "invalid")
    assert reason(STORY, "native") == "method.invalid"
    path.write_text(yaml.safe_dump(_method()))
    commit_all(repo, "valid")
    assert reason(STORY, "nope") == "method.unknown"
    assert reason(STORY, "../bad") == "method.invalid"
    assert reason(STORY, "alpha") == "base.unknown"
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )
    assert reason(STORY, "alpha") == "inventory.absent"


def _committed_method_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = init_repo(tmp_path / "repo")
    method_path = repo / ".beddel-profile" / "method.yaml"
    method_path.parent.mkdir(parents=True, exist_ok=True)
    method_path.write_text(yaml.safe_dump(_method(), sort_keys=False))
    base = commit_all(repo, "method")
    subprocess.run(
        ["git", "-C", str(repo), "update-ref", "refs/remotes/origin/main", base],
        check=True,
    )
    return repo, base


def test_derive_refusal_reasons_cover_the_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _base = _committed_method_repo(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert (
        profile_deliver_derive(str(repo), "a" * 70, "alpha")["reason"]
        == "change_id.invalid"
    )

    write_version(repo, "v1", good())
    (repo / ".beddel-profile" / "inventory" / "v1.ratification.yaml").write_text("x\n")
    write_version(repo, "v2", good("v2"))
    (repo / ".beddel-profile" / "inventory" / "v2.ratification.yaml").write_text("x\n")
    commit_all(repo, "ambiguous inventory")
    assert (
        profile_deliver_derive(str(repo), STORY, "alpha")["reason"]
        == "inventory.ambiguous"
    )

    repo_actor, _ = _committed_method_repo(tmp_path / "actor")
    write_version(repo_actor, "v1", good())
    (repo_actor / ".beddel-profile" / "inventory" / "v1.ratification.yaml").write_text(
        "x\n"
    )
    commit_all(repo_actor, "inventory")
    assert (
        profile_deliver_derive(str(repo_actor), STORY, "alpha")["reason"]
        == "actor.unknown"
    )

    repo_records, _ = _committed_method_repo(tmp_path / "records")
    write_version(repo_records, "v1", good())
    (
        repo_records / ".beddel-profile" / "inventory" / "v1.ratification.yaml"
    ).write_text("x\n")
    commit_all(repo_records, "inventory")
    from beddel_profile_dev._io import records_root

    stage_root = records_root(repo_records, "records/profile-dev")
    (stage_root / "stage-outcomes").mkdir(parents=True)
    (stage_root / "stage-outcomes" / "1.json").write_text("not json")
    assert (
        profile_deliver_derive(str(repo_records), STORY, "alpha")["reason"]
        == "records.unreadable"
    )

    repo_branch, _ = _committed_method_repo(tmp_path / "branch")
    bad_method = _method()
    bad_method["inputs"] = {**bad_method["inputs"], "branch": "feat/{story_key}"}
    (repo_branch / ".beddel-profile" / "method.yaml").write_text(
        yaml.safe_dump(bad_method)
    )
    commit_all(repo_branch, "bad rendered branch")
    assert (
        profile_deliver_derive(str(repo_branch), "bad..key", "alpha")["reason"]
        == "method.invalid"
    )

    repo_remote, _ = _committed_method_repo(tmp_path / "remote")
    remote_method = _method()
    remote_method["inputs"] = {**remote_method["inputs"], "remote": "{story_key}"}
    (repo_remote / ".beddel-profile" / "method.yaml").write_text(
        yaml.safe_dump(remote_method)
    )
    commit_all(repo_remote, "bad rendered remote")
    assert (
        profile_deliver_derive(str(repo_remote), "a..b", "alpha")["reason"]
        == "method.invalid"
    )

    repo_nested, _ = _committed_method_repo(tmp_path / "nested")
    nested = repo_nested / ".beddel-profile" / "inventory" / "sub"
    nested.mkdir(parents=True)
    (nested / "v1.yaml").write_text(yaml.safe_dump(good()))
    (repo_nested / ".beddel-profile" / "inventory" / "v1.ratification.yaml").write_text(
        "x\n"
    )
    commit_all(repo_nested, "nested inventory file")
    assert (
        profile_deliver_derive(str(repo_nested), STORY, "alpha")["reason"]
        == "inventory.absent"
    )


def test_derive_actor_follows_the_latest_approval_then_user_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    repo, _base = _committed_method_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Local"], check=True)
    write_version(repo, "v1", good())
    (repo / ".beddel-profile" / "inventory" / "v1.ratification.yaml").write_text("x\n")
    approvals = repo / ".beddel-profile" / "approvals" / STORY
    approvals.mkdir(parents=True)
    (approvals / "1.yaml").write_text("approved_by: older\n")
    commit_all(repo, "older approval")
    assert profile_deliver_derive(str(repo), STORY, "alpha")["inputs"]["actor"] == (
        "older"
    )
    (approvals / "2.yaml").write_text("approved_by: ''\n")
    commit_all(repo, "invalid latest approval")
    assert profile_deliver_derive(str(repo), STORY, "alpha")["inputs"]["actor"] == (
        "Local"
    )
    (approvals / "3.yaml").write_text(
        "approved_by: a\napproved_at: 2026-13-01T00:00:00Z\n"
    )
    commit_all(repo, "unparseable latest approval")
    assert profile_deliver_derive(str(repo), STORY, "alpha")["inputs"]["actor"] == (
        "Local"
    )


def test_kit_names_no_planning_method() -> None:
    needle = "b" + "mad"
    result = subprocess.run(
        ["git", "grep", "-n", "-i", needle, "--", "kits/profile-dev-kit"],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout == ""
