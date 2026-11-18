from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from beddel_profile_dev._errors import ProfileError
from beddel_profile_dev.method import load_method, valid_instruction
from beddel_profile_dev.tools.method import (
    profile_deliver_method,
    profile_stage_instruction,
)

from ._helpers import commit_all, init_repo


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
