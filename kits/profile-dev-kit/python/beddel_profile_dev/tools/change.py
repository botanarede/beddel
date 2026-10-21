"""Record of a Change and the link of its Analyzed revision (FR-1, AD-9).

A Change is identified by a maintainer-chosen ``change_id`` and its ``base``
commit, fixed by the first record. The Change never declares what it touches:
the footprint is computed from ``base`` and the Analyzed revision elsewhere.
Records are create-only and live in the work tree under the records directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from beddel.tools import beddel_tool

from beddel_profile_dev._errors import (
    PROFILE_CHANGE_CONFLICT,
    PROFILE_CHANGE_INVALID,
    ProfileError,
)
from beddel_profile_dev._io import (
    canonical_json,
    is_ancestor,
    read_confined,
    real_repo_root,
    resolve_revision,
    write_create_only,
)
from beddel_profile_dev.config import load_config
from beddel_profile_dev.inventory import is_valid_id

__all__ = ["profile_record_change"]

CHANGE_SCHEMA = "profile-dev/change/1"
CHANGE_REVISION_SCHEMA = "profile-dev/change-revision/1"


def _invalid() -> ProfileError:
    return ProfileError(
        PROFILE_CHANGE_INVALID,
        "change invalid: bad id, or base is not an ancestor of the revision",
    )


def _conflict() -> ProfileError:
    return ProfileError(
        PROFILE_CHANGE_CONFLICT,
        "the Change is already recorded with another base or another link",
    )


def _stored_matches(root: Path, relative: str, data: bytes) -> bool | None:
    """None if absent, else whether the stored bytes are identical."""
    stored = read_confined(root, relative)
    if stored is None:
        return None
    return stored == data


def _resolve_base(root: Path, base: str) -> str:
    """Resolve the ``base`` input; an unresolvable base is invalid input."""
    try:
        return resolve_revision(root, base)
    except ProfileError:
        raise _invalid() from None


@beddel_tool(
    name="profile_record_change",
    description="Record a Change (id and base) and the link of its Analyzed revision",
    category="profile",
)
def profile_record_change(
    repo_path: str, change_id: str, base: str, revision: str
) -> dict[str, Any]:
    """Record the Change and the link of its Analyzed revision, create-only.

    Raises:
        ProfileError: ``PROFILE_CHANGE_INVALID``, ``PROFILE_CHANGE_CONFLICT``
            or ``PROFILE_REPOSITORY_INVALID``.
    """
    config = load_config()
    if not is_valid_id(change_id):
        raise _invalid()
    root = real_repo_root(repo_path)
    base_sha = _resolve_base(root, base)
    sha = resolve_revision(root, revision)
    if not is_ancestor(root, base_sha, sha):
        raise _invalid()

    change_rel = f"{config.records_dir}/changes/{change_id}/change.json"
    link_rel = f"{config.records_dir}/changes/{change_id}/revisions/{sha}/revision.json"
    change = canonical_json(
        {"schema": CHANGE_SCHEMA, "change_id": change_id, "base": base_sha}
    )
    link = canonical_json(
        {
            "schema": CHANGE_REVISION_SCHEMA,
            "change_id": change_id,
            "base": base_sha,
            "revision": sha,
        }
    )
    if _stored_matches(root, change_rel, change) is False:
        raise _conflict()
    if _stored_matches(root, link_rel, link) is False:
        raise _conflict()
    for relative, data in ((change_rel, change), (link_rel, link)):
        if not write_create_only(root, relative, data) and (
            read_confined(root, relative) != data
        ):
            raise _conflict()
    return {
        "ok": True,
        "change_id": change_id,
        "base": base_sha,
        "revision": sha,
        "change": change_rel,
        "revision_link": link_rel,
    }
