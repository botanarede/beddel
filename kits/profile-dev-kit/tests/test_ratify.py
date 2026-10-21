"""AC3: ratification is transport; fixed refusals write nothing."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml
from beddel_profile_dev._errors import PROFILE_RATIFICATION_REFUSED, ProfileError
from beddel_profile_dev.tools.ratify import profile_ratify_inventory

from ._helpers import INVENTORY_DIR, good, init_repo, write_version


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return init_repo(tmp_path / "repo")


def _record(repo: Path, version: str = "v1") -> Path:
    return repo / INVENTORY_DIR / f"{version}.ratification.yaml"


def _refused(repo: Path, version: str, actor: str) -> ProfileError:
    with pytest.raises(ProfileError) as info:
        profile_ratify_inventory(str(repo), version, actor)
    assert info.value.code == PROFILE_RATIFICATION_REFUSED
    assert info.value.message.startswith("inventory ratification refused: ")
    return info.value


def test_writes_exactly_the_record(repo: Path) -> None:
    path = write_version(repo, "v1", good())
    result = profile_ratify_inventory(str(repo), "v1", "Maintainer One")
    record = yaml.safe_load(_record(repo).read_text())
    assert set(record) == {
        "schema",
        "inventory_version",
        "inventory_sha256",
        "ratified_by",
        "ratified_at",
    }
    assert record["schema"] == "profile-dev/ratification/1"
    assert record["inventory_version"] == "v1"
    assert record["inventory_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert record["ratified_by"] == "Maintainer One"
    assert record["ratified_at"].endswith("Z") and "T" in record["ratified_at"]
    assert (
        result["ok"] is True
        and result["inventory_sha256"] == record["inventory_sha256"]
    )


def test_actor_comes_only_from_the_input(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_version(repo, "v1", good())
    monkeypatch.setenv("USER", "envuser")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "envgit")
    profile_ratify_inventory(str(repo), "v1", "explicit")
    assert yaml.safe_load(_record(repo).read_text())["ratified_by"] == "explicit"


def test_second_ratification_is_refused_and_record_unchanged(repo: Path) -> None:
    write_version(repo, "v1", good())
    profile_ratify_inventory(str(repo), "v1", "a")
    before = _record(repo).read_bytes()
    assert _refused(repo, "v1", "b").details == {"reason": "record.exists"}
    assert _record(repo).read_bytes() == before


def test_absent_version_file(repo: Path) -> None:
    _refused(repo, "v1", "a")
    assert not _record(repo).exists()


@pytest.mark.parametrize("content", ["- a\n- b\n", "just text\n", "a: [\n"])
def test_not_a_mapping(repo: Path, content: str) -> None:
    path = repo / INVENTORY_DIR / "v1.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(content)
    assert _refused(repo, "v1", "a").details == {"reason": "inventory.not_mapping"}
    assert not _record(repo).exists()


def test_version_mismatch(repo: Path) -> None:
    write_version(repo, "v1", good("v2"))
    assert _refused(repo, "v1", "a").details == {"reason": "version.mismatch"}
    assert not _record(repo).exists()


@pytest.mark.parametrize("version", ["", "../x", "A", "v1/../v2", "a b"])
def test_invalid_id(repo: Path, version: str) -> None:
    assert _refused(repo, version, "a").details == {"reason": "id.invalid"}


@pytest.mark.parametrize("actor", ["", "   ", "x" * 201, "a\nb", "a\x00b", "a\x7fb"])
def test_invalid_actor(repo: Path, actor: str) -> None:
    write_version(repo, "v1", good())
    assert _refused(repo, "v1", actor).details == {"reason": "actor.invalid"}
    assert not _record(repo).exists()


def test_actor_of_exactly_200_chars_is_accepted(repo: Path) -> None:
    write_version(repo, "v1", good())
    profile_ratify_inventory(str(repo), "v1", "x" * 200)


def test_refusal_message_never_echoes_the_actor(repo: Path) -> None:
    error = _refused(repo, "v1", "SECRETNAME")
    assert "SECRETNAME" not in error.message + repr(error.details)


def test_symlinked_inventory_dir_escaping_the_repo_is_refused(
    repo: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "v1.yaml").write_text(yaml.safe_dump(good()))
    (repo / ".beddel-profile").mkdir()
    (repo / ".beddel-profile" / "inventory").symlink_to(outside)
    with pytest.raises(ProfileError):
        profile_ratify_inventory(str(repo), "v1", "a")
    assert not (outside / "v1.ratification.yaml").exists()


# --- immutability against the index and history (Story 2.3 AC9) -------------


def test_record_only_in_the_index_refuses_ratification(repo: Path) -> None:
    from ._helpers import git

    write_version(repo, "v1", good())
    profile_ratify_inventory(str(repo), "v1", "a")
    git(repo, "add", str(_record(repo).relative_to(repo)))
    _record(repo).unlink()
    assert _refused(repo, "v1", "b").details == {"reason": "record.exists"}
    assert not _record(repo).exists()


def test_record_only_in_history_refuses_ratification(repo: Path) -> None:
    from ._helpers import commit_all, git

    write_version(repo, "v1", good())
    profile_ratify_inventory(str(repo), "v1", "a")
    commit_all(repo, "ratify")
    git(repo, "rm", "-q", str(_record(repo).relative_to(repo)))
    commit_all(repo, "drop the record")
    assert not _record(repo).exists()
    assert _refused(repo, "v1", "b").details == {"reason": "record.exists"}
    assert not _record(repo).exists()


def test_unborn_head_has_no_history_and_is_not_an_error(repo: Path) -> None:
    write_version(repo, "v1", good())
    profile_ratify_inventory(str(repo), "v1", "a")
    assert _record(repo).is_file()


def test_unrelated_history_does_not_refuse(repo: Path) -> None:
    from ._helpers import commit_all

    write_version(repo, "v1", good())
    commit_all(repo, "version only")
    profile_ratify_inventory(str(repo), "v1", "a")
    assert _record(repo).is_file()


def test_unreadable_history_refuses_with_its_own_reason(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from beddel_profile_dev._errors import PROFILE_REPOSITORY_INVALID

    def broken(*_: object) -> bool:
        raise ProfileError(PROFILE_REPOSITORY_INVALID, "x")

    write_version(repo, "v1", good())
    monkeypatch.setattr("beddel_profile_dev.tools.ratify.in_head_history", broken)
    assert _refused(repo, "v1", "a").details == {"reason": "history.unreadable"}
    assert not _record(repo).exists()
