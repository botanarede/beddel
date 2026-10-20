"""AC4-AC7, AC10: binding precondition, integrity block, snapshot, confinement."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from beddel_profile_dev._errors import (
    PROFILE_INVENTORY_BINDING_CONFLICT,
    PROFILE_INVENTORY_INTEGRITY_BLOCK,
    PROFILE_INVENTORY_UNRATIFIED,
    PROFILE_REPOSITORY_INVALID,
    ProfileError,
)
from beddel_profile_dev.tools.bind import profile_bind_inventory
from beddel_profile_dev.tools.ratify import profile_ratify_inventory

from ._helpers import (
    INVENTORY_DIR,
    commit_all,
    git,
    good,
    init_repo,
    make_source,
    write_version,
)

RECORDS = ".beddel-profile/records/revisions"


def _ratified(
    tmp_path: Path, data: Any = None, version: str = "v1", *, contracts: bool = True
) -> tuple[Path, str]:
    repo = init_repo(tmp_path / "repo")
    make_source(repo, with_contracts=contracts)
    write_version(repo, version, good(version) if data is None else data)
    profile_ratify_inventory(str(repo), version, "tester")
    return repo, commit_all(repo)


def _fails(repo: Path, rev: str, version: str = "v1") -> ProfileError:
    with pytest.raises(ProfileError) as info:
        profile_bind_inventory(str(repo), rev, version)
    return info.value


def _tree(repo: Path) -> set[str]:
    return {
        str(p.relative_to(repo))
        for p in (repo / ".beddel-profile").rglob("*")
        if p.is_file() and "records" in p.parts
    }


def test_success_writes_binding_and_canonical_snapshot(tmp_path: Path) -> None:
    repo, sha = _ratified(tmp_path)
    result = profile_bind_inventory(str(repo), "HEAD", "v1")
    digest = hashlib.sha256((repo / INVENTORY_DIR / "v1.yaml").read_bytes()).hexdigest()
    snap_rel = f"{RECORDS}/{sha}/snapshot.json"
    assert result == {
        "ok": True,
        "revision": sha,
        "inventory_version": "v1",
        "inventory_sha256": digest,
        "snapshot": snap_rel,
        "obligations": 3,
        "targets_absent": 0,
    }
    raw = (repo / snap_rel).read_text()
    snap = json.loads(raw)
    assert (snap["revision"], snap["inventory_version"], snap["inventory_sha256"]) == (
        sha,
        "v1",
        digest,
    )
    keys = [
        (o["class"], o["affected_point"], o["criterion"]) for o in snap["obligations"]
    ]
    assert keys == sorted(keys)
    assert raw == json.dumps(snap, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    assert str(repo) not in raw
    binding = json.loads((repo / RECORDS / sha / "binding.json").read_text())
    assert (
        binding["snapshot"] == snap_rel and binding["schema"] == "profile-dev/binding/1"
    )


def test_revision_is_resolved_to_a_full_sha(tmp_path: Path) -> None:
    repo, sha = _ratified(tmp_path)
    git(repo, "tag", "t1")
    assert profile_bind_inventory(str(repo), "t1", "v1")["revision"] == sha


def test_unratified_when_record_absent(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    make_source(repo)
    write_version(repo, "v1", good())
    sha = commit_all(repo)
    assert _fails(repo, sha).code == PROFILE_INVENTORY_UNRATIFIED
    assert not (repo / ".beddel-profile" / "records").exists()


def test_unratified_when_version_absent(tmp_path: Path) -> None:
    repo, sha = _ratified(tmp_path)
    assert _fails(repo, sha, "v9").code == PROFILE_INVENTORY_UNRATIFIED
    assert _fails(repo, sha, "../x").code == PROFILE_INVENTORY_UNRATIFIED
    assert not (repo / ".beddel-profile" / "records").exists()


def test_unratified_when_hash_differs(tmp_path: Path) -> None:
    repo, _ = _ratified(tmp_path)
    changed = good()
    changed["criteria"][0]["description"] = "changed after ratification"
    write_version(repo, "v1", changed)
    sha = commit_all(repo)
    assert _fails(repo, sha).code == PROFILE_INVENTORY_UNRATIFIED
    assert not (repo / ".beddel-profile" / "records").exists()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(inventory_version="v2"),
        lambda r: r.update(schema="other"),
        lambda r: r.update(ratified_by=""),
        lambda r: r.update(extra=1),
        lambda r: r.pop("ratified_at"),
    ],
)
def test_unratified_when_record_malformed(tmp_path: Path, mutate: Any) -> None:
    repo, _ = _ratified(tmp_path)
    path = repo / INVENTORY_DIR / "v1.ratification.yaml"
    record = yaml.safe_load(path.read_text())
    mutate(record)
    path.write_text(yaml.safe_dump(record))
    sha = commit_all(repo)
    assert _fails(repo, sha).code == PROFILE_INVENTORY_UNRATIFIED


def test_unratified_when_record_only_in_the_work_tree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    make_source(repo)
    write_version(repo, "v1", good())
    sha = commit_all(repo)  # version committed, not ratified
    profile_ratify_inventory(str(repo), "v1", "tester")  # work tree only
    assert _fails(repo, sha).code == PROFILE_INVENTORY_UNRATIFIED


def test_work_tree_edits_do_not_affect_the_bound_revision(tmp_path: Path) -> None:
    repo, sha = _ratified(tmp_path)
    (repo / INVENTORY_DIR / "v1.yaml").write_text("garbage: [\n")
    assert profile_bind_inventory(str(repo), sha, "v1")["obligations"] == 3


def test_integrity_block_prevents_binding_and_records_every_failure(
    tmp_path: Path,
) -> None:
    data = good()
    data["obligations"][0]["class"] = "ghost"
    data["components"][0]["path"] = "../escape"
    repo, sha = _ratified(tmp_path, data)
    err = _fails(repo, sha)
    assert err.code == PROFILE_INVENTORY_INTEGRITY_BLOCK
    assert err.message == (
        "inventory integrity block: path.invalid, ref.class_unresolved"
    )
    files = _tree(repo)
    assert len(files) == 1
    block_path = repo / next(iter(files))
    assert block_path.parent.name == "integrity-blocks"
    block = json.loads(block_path.read_text())
    assert {(f["locator"], f["code"]) for f in block["failures"]} == {
        ("components[0].path", "path.invalid"),
        ("obligations[0].class", "ref.class_unresolved"),
    }
    assert not (repo / RECORDS / sha / "snapshot.json").exists()
    assert not (repo / RECORDS / sha / "binding.json").exists()


def test_unreadable_yaml_is_an_integrity_block(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    path = repo / INVENTORY_DIR / "v1.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("version: v1\nclasses: [\n")
    # The tool refuses to ratify unreadable YAML; a hand-made record is enough.
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (repo / INVENTORY_DIR / "v1.ratification.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "profile-dev/ratification/1",
                "inventory_version": "v1",
                "inventory_sha256": digest,
                "ratified_by": "tester",
                "ratified_at": "2026-01-01T00:00:00Z",
            }
        )
    )
    sha = commit_all(repo)
    err = _fails(repo, sha)
    assert err.code == PROFILE_INVENTORY_INTEGRITY_BLOCK
    assert "yaml.invalid" in err.message


def test_recorded_block_stops_without_revalidating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = good()
    data["obligations"][0]["class"] = "ghost"
    repo, sha = _ratified(tmp_path, data)
    first = _fails(repo, sha)
    from beddel_profile_dev.tools import bind

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("re-validated")

    monkeypatch.setattr(bind, "validate_inventory", boom)
    second = _fails(repo, sha)
    assert second.code == PROFILE_INVENTORY_INTEGRITY_BLOCK
    assert second.message == first.message
    assert len(_tree(repo)) == 1


def test_absent_target_does_not_prevent_binding(tmp_path: Path) -> None:
    repo, sha = _ratified(tmp_path, contracts=False)
    result = profile_bind_inventory(str(repo), sha, "v1")
    assert result["targets_absent"] == 1
    snap = json.loads((repo / result["snapshot"]).read_text())
    absent = [o for o in snap["obligations"] if not o["target_present"]]
    assert [o["affected_point"] for o in absent] == ["contracts"]
    assert not any((repo / RECORDS / sha / "integrity-blocks").glob("*"))


def test_rebinding_is_idempotent_and_byte_identical(tmp_path: Path) -> None:
    repo, sha = _ratified(tmp_path)
    first = profile_bind_inventory(str(repo), sha, "v1")
    before = {p: (repo / p).read_bytes() for p in _tree(repo)}
    assert profile_bind_inventory(str(repo), sha, "v1") == first
    assert {p: (repo / p).read_bytes() for p in _tree(repo)} == before


def test_tampered_snapshot_makes_rebinding_fail(tmp_path: Path) -> None:
    repo, sha = _ratified(tmp_path)
    result = profile_bind_inventory(str(repo), sha, "v1")
    (repo / result["snapshot"]).write_text("{}\n")
    assert _fails(repo, sha).code == PROFILE_INVENTORY_BINDING_CONFLICT


def test_another_version_for_a_bound_revision_conflicts(tmp_path: Path) -> None:
    repo, _ = _ratified(tmp_path)
    write_version(repo, "v2", good("v2"))
    profile_ratify_inventory(str(repo), "v2", "tester")
    sha = commit_all(repo)
    profile_bind_inventory(str(repo), sha, "v1")
    before = (repo / RECORDS / sha / "snapshot.json").read_bytes()
    assert _fails(repo, sha, "v2").code == PROFILE_INVENTORY_BINDING_CONFLICT
    assert (repo / RECORDS / sha / "snapshot.json").read_bytes() == before


def test_a_later_version_never_alters_an_existing_snapshot(tmp_path: Path) -> None:
    repo, sha1 = _ratified(tmp_path)
    profile_bind_inventory(str(repo), sha1, "v1")
    before = (repo / RECORDS / sha1 / "snapshot.json").read_bytes()
    write_version(repo, "v2", good("v2"))
    profile_ratify_inventory(str(repo), "v2", "tester")
    sha2 = commit_all(repo)
    profile_bind_inventory(str(repo), sha2, "v2")
    assert (repo / RECORDS / sha1 / "snapshot.json").read_bytes() == before


def test_successful_binding_discharges_blocks_of_other_versions(
    tmp_path: Path,
) -> None:
    bad = good()
    bad["obligations"][0]["class"] = "ghost"
    repo, _ = _ratified(tmp_path, bad)
    write_version(repo, "v2", good("v2"))
    profile_ratify_inventory(str(repo), "v2", "tester")
    sha = commit_all(repo)
    assert _fails(repo, sha, "v1").code == PROFILE_INVENTORY_INTEGRITY_BLOCK
    profile_bind_inventory(str(repo), sha, "v2")
    blocks = repo / RECORDS / sha / "integrity-blocks"
    discharges = list(blocks.glob("*.discharged.json"))
    assert len(discharges) == 1
    record = json.loads(discharges[0].read_text())
    assert record["resolved_by_version"] == "v2"
    # The block file survives its discharge; the revision is now bound to v2, so
    # asking for v1 again is a binding conflict.
    assert list(blocks.glob("*-*.json"))
    assert _fails(repo, sha, "v1").code == PROFILE_INVENTORY_BINDING_CONFLICT


def test_nul_in_revision_or_path_is_a_profile_error(tmp_path: Path) -> None:
    repo, _ = _ratified(tmp_path)
    assert _fails(repo, "HEAD\x00x").code == PROFILE_REPOSITORY_INVALID
    assert _fails(Path("a\x00b"), "HEAD").code == PROFILE_REPOSITORY_INVALID


def test_git_failure_on_presence_check_is_an_error_not_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, sha = _ratified(tmp_path)
    import beddel_profile_dev._io as io

    real = io._git

    def flaky(repo_dir: Path, *args: str) -> object:
        return None if args and args[0] == "ls-tree" else real(repo_dir, *args)

    monkeypatch.setattr(io, "_git", flaky)
    assert _fails(repo, sha).code == PROFILE_REPOSITORY_INVALID
    assert not (repo / RECORDS / sha / "snapshot.json").exists()
    assert not (repo / RECORDS / sha / "binding.json").exists()
    monkeypatch.undo()
    assert profile_bind_inventory(str(repo), sha, "v1")["targets_absent"] == 0


@pytest.mark.parametrize("field", ["ratified_at", "ratified_by"])
def test_ratification_record_fields_are_strict(tmp_path: Path, field: str) -> None:
    repo, _ = _ratified(tmp_path)
    path = repo / INVENTORY_DIR / "v1.ratification.yaml"
    record = yaml.safe_load(path.read_text())
    record[field] = "whenever" if field == "ratified_at" else "a\nb"
    path.write_text(yaml.safe_dump(record))
    assert _fails(repo, commit_all(repo)).code == PROFILE_INVENTORY_UNRATIFIED


def test_symlinked_profile_root_escaping_the_repo_is_refused(tmp_path: Path) -> None:
    repo, sha = _ratified(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / ".beddel-profile").rename(tmp_path / "moved")
    (repo / ".beddel-profile").symlink_to(outside)
    assert _fails(repo, sha).code == PROFILE_REPOSITORY_INVALID
    assert list(outside.iterdir()) == []


def test_rebinding_after_a_discharge_is_still_idempotent(tmp_path: Path) -> None:
    bad = good()
    bad["obligations"][0]["class"] = "ghost"
    repo, _ = _ratified(tmp_path, bad)
    write_version(repo, "v2", good("v2"))
    profile_ratify_inventory(str(repo), "v2", "tester")
    sha = commit_all(repo)
    assert _fails(repo, sha, "v1").code == PROFILE_INVENTORY_INTEGRITY_BLOCK
    first = profile_bind_inventory(str(repo), sha, "v2")
    assert profile_bind_inventory(str(repo), sha, "v2") == first


def test_invalid_revision_and_repository(tmp_path: Path) -> None:
    repo, _ = _ratified(tmp_path)
    for revision in ["nope", "--all", "", "HEAD:src"]:
        assert _fails(repo, revision).code == PROFILE_REPOSITORY_INVALID
    plain = tmp_path / "plain"
    plain.mkdir()
    assert _fails(plain, "HEAD").code == PROFILE_REPOSITORY_INVALID
    assert _fails(repo / "src", "HEAD").code == PROFILE_REPOSITORY_INVALID
    assert _fails(Path(""), "HEAD").code == PROFILE_REPOSITORY_INVALID


def test_symlinked_records_dir_escaping_the_repo_is_refused(tmp_path: Path) -> None:
    repo, sha = _ratified(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / ".beddel-profile" / "records").symlink_to(outside)
    assert _fails(repo, sha).code == PROFILE_REPOSITORY_INVALID
    assert list(outside.iterdir()) == []


def test_symlinked_revision_dir_escaping_the_repo_is_refused(tmp_path: Path) -> None:
    repo, sha = _ratified(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / RECORDS).mkdir(parents=True)
    (repo / RECORDS / sha).symlink_to(outside)
    assert _fails(repo, sha).code == PROFILE_REPOSITORY_INVALID
    assert list(outside.iterdir()) == []


def test_dangling_symlink_at_a_record_path_is_not_followed(tmp_path: Path) -> None:
    repo, sha = _ratified(tmp_path)
    outside = tmp_path / "outside"
    (repo / RECORDS / sha).mkdir(parents=True)
    (repo / RECORDS / sha / "snapshot.json").symlink_to(outside / "x.json")
    assert _fails(repo, sha).code in {
        PROFILE_INVENTORY_BINDING_CONFLICT,
        PROFILE_REPOSITORY_INVALID,
    }
    assert not outside.exists()


def test_inherited_git_env_cannot_redirect_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, sha = _ratified(tmp_path)
    other = init_repo(tmp_path / "other")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    assert profile_bind_inventory(str(repo), sha, "v1")["revision"] == sha


def test_pathspec_magic_in_a_component_path_is_literal(tmp_path: Path) -> None:
    data = good()
    data["components"][0]["path"] = ":/src/api.py"
    data["components"][1]["path"] = "src/*.py"
    repo, sha = _ratified(tmp_path, data)
    result = profile_bind_inventory(str(repo), sha, "v1")
    assert result["targets_absent"] == 3  # both paths are literal and absent


def test_sources_use_safe_load_only() -> None:
    root = Path(__file__).resolve().parent.parent / "python"
    for path in root.rglob("*.py"):
        text = path.read_text()
        assert "yaml.load(" not in text and "unsafe_load" not in text, path
        assert "shell=True" not in text and "os.system" not in text, path
