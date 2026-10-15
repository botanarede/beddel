"""Owner-only credential storage for remote MCP servers.

Credentials (OAuth tokens and the registered client information) are persisted
outside the repository, one file per ``(canonical endpoint, authorization
method)`` pair.  They are **never** looked up by the server key a workflow uses,
so a token stored for one endpoint can never be presented to another, and
renaming a server in a workflow neither strands nor shares credentials.

Layout and guarantees
---------------------
* Directory: ``$BEDDEL_MCP_CREDENTIALS_DIR`` or ``~/.beddel/mcp-credentials``,
  created with mode ``0700``.  A directory inside a git work tree that holds the
  current working directory or this kit is refused, and so is a directory that
  is group- or world-accessible.
* File name: SHA-256 of the endpoint and method (the endpoint text is not put in
  a path).  The record repeats both and the reader checks them, so a file moved
  to another name is not honoured.
* Writes create a temporary file with ``os.open(..., 0o600)`` -- the mode is
  owner-only from the first byte, never tightened afterwards -- and atomically
  replace the destination.  The directory is opened with
  ``O_DIRECTORY | O_NOFOLLOW`` and checked with ``fstat``; the file is created,
  replaced and read relative to that descriptor (``dir_fd``), so swapping a
  parent directory after the check cannot redirect it.  The directory is
  fsynced after the replace so the rename survives a crash.
* Reads refuse a file that is not a regular file owned by the current user with
  no group or world permission bits.
* The authorization server (``issuer``) is recorded inside the client
  information by the SDK.  When a different client registration replaces it, the
  tokens issued under the previous one are discarded in the same write.

Nothing here ever logs, prints or puts a token, secret or file content in an
exception message; failures carry fixed reasons only.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import secrets
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp.client.auth import TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

__all__ = [
    "CREDENTIALS_DIR_ENV",
    "CredentialStore",
    "CredentialStoreError",
    "FileTokenStorage",
    "StoredCredentials",
]

CREDENTIALS_DIR_ENV = "BEDDEL_MCP_CREDENTIALS_DIR"
_DEFAULT_DIRECTORY = Path("~/.beddel/mcp-credentials")
_RECORD_VERSION = 1
_MAX_RECORD_BYTES = 256 * 1024
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class CredentialStoreError(Exception):
    """The credential store cannot be used safely.

    ``reason`` is a fixed, secret-free sentence.  The class deliberately has no
    ``details`` and never wraps the underlying ``OSError`` text.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class StoredCredentials:
    """What is persisted for one ``(endpoint, authorization)`` pair.

    The fields hold secrets, so they are excluded from ``repr``.
    """

    tokens: OAuthToken | None = field(default=None, repr=False)
    expires_at: float | None = field(default=None, repr=False)
    client_info: OAuthClientInformationFull | None = field(default=None, repr=False)
    # Authorization-server metadata discovered during the operator flow.  The SDK
    # keeps it in memory only, and without it a fresh process would send a
    # refresh request to a guessed ``/token`` path instead of the real token
    # endpoint.  It holds no secret.
    oauth_metadata: dict[str, Any] | None = field(default=None, repr=False)
    auth_server_url: str | None = field(default=None, repr=False)


def _git_root(start: Path) -> Path | None:
    """Return the nearest ancestor of *start* holding a ``.git`` entry."""
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _repository_roots() -> list[Path]:
    """Work-tree roots the credential directory must stay out of."""
    roots: list[Path] = []
    for start in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        root = _git_root(start)
        if root is not None and root not in roots:
            roots.append(root)
    return roots


class CredentialStore:
    """Filesystem store of per-endpoint OAuth credentials.

    Constructing a store performs no I/O: the directory is resolved, validated
    and created only on first read or write.

    Args:
        directory: Credential directory.  Defaults to
            ``$BEDDEL_MCP_CREDENTIALS_DIR`` or ``~/.beddel/mcp-credentials``.
    """

    def __init__(self, directory: str | os.PathLike[str] | None = None) -> None:
        if directory is None:
            directory = os.environ.get(CREDENTIALS_DIR_ENV) or _DEFAULT_DIRECTORY
        self._directory = Path(directory).expanduser()

    @staticmethod
    def key_digest(endpoint: str, authorization: str) -> str:
        """Return the file-name digest for an ``(endpoint, authorization)`` pair."""
        return hashlib.sha256(f"{endpoint}\n{authorization}".encode()).hexdigest()

    def path_for(self, endpoint: str, authorization: str) -> Path:
        """Return the record path for a pair (no I/O)."""
        return self._directory / f"{self.key_digest(endpoint, authorization)}.json"

    # -- directory ------------------------------------------------------

    def _open_directory(self, *, create: bool) -> int | None:
        """Open the credential directory and return a checked file descriptor.

        The directory is opened with ``O_DIRECTORY | O_NOFOLLOW`` and then
        verified with ``fstat`` (owned by the current user, no group or other
        permission bits); every later file operation goes through that
        descriptor (``dir_fd``), so replacing a parent directory or the path
        after the check cannot redirect them.  The caller closes the descriptor.

        Returns:
            The descriptor, or ``None`` when the directory does not exist and
            *create* is false.

        Raises:
            CredentialStoreError: The platform, the location or the directory
                is not acceptable.  Raised outside any ``except`` block so no
                ``OSError`` text is chained to it.
        """
        if os.name != "posix":
            raise CredentialStoreError(
                "owner-only credential storage is not supported on this platform"
            )
        directory = self._directory.resolve()
        for root in _repository_roots():
            if directory == root or root in directory.parents:
                raise CredentialStoreError(
                    f"credential directory is inside a repository; set {CREDENTIALS_DIR_ENV} "
                    "to a directory outside it"
                )
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | _NOFOLLOW
        failure: str | None = None
        absent = False
        fd = -1
        try:
            fd = os.open(directory, flags)
        except FileNotFoundError:
            absent = True
        except OSError:
            failure = "credential directory cannot be opened"
        if failure is not None:
            raise CredentialStoreError(failure)
        if absent:
            if not create:
                return None
            try:
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                fd = os.open(directory, flags)
            except OSError:
                failure = "credential directory cannot be created"
            if failure is not None:
                raise CredentialStoreError(failure)
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            failure = "credential directory is not owned by the current user"
        elif info.st_mode & 0o077:
            failure = "credential directory is accessible to other users"
        if failure is not None:
            os.close(fd)
            raise CredentialStoreError(failure)
        return fd

    # -- read -----------------------------------------------------------

    def read(self, endpoint: str, authorization: str) -> StoredCredentials | None:
        """Load the record for a pair.

        Returns:
            The stored credentials, or ``None`` when nothing is stored.

        Raises:
            CredentialStoreError: The store or the record is unusable (wrong
                permissions or owner, corrupt, bound to another endpoint).
        """
        dir_fd = self._open_directory(create=False)
        if dir_fd is None:
            return None
        name = f"{self.key_digest(endpoint, authorization)}.json"
        failure: str | None = None
        raw = b""
        try:
            fd = -1
            try:
                fd = os.open(name, os.O_RDONLY | _NOFOLLOW, dir_fd=dir_fd)
            except FileNotFoundError:
                return None
            except OSError:
                failure = "credential record cannot be opened"
            if failure is None:
                try:
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                        failure = "credential record is not a regular owned file"
                    elif info.st_mode & 0o077:
                        failure = "credential record is accessible to other users"
                    elif info.st_size > _MAX_RECORD_BYTES:
                        failure = "credential record is too large"
                    else:
                        with os.fdopen(fd, "rb", closefd=False) as handle:
                            raw = handle.read(_MAX_RECORD_BYTES + 1)
                finally:
                    os.close(fd)
        finally:
            os.close(dir_fd)
        if failure is not None:
            raise CredentialStoreError(failure)
        record: StoredCredentials | None = None
        try:
            record = self._parse(raw, endpoint, authorization)
        except CredentialStoreError:
            raise
        except Exception:
            # Corrupt content must never surface its own text.
            failure = "credential record is corrupt"
        if failure is not None:
            raise CredentialStoreError(failure)
        return record

    @staticmethod
    def _parse(raw: bytes, endpoint: str, authorization: str) -> StoredCredentials:
        data = json.loads(raw)
        if (
            data["version"] != _RECORD_VERSION
            or data["endpoint"] != endpoint
            or data["authorization"] != authorization
        ):
            raise CredentialStoreError("credential record is bound to another endpoint")
        tokens = data.get("tokens")
        client_info = data.get("client_info")
        expires_at = data.get("expires_at")
        return StoredCredentials(
            tokens=OAuthToken.model_validate(tokens) if tokens else None,
            expires_at=float(expires_at) if expires_at is not None else None,
            client_info=(
                OAuthClientInformationFull.model_validate(client_info) if client_info else None
            ),
            oauth_metadata=data.get("oauth_metadata") or None,
            auth_server_url=data.get("auth_server_url") or None,
        )

    # -- write ----------------------------------------------------------

    def write(self, endpoint: str, authorization: str, credentials: StoredCredentials) -> None:
        """Atomically persist *credentials* with owner-only permissions."""
        dir_fd = self._open_directory(create=True)
        assert dir_fd is not None  # create=True always yields a descriptor
        final = f"{self.key_digest(endpoint, authorization)}.json"
        temporary = f".{final}.{secrets.token_hex(8)}.tmp"
        payload: dict[str, Any] = {
            "version": _RECORD_VERSION,
            "endpoint": endpoint,
            "authorization": authorization,
            "tokens": (
                credentials.tokens.model_dump(mode="json", exclude_none=True)
                if credentials.tokens
                else None
            ),
            "expires_at": credentials.expires_at,
            "client_info": (
                credentials.client_info.model_dump(mode="json", exclude_none=True)
                if credentials.client_info
                else None
            ),
            "oauth_metadata": credentials.oauth_metadata,
            "auth_server_url": credentials.auth_server_url,
        }
        failed = False
        try:
            try:
                # 0o600 from creation: the file is never readable by anyone else,
                # not even between creation and a later chmod.  Name and
                # replacement are relative to the verified directory descriptor.
                fd = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW,
                    0o600,
                    dir_fd=dir_fd,
                )
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        json.dump(payload, handle)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, final, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
                except BaseException:
                    with contextlib.suppress(OSError):
                        os.unlink(temporary, dir_fd=dir_fd)
                    raise
                # Make the rename itself durable (best effort: not every
                # filesystem accepts fsync on a directory descriptor).
                with contextlib.suppress(OSError):
                    os.fsync(dir_fd)
            except OSError:
                failed = True
        finally:
            os.close(dir_fd)
        if failed:
            raise CredentialStoreError("credential record cannot be written")


class FileTokenStorage(TokenStorage):
    """SDK ``TokenStorage`` backed by a :class:`CredentialStore`.

    Bound to one ``(endpoint, authorization)`` pair at construction; it cannot
    read or write any other pair.  Reads are strict: a record that cannot be
    trusted raises :class:`CredentialStoreError` instead of being served.
    Writes replace an untrustworthy record rather than merging into it.
    """

    def __init__(
        self,
        store: CredentialStore,
        endpoint: str,
        authorization: str,
    ) -> None:
        self._store = store
        self._endpoint = endpoint
        self._authorization = authorization

    def _read(self) -> StoredCredentials:
        return self._store.read(self._endpoint, self._authorization) or StoredCredentials()

    def _load(self) -> StoredCredentials:
        try:
            return self._read()
        except CredentialStoreError:
            # A record that cannot be trusted is replaced, never merged.
            return StoredCredentials()

    async def get_tokens(self) -> OAuthToken | None:
        """Return the stored tokens, or ``None``."""
        return self._read().tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Persist *tokens* and the absolute expiry they imply."""
        current = self._load()
        current.tokens = tokens
        current.expires_at = (
            time.time() + tokens.expires_in if tokens.expires_in is not None else None
        )
        self._store.write(self._endpoint, self._authorization, current)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Return the stored client registration, or ``None``."""
        return self._read().client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Persist the client registration.

        Replacing a registration by a different one (another client id or
        another issuer) discards the tokens issued under the previous one.
        """
        current = self._load()
        previous = current.client_info
        if previous is not None and (
            previous.client_id != client_info.client_id or previous.issuer != client_info.issuer
        ):
            current.tokens = None
            current.expires_at = None
            current.oauth_metadata = None
            current.auth_server_url = None
        current.client_info = client_info
        self._store.write(self._endpoint, self._authorization, current)
