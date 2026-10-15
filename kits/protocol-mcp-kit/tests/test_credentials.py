"""Tests for the owner-only credential store (Story 1.1, AC 5, 6, 9)."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import pytest
from beddel_protocol_mcp.credentials import (
    CREDENTIALS_DIR_ENV,
    CredentialStore,
    CredentialStoreError,
    StoredCredentials,
)
from mcp.shared.auth import OAuthToken
from mcp_fakes import MCP_URL, FakeServer, seed_credentials

KIT_ROOT = Path(__file__).resolve().parent.parent


class TestCredentialStore:
    def test_construction_performs_no_io_and_honours_the_environment(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        target = tmp_path / "from-env"
        monkeypatch.setenv(CREDENTIALS_DIR_ENV, str(target))
        store = CredentialStore()
        assert store.path_for(MCP_URL, "oauth").parent == target
        assert not target.exists()

    def test_read_of_a_missing_store_creates_nothing(
        self, creds_dir: Path, store: CredentialStore
    ):
        assert store.read(MCP_URL, "oauth") is None
        assert not creds_dir.exists()

    def test_write_creates_a_0700_directory_and_a_0600_file_under_a_permissive_umask(
        self, creds_dir: Path, store: CredentialStore
    ) -> None:
        previous = os.umask(0)
        try:
            store.write(MCP_URL, "oauth", StoredCredentials(tokens=OAuthToken(access_token="a")))
        finally:
            os.umask(previous)
        assert stat.S_IMODE(creds_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(store.path_for(MCP_URL, "oauth").stat().st_mode) == 0o600
        assert [p.name for p in creds_dir.iterdir()] == [store.path_for(MCP_URL, "oauth").name]

    def test_a_directory_open_to_other_users_is_refused(self, creds_dir: Path) -> None:
        creds_dir.mkdir()
        os.chmod(creds_dir, 0o755)
        with pytest.raises(CredentialStoreError):
            CredentialStore(creds_dir).read(MCP_URL, "oauth")

    def test_a_record_open_to_other_users_is_refused(
        self, fake: FakeServer, store: CredentialStore
    ):
        seed_credentials(fake, store)
        os.chmod(store.path_for(MCP_URL, "oauth"), 0o640)
        with pytest.raises(CredentialStoreError):
            store.read(MCP_URL, "oauth")

    def test_a_corrupt_record_fails_closed_without_echoing_its_content(
        self, fake: FakeServer, store: CredentialStore
    ) -> None:
        seed_credentials(fake, store)
        path = store.path_for(MCP_URL, "oauth")
        path.write_text('{"tokens": "corrupt-secret-content"')
        os.chmod(path, 0o600)
        with pytest.raises(CredentialStoreError) as caught:
            store.read(MCP_URL, "oauth")
        assert "corrupt-secret-content" not in str(caught.value)

    def test_a_symlinked_record_is_not_followed(
        self, fake: FakeServer, store: CredentialStore, tmp_path
    ):
        seed_credentials(fake, store)
        path = store.path_for(MCP_URL, "oauth")
        elsewhere = tmp_path / "elsewhere.json"
        path.rename(elsewhere)
        path.symlink_to(elsewhere)
        with pytest.raises(CredentialStoreError):
            store.read(MCP_URL, "oauth")

    def test_a_directory_inside_a_repository_is_refused_for_read_and_write(self) -> None:
        inside = CredentialStore(KIT_ROOT / "tests" / "_credentials_must_not_exist")
        with pytest.raises(CredentialStoreError):
            inside.write(MCP_URL, "oauth", StoredCredentials())
        with pytest.raises(CredentialStoreError):
            inside.read(MCP_URL, "oauth")
        assert not (KIT_ROOT / "tests" / "_credentials_must_not_exist").exists()

    def test_credentials_stay_out_of_reprs(self, fake: FakeServer, store: CredentialStore) -> None:
        response = seed_credentials(fake, store)
        stored = store.read(MCP_URL, "oauth")
        assert stored is not None
        assert response["access_token"] not in repr(stored)
        assert response["refresh_token"] not in repr(stored)

    def test_file_operations_go_through_the_checked_directory_descriptor(
        self, store: CredentialStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: list[tuple[Any, ...]] = []
        real_open, real_replace, real_fsync = os.open, os.replace, os.fsync

        def spy_open(path: Any, flags: int, mode: int = 0o777, *, dir_fd: int | None = None):
            events.append(("open", str(path), flags, mode, dir_fd))
            return real_open(path, flags, mode, dir_fd=dir_fd)

        def spy_replace(src: str, dst: str, *, src_dir_fd: int | None, dst_dir_fd: int | None):
            events.append(("replace", src, dst, src_dir_fd, dst_dir_fd))
            return real_replace(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)

        def spy_fsync(fd: int) -> None:
            kind = "fsync-dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "fsync-file"
            events.append((kind,))
            real_fsync(fd)

        monkeypatch.setattr(os, "open", spy_open)
        monkeypatch.setattr(os, "replace", spy_replace)
        monkeypatch.setattr(os, "fsync", spy_fsync)
        store.write(MCP_URL, "oauth", StoredCredentials(tokens=OAuthToken(access_token="a")))

        opens = [e for e in events if e[0] == "open"]
        directory_opens = [e for e in opens if e[4] is None]  # opened by path (twice if created)
        file_opens = [e for e in opens if e[4] is not None]
        assert directory_opens and len(file_opens) == 1
        for directory_open in directory_opens:
            assert directory_open[2] & os.O_DIRECTORY and directory_open[2] & os.O_NOFOLLOW
        file_open = file_opens[0]
        assert file_open[2] & os.O_NOFOLLOW and file_open[3] == 0o600
        assert "/" not in file_open[1]  # relative to the descriptor
        replace = next(e for e in events if e[0] == "replace")
        assert replace[3] is not None and replace[4] is not None
        assert "/" not in replace[1] and "/" not in replace[2]
        kinds = [e[0] for e in events if e[0] in {"fsync-file", "replace", "fsync-dir"}]
        assert kinds == ["fsync-file", "replace", "fsync-dir"]  # the rename is made durable

    def test_directory_swapped_for_a_symlink_after_resolution_is_not_followed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real = tmp_path / "real"
        real.mkdir(mode=0o700)
        link = tmp_path / "link"
        link.symlink_to(real)
        # Simulate the path being replaced by a symlink after it was resolved.
        monkeypatch.setattr(Path, "resolve", lambda self, strict=False: self)
        with pytest.raises(CredentialStoreError):
            CredentialStore(link).read(MCP_URL, "oauth")
        with pytest.raises(CredentialStoreError):
            CredentialStore(link).write(MCP_URL, "oauth", StoredCredentials())
        assert list(real.iterdir()) == []

    def test_no_temporary_file_survives_a_failed_write(
        self, creds_dir: Path, store: CredentialStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def broken_replace(*_a: Any, **_k: Any) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(os, "replace", broken_replace)
        with pytest.raises(CredentialStoreError) as caught:
            store.write(MCP_URL, "oauth", StoredCredentials(tokens=OAuthToken(access_token="a")))
        assert "disk full" not in str(caught.value)
        assert list(creds_dir.iterdir()) == []
