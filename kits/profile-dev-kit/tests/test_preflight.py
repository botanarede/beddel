"""AC3-AC5: preflight checks, fixed message, fail-closed config, no secret echo."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest
from beddel_profile_dev import config as cfg
from beddel_profile_dev._errors import (
    PROFILE_CONFIG_INVALID,
    PROFILE_PREFLIGHT_FAILED,
    ProfileError,
)
from beddel_profile_dev.tools.preflight import profile_preflight

MARKER = "SECRET-MARKER-9f3a71"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """PATH with fake gate executables plus the real git."""
    import shutil

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("pytest", "ruff", "mypy"):
        exe = bin_dir / name
        exe.write_text("#!/bin/sh\nexit 0\n")
        exe.chmod(0o755)
    git = shutil.which("git")
    assert git is not None
    (bin_dir / "git").symlink_to(
        git
    )  # only git, so a system ruff/pytest cannot leak in
    monkeypatch.setenv("PATH", str(bin_dir))
    return bin_dir


def _failed(exc: ProfileError) -> list[str]:
    return exc.details["failed"]


def test_success_returns_structured_result(repo: Path, fake_bin: Path) -> None:
    result = profile_preflight(str(repo))
    assert result["ok"] is True
    ids = [c["id"] for c in result["checks"]]
    assert ids == [
        "repo.exists",
        "repo.is_dir",
        "repo.git_work_tree",
        "executable.git",
        "executable.pytest",
        "executable.ruff",
        "executable.mypy",
    ]
    assert all(c["ok"] is True for c in result["checks"])


def test_non_repository_directory_fails_only_git_check(
    tmp_path: Path, fake_bin: Path
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(ProfileError) as info:
        profile_preflight(str(plain))
    assert info.value.code == PROFILE_PREFLIGHT_FAILED
    assert _failed(info.value) == ["repo.git_work_tree"]
    assert info.value.message == "profile preflight failed: repo.git_work_tree"


def test_missing_path_fails_all_repo_checks(tmp_path: Path, fake_bin: Path) -> None:
    with pytest.raises(ProfileError) as info:
        profile_preflight(str(tmp_path / "nope"))
    assert _failed(info.value) == ["repo.exists", "repo.is_dir", "repo.git_work_tree"]


def test_file_path_fails_is_dir(tmp_path: Path, fake_bin: Path) -> None:
    file_path = tmp_path / "f.txt"
    file_path.write_text("x")
    with pytest.raises(ProfileError) as info:
        profile_preflight(str(file_path))
    assert "repo.is_dir" in _failed(info.value)


def test_missing_executable_is_reported(repo: Path, fake_bin: Path) -> None:
    (fake_bin / "ruff").unlink()
    with pytest.raises(ProfileError) as info:
        profile_preflight(str(repo))
    assert _failed(info.value) == ["executable.ruff"]


def test_message_has_no_path_or_value(tmp_path: Path, fake_bin: Path) -> None:
    target = tmp_path / "very-distinct-dir-name"
    with pytest.raises(ProfileError) as info:
        profile_preflight(str(target))
    assert "very-distinct-dir-name" not in info.value.message
    assert str(tmp_path) not in info.value.message


def test_required_env_key_missing_and_empty(
    repo: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfg, "REQUIRED_ENV_KEYS", ("PROFILE_TEST_KEY",))
    monkeypatch.delenv("PROFILE_TEST_KEY", raising=False)
    with pytest.raises(ProfileError) as info:
        profile_preflight(str(repo))
    assert _failed(info.value) == ["env.PROFILE_TEST_KEY"]
    monkeypatch.setenv("PROFILE_TEST_KEY", "")
    with pytest.raises(ProfileError):
        profile_preflight(str(repo))


def test_required_env_key_present_passes(
    repo: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfg, "REQUIRED_ENV_KEYS", ("PROFILE_TEST_KEY",))
    monkeypatch.setenv("PROFILE_TEST_KEY", MARKER)
    result = profile_preflight(str(repo))
    assert {"id": "env.PROFILE_TEST_KEY", "ok": True} in result["checks"]


def test_secret_marker_never_echoed(
    repo: Path,
    tmp_path: Path,
    fake_bin: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        cfg, "REQUIRED_ENV_KEYS", ("PROFILE_TEST_KEY", "PROFILE_OTHER_KEY")
    )
    monkeypatch.setenv("PROFILE_TEST_KEY", MARKER)
    monkeypatch.delenv("PROFILE_OTHER_KEY", raising=False)
    caplog.set_level(logging.DEBUG)

    ok_result = None
    with pytest.raises(ProfileError) as info:  # fails on the other key
        profile_preflight(str(repo))
    monkeypatch.setenv("PROFILE_OTHER_KEY", "x")
    ok_result = profile_preflight(str(repo))

    exc = info.value
    chain = []
    cursor: BaseException | None = exc
    while cursor is not None:
        chain.append(str(cursor))
        cursor = cursor.__cause__ or cursor.__context__
    assert MARKER not in repr(ok_result)
    assert MARKER not in exc.message
    assert MARKER not in repr(exc.details)
    assert all(MARKER not in text for text in chain)
    assert MARKER not in caplog.text


def test_malformed_config_raises_and_never_degrades(
    repo: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfg, "GATE_EXECUTABLES", "git")  # not a list
    with pytest.raises(ProfileError) as info:
        profile_preflight(str(repo))
    assert info.value.code == PROFILE_CONFIG_INVALID


def test_missing_config_constant_raises(
    repo: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delattr(cfg, "REQUIRED_ENV_KEYS")
    with pytest.raises(ProfileError) as info:
        profile_preflight(str(repo))
    assert info.value.code == PROFILE_CONFIG_INVALID


_PATHS: dict[str, object] = {
    "inventory_dir": ".beddel-profile/inventory",
    "records_dir": ".beddel-profile/records",
}


@pytest.mark.parametrize(
    "raw",
    [
        {"gate_executables": ["git"], **_PATHS},  # missing key
        {
            "gate_executables": ["git"],
            "required_env_keys": [],
            "extra": [],
            **_PATHS,
        },  # unknown key
        {"gate_executables": "git", "required_env_keys": [], **_PATHS},  # not a list
        {"gate_executables": [1], "required_env_keys": [], **_PATHS},  # non-string
        {"gate_executables": ["git"], "required_env_keys": [""], **_PATHS},  # empty
        {"gate_executables": ["git"], "required_env_keys": []},  # paths missing
        {
            "gate_executables": ["git"],
            "required_env_keys": [],
            "inventory_dir": "/abs",
            "records_dir": "r",
        },
        {
            "gate_executables": ["git"],
            "required_env_keys": [],
            "inventory_dir": "a/../b",
            "records_dir": "r",
        },
        {
            "gate_executables": ["git"],
            "required_env_keys": [],
            "inventory_dir": "a\\b",
            "records_dir": "r",
        },
        {
            "gate_executables": ["git"],
            "required_env_keys": [],
            "inventory_dir": "a//b",
            "records_dir": "r",
        },
        {
            "gate_executables": ["git"],
            "required_env_keys": [],
            "inventory_dir": "a",
            "records_dir": 3,
        },
    ],
)
def test_validate_config_rejects_malformed(raw: dict[str, object]) -> None:
    with pytest.raises(ProfileError) as info:
        cfg.validate_config(raw)
    assert info.value.code == PROFILE_CONFIG_INVALID


def test_default_config_is_valid() -> None:
    loaded = cfg.load_config()
    assert loaded.gate_executables == ("git", "pytest", "ruff", "mypy")
    assert loaded.required_env_keys == ()
    assert loaded.inventory_dir == ".beddel-profile/inventory"
    assert loaded.records_dir == ".beddel-profile/records"


def test_kit_root_resolves_to_kit_directory() -> None:
    assert (cfg.get_kit_root() / "kit.yaml").is_file()


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_repo_path_fails_closed(
    blank: str, repo: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(repo)  # a blank path must NOT fall back to the cwd
    with pytest.raises(ProfileError) as info:
        profile_preflight(blank)
    assert _failed(info.value) == ["repo.exists", "repo.is_dir", "repo.git_work_tree"]


def test_inherited_git_dir_cannot_redirect_the_check(
    repo: Path, tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("GIT_DIR", str(repo / ".git"))
    with pytest.raises(ProfileError) as info:
        profile_preflight(str(plain))
    assert _failed(info.value) == ["repo.git_work_tree"]


def test_extra_public_constant_is_rejected_at_runtime(
    repo: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfg, "REVIEW_ENV_KEYS", ("X",), raising=False)
    with pytest.raises(ProfileError) as info:
        profile_preflight(str(repo))
    assert info.value.code == PROFILE_CONFIG_INVALID


def test_env_key_name_with_assignment_is_rejected() -> None:
    with pytest.raises(ProfileError):
        cfg.validate_config(
            {
                "gate_executables": ["git"],
                "required_env_keys": ["KEY=value"],
                **_PATHS,
            }
        )
