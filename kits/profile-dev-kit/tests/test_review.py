"""AC1-AC9, AC12: the external Review records an operational outcome only.

The review route is never reached: every test replaces the single adapter seam
(``beddel_profile_dev._adapters.get_review_adapter``) with a fake, or stops
before the route is touched.
"""

from __future__ import annotations

import json
import subprocess
import sys
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from beddel.domain.errors import AgentError
from beddel.error_codes import AGENT_EXECUTION_FAILED, AGENT_TIMEOUT
from beddel_profile_dev import _adapters
from beddel_profile_dev import config as cfg
from beddel_profile_dev._errors import (
    PROFILE_CHANGE_INVALID,
    PROFILE_CONFIG_INVALID,
    PROFILE_REPOSITORY_INVALID,
    PROFILE_REVIEW_UNSCOPED,
    ProfileError,
)
from beddel_profile_dev._io import (
    _BINARY_SIZE,
    _Change,
    _render_change,
    canonical_json,
    resolve_revision,
)
from beddel_profile_dev.tools import review as review_module
from beddel_profile_dev.tools.bind import profile_bind_inventory
from beddel_profile_dev.tools.change import profile_record_change
from beddel_profile_dev.tools.impact import profile_derive_impact
from beddel_profile_dev.tools.review import REVIEW_SCHEMA, profile_run_review

from ._helpers import FakeReviewAdapter, change_fixture, git, install_fake_review

RECORDS = ".beddel-profile/records"
RESULT_KEYS = {
    "ok",
    "change_id",
    "revision",
    "review",
    "review_ref",
    "attempt",
    "status",
    "agent",
    "model",
}
OUTCOME_KEYS = {
    "schema",
    "change_id",
    "revision",
    "inventory_version",
    "inventory_sha256",
    "agent",
    "model",
    "status",
    "review_ref",
}
FORBIDDEN = ("verdict", "evidence", "finding", "pendency", "passed", "satisfied")
KIT_ROOT = Path(__file__).resolve().parent.parent


def _touch_api(repo: Path) -> None:
    (repo / "src" / "api.py").write_text("x = 2\n")


def _prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    impact: bool = True,
    adapter: FakeReviewAdapter | None = None,
    mutate: Callable[[Path], None] = _touch_api,
) -> tuple[Path, str, FakeReviewAdapter, list[tuple[str, int]]]:
    """A ratified repo with a Change, its impact record and a faked route."""
    monkeypatch.delenv("KIRO_API_KEY", raising=False)
    repo, base, rev = change_fixture(tmp_path, mutate)
    fake, factory_calls = install_fake_review(monkeypatch, adapter)
    if impact:
        profile_record_change(str(repo), "c1", base, rev)
        profile_bind_inventory(str(repo), rev, "v1")
        profile_derive_impact(str(repo), "c1", rev)
    return repo, rev, fake, factory_calls


def _revision_dir(repo: Path, rev: str, change: str = "c1") -> Path:
    return repo / RECORDS / "changes" / change / "revisions" / rev


def _review(repo: Path, rev: str) -> dict[str, Any]:
    data = json.loads((_revision_dir(repo, rev) / "review.json").read_text())
    assert isinstance(data, dict)
    return data


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _nothing_written(repo: Path, rev: str) -> None:
    assert not (_revision_dir(repo, rev) / "review.json").exists()
    assert not (_revision_dir(repo, rev) / "review-output").exists()


async def _refused(repo: Path, rev: str, change: str = "c1") -> ProfileError:
    with pytest.raises(ProfileError) as info:
        await profile_run_review(str(repo), change, rev)
    return info.value


# --- AC 3, 5: what the record is ----------------------------------------------


async def test_a_completed_review_is_an_operational_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    impact = json.loads((_revision_dir(repo, rev) / "impact.json").read_text())
    result = await profile_run_review(str(repo), "c1", rev)
    ref = f"{RECORDS}/changes/c1/revisions/{rev}/review-output/1.txt"
    assert set(result) == RESULT_KEYS
    assert result == {
        "ok": True,
        "change_id": "c1",
        "revision": rev,
        "review": f"{RECORDS}/changes/c1/revisions/{rev}/review.json",
        "review_ref": ref,
        "attempt": 1,
        "status": "completed",
        "agent": "kiro",
        "model": "claude-opus-4.5",
    }
    review = _review(repo, rev)
    assert set(review) == OUTCOME_KEYS  # no error_code on a completed review
    assert review == {
        "schema": REVIEW_SCHEMA,
        "change_id": "c1",
        "revision": rev,
        "inventory_version": impact["inventory_version"],
        "inventory_sha256": impact["inventory_sha256"],
        "agent": cfg.REVIEW_AGENT,
        "model": cfg.REVIEW_MODEL,
        "status": "completed",
        "review_ref": ref,
    }
    assert REVIEW_SCHEMA == "profile-dev/review-outcome/1"
    assert (repo / ref).read_text() == "canned review\n"
    assert len(fake.calls) == 1


async def test_the_record_is_canonical_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, _, _ = _prepare(tmp_path, monkeypatch)
    await profile_run_review(str(repo), "c1", rev)
    raw = (_revision_dir(repo, rev) / "review.json").read_bytes()
    assert raw == canonical_json(json.loads(raw))


@pytest.mark.parametrize("behavior", ["completed", "timeout", "error", "os_error"])
async def test_the_outcome_carries_no_judgement_vocabulary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, behavior: str
) -> None:
    repo, rev, _, _ = _prepare(
        tmp_path, monkeypatch, adapter=FakeReviewAdapter(behavior)
    )
    result = await profile_run_review(str(repo), "c1", rev)
    review = _review(repo, rev)
    assert review["status"] in {"completed", "timed_out", "errored"}
    for record in (review, result):
        for key in record:
            assert not any(word in key for word in FORBIDDEN), key
        for value in record.values():
            if isinstance(value, str):
                assert not any(word in value.lower() for word in FORBIDDEN), value


async def test_the_reviewer_text_is_stored_verbatim_and_never_interpreted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = 'VERDICT: PASS\n{"status": "errored"}\n\u00e9\n'
    repo, rev, _, _ = _prepare(
        tmp_path, monkeypatch, adapter=FakeReviewAdapter(output=text)
    )
    await profile_run_review(str(repo), "c1", rev)
    out = _revision_dir(repo, rev) / "review-output" / "1.txt"
    assert out.read_bytes() == text.encode("utf-8")
    assert _review(repo, rev)["status"] == "completed"  # the text decides nothing


async def test_undecodable_text_is_replaced_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, _, _ = _prepare(
        tmp_path, monkeypatch, adapter=FakeReviewAdapter(output="a\udc80b")
    )
    await profile_run_review(str(repo), "c1", rev)
    out = _revision_dir(repo, rev) / "review-output" / "1.txt"
    assert out.read_bytes() == b"a?b"


async def test_a_review_never_rewrites_an_earlier_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, _, _ = _prepare(tmp_path, monkeypatch)
    before = _tree(repo / RECORDS)
    await profile_run_review(str(repo), "c1", rev)
    await profile_run_review(str(repo), "c1", rev)
    after = _tree(repo / RECORDS)
    prefix = f"changes/c1/revisions/{rev}/review"
    for name, data in before.items():
        assert after[name] == data, name  # impact, change, binding: byte-identical
    assert all(n.startswith(prefix) for n in after if n not in before)


# --- AC 2, 2a: the route, read-only, SSO, model from config -------------------


async def test_the_route_is_called_read_only_with_the_configured_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, factory_calls = _prepare(tmp_path, monkeypatch)
    await profile_run_review(str(repo), "c1", rev)
    assert factory_calls == [(cfg.REVIEW_AGENT, cfg.REVIEW_TIMEOUT_SECONDS)]
    (call,) = fake.calls
    assert call["sandbox"] == "read-only"
    assert call["model"] == cfg.REVIEW_MODEL == "claude-opus-4.5"
    assert call["tools"] is None
    assert call["output_schema"] is None
    assert call["api_key_in_env"] is False


async def test_the_model_agent_and_budget_come_from_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, factory_calls = _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(cfg, "REVIEW_MODEL", "other-model-1")
    monkeypatch.setattr(cfg, "REVIEW_TIMEOUT_SECONDS", 77)
    await profile_run_review(str(repo), "c1", rev)
    assert fake.calls[0]["model"] == "other-model-1"
    assert factory_calls == [("kiro", 77)]
    assert _review(repo, rev)["model"] == "other-model-1"


@pytest.mark.parametrize("value", ["sk-secret", ""])
async def test_an_ambient_api_key_is_refused_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    repo, rev, fake, factory_calls = _prepare(tmp_path, monkeypatch)
    monkeypatch.setenv("KIRO_API_KEY", value)
    error = await _refused(repo, rev)
    assert error.code == PROFILE_REVIEW_UNSCOPED
    assert "sk-secret" not in str(error) and "sk-secret" not in repr(error.details)
    assert fake.calls == [] and factory_calls == []
    _nothing_written(repo, rev)


async def test_an_unknown_review_agent_is_refused_through_the_real_resolver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, _, _ = _prepare(tmp_path, monkeypatch)
    monkeypatch.undo()  # drop the fake seam: the real resolver must refuse
    monkeypatch.delenv("KIRO_API_KEY", raising=False)
    monkeypatch.setattr(cfg, "REVIEW_AGENT", "nonexistent")
    error = await _refused(repo, rev)
    assert error.code == PROFILE_REVIEW_UNSCOPED
    _nothing_written(repo, rev)


def test_the_resolver_map_is_static_and_knows_only_the_kiro_route() -> None:
    assert _adapters.REVIEW_ADAPTERS == {
        "kiro": ("beddel_agent_kiro", "KiroCLIAgentAdapter")
    }
    with pytest.raises(ProfileError) as info:
        _adapters.get_review_adapter("codex", timeout_seconds=5)
    assert info.value.code == PROFILE_REVIEW_UNSCOPED


def test_the_resolver_hands_the_binary_over_and_passes_no_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    class _Adapter:
        def __init__(self, **kwargs: Any) -> None:
            seen.update(kwargs)

    cli = tmp_path / "kiro-cli"
    monkeypatch.setitem(
        sys.modules,
        "beddel_agent_kiro",
        types.SimpleNamespace(KiroCLIAgentAdapter=_Adapter),
    )
    monkeypatch.setattr(_adapters, "_locate_cli", lambda: cli)
    adapter = _adapters.get_review_adapter("kiro", timeout_seconds=42)
    assert isinstance(adapter, _Adapter)
    assert seen == {"cli_path": cli, "timeout": 42}  # no api_key, no model


def test_a_missing_binary_is_never_installed_and_is_an_agent_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _NeverBuilt:
        def __init__(self, **kwargs: Any) -> None:
            raise AssertionError("the adapter must not be built without a binary")

    monkeypatch.setitem(
        sys.modules,
        "beddel_agent_kiro",
        types.SimpleNamespace(KiroCLIAgentAdapter=_NeverBuilt),
    )
    monkeypatch.setattr(_adapters, "_locate_cli", lambda: None)
    with pytest.raises(AgentError) as info:
        _adapters.get_review_adapter("kiro", timeout_seconds=5)
    assert info.value.code == AGENT_EXECUTION_FAILED


def test_an_adapter_module_that_cannot_be_imported_is_an_agent_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "beddel_agent_kiro", None)  # import fails
    with pytest.raises(AgentError) as info:
        _adapters.get_review_adapter("kiro", timeout_seconds=5)
    assert info.value.code == AGENT_EXECUTION_FAILED


def test_the_binary_is_located_without_installing_or_touching_a_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(bin_dir))
    assert _adapters._locate_cli() is None  # absent: nothing is installed
    assert list(home.iterdir()) == [] and list(bin_dir.iterdir()) == []
    binary = bin_dir / "kiro-cli"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    assert _adapters._locate_cli() == binary
    default = home / ".local" / "bin" / "kiro-cli"
    default.parent.mkdir(parents=True)
    default.write_text("#!/bin/sh\n")
    default.chmod(0o755)
    assert _adapters._locate_cli() == default  # the default location wins
    assert not (home / ".local" / "share").exists()


async def test_a_route_that_cannot_be_loaded_is_recorded_as_errored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, _, _ = _prepare(tmp_path, monkeypatch)
    monkeypatch.undo()
    monkeypatch.delenv("KIRO_API_KEY", raising=False)
    monkeypatch.setitem(sys.modules, "beddel_agent_kiro", None)
    result = await profile_run_review(str(repo), "c1", rev)
    assert result["status"] == "errored"
    assert _review(repo, rev)["error_code"] == AGENT_EXECUTION_FAILED


# --- AC 1, 6: scope comes from impact.json only --------------------------------


async def test_the_prompt_carries_the_derived_set_and_the_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    impact = json.loads((_revision_dir(repo, rev) / "impact.json").read_text())
    await profile_run_review(str(repo), "c1", rev)
    prompt = fake.calls[0]["prompt"]
    assert impact["base"] in prompt and rev in prompt
    assert impact["inventory_version"] in prompt
    assert impact["inventory_sha256"] in prompt
    assert json.dumps(impact["footprint"], indent=2) in prompt
    assert json.dumps(impact["affected_points"], sort_keys=True, indent=2) in prompt
    assert json.dumps(impact["required_evidence"], sort_keys=True, indent=2) in prompt
    assert "-x = 1" in prompt and "+x = 2" in prompt  # the base..revision diff
    assert "read-only" in prompt


async def test_scope_is_read_from_impact_json_and_never_re_derived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    path = _revision_dir(repo, rev) / "impact.json"
    impact = json.loads(path.read_text())
    impact["inventory_version"] = "v9"
    impact["inventory_sha256"] = "ab" * 32
    impact["footprint"] = ["not/derived/here.py"]
    impact["affected_points"] = [{"id": "recorded-only-point"}]
    impact["required_evidence"] = [{"obligation": "recorded-only-evidence"}]
    path.write_text(json.dumps(impact))
    await profile_run_review(str(repo), "c1", rev)
    prompt = fake.calls[0]["prompt"]
    for marker in (
        "not/derived/here.py",
        "recorded-only-point",
        "recorded-only-evidence",
    ):
        assert marker in prompt
    review = _review(repo, rev)
    assert review["inventory_version"] == "v9"
    assert review["inventory_sha256"] == "ab" * 32


async def test_the_scope_handed_over_is_byte_identical_across_runs_and_work_trees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    await profile_run_review(str(repo), "c1", rev)
    (repo / "src" / "api.py").write_text("x = 3  # edited after the revision\n")
    (repo / "src" / "untracked.py").write_text("y = 1\n")
    await profile_run_review(str(repo), "c1", rev)
    assert fake.calls[0]["prompt"] == fake.calls[1]["prompt"]
    assert "edited after the revision" not in fake.calls[1]["prompt"]


async def test_git_configuration_never_changes_the_diff_handed_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    await profile_run_review(str(repo), "c1", rev)
    for key, value in (
        ("diff.noprefix", "true"),
        ("diff.mnemonicPrefix", "true"),
        ("diff.context", "0"),
        ("diff.algorithm", "patience"),
        ("diff.renames", "copies"),
        ("diff.external", "false"),
        ("diff.orderFile", str(tmp_path / "no-such-order-file")),
        ("core.quotePath", "false"),
    ):
        git(repo, "config", key, value)
    await profile_run_review(str(repo), "c1", rev)
    assert fake.calls[0]["prompt"] == fake.calls[1]["prompt"]
    assert "diff --git a/src/api.py b/src/api.py" in fake.calls[1]["prompt"]


def _commit_gitattributes_minus_diff(repo: Path) -> None:
    """mutate: write api.py change AND commit a -diff .gitattributes in the same revision."""
    (repo / "src" / "api.py").write_text("x = 2\n")
    (repo / ".gitattributes").write_text("src/api.py -diff\n")


def _commit_gitattributes_diff_driver(repo: Path) -> None:
    """mutate: write api.py change AND commit a diff=custom .gitattributes in the revision."""
    (repo / "src" / "api.py").write_text("x = 2\n")
    (repo / ".gitattributes").write_text("src/api.py diff=custom\n")


async def test_attributes_and_big_file_settings_never_change_the_diff_handed_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # R5 FIX: .gitattributes is COMMITTED IN THE REVISION via mutate so that
    # `git diff <rev>~1 <rev>` reads the attribute from the committed tree and
    # the guard actually bites (R4 defect: writing it to the work tree after the
    # revision commit means porcelain with --attr-source=<rev> ignores it).
    repo, rev, fake, _ = _prepare(
        tmp_path, monkeypatch, mutate=_commit_gitattributes_minus_diff
    )
    await profile_run_review(str(repo), "c1", rev)
    # A user-level attributes file and a tiny big-file threshold also bend porcelain.
    user_attributes = tmp_path / "xdg" / "git" / "attributes"
    user_attributes.parent.mkdir(parents=True)
    user_attributes.write_text("*.py -diff\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    git(repo, "config", "core.attributesFile", str(user_attributes))
    git(repo, "config", "core.bigFileThreshold", "1")
    # Guard: the committed -diff attribute DOES change porcelain `git diff <rev>~1 <rev>`.
    raw = git(repo, "diff", f"{rev}~1", rev)
    assert "Binary files" in raw and "+x = 2" not in raw
    # The kit diff is unaffected: still shows the textual change.
    await profile_run_review(str(repo), "c1", rev)
    assert fake.calls[0]["prompt"] == fake.calls[1]["prompt"]
    assert "+x = 2" in fake.calls[1]["prompt"]
    assert "diff --git a/src/api.py b/src/api.py" in fake.calls[1]["prompt"]


async def test_a_repo_local_diff_driver_never_hides_the_diff_handed_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A diff.<driver>.binary attribute, committed in the revision AND wired via
    a repo-local diff.custom.binary config, must never turn the hunk binary in
    the kit diff. The guard verifies it bends porcelain first."""
    # R5 FIX: .gitattributes with diff=custom is COMMITTED IN THE REVISION so
    # that `git diff <rev>~1 <rev>` (reading attrs from the committed tree) is
    # bent by the guard; repo-local config is set after commit.
    repo, rev, fake, _ = _prepare(
        tmp_path, monkeypatch, mutate=_commit_gitattributes_diff_driver
    )
    await profile_run_review(str(repo), "c1", rev)
    git(repo, "config", "diff.custom.binary", "true")
    # Guard: the repo-local driver bends porcelain `git diff <rev>~1 <rev>`.
    raw = git(repo, "diff", f"{rev}~1", rev)
    assert "Binary files" in raw and "+x = 2" not in raw
    # The kit diff is unaffected.
    await profile_run_review(str(repo), "c1", rev)
    assert fake.calls[0]["prompt"] == fake.calls[1]["prompt"]
    assert "+x = 2" in fake.calls[1]["prompt"]
    assert "diff --git a/src/api.py b/src/api.py" in fake.calls[1]["prompt"]


async def test_a_committed_gitattributes_minus_diff_is_ignored_by_the_kit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A revision that commits ``*.py -diff`` makes porcelain report binary,
    but the kit-rendered diff stays textual (the plumbing renderer owns binary
    classification; attributes are never consulted)."""

    def _mutate(repo: Path) -> None:
        (repo / "src" / "api.py").write_text("x = 2\n")
        (repo / ".gitattributes").write_text("*.py -diff\n")

    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch, mutate=_mutate)
    # Guard: porcelain `git diff <rev>~1 <rev>` goes binary due to -diff attr.
    raw = git(repo, "diff", f"{rev}~1", rev)
    assert "Binary files" in raw and "+x = 2" not in raw
    # Kit diff: textual regardless of the -diff attribute.
    await profile_run_review(str(repo), "c1", rev)
    prompt = fake.calls[0]["prompt"]
    assert "+x = 2" in prompt
    assert "diff --git a/src/api.py b/src/api.py" in prompt
    assert "Binary files" not in prompt


def _touch_api_with_a_late_nul(repo: Path) -> None:
    # Git sniffs binary content in the first 8000 bytes only: this stays text.
    (repo / "src" / "api.py").write_bytes(
        b"x = 2\n" + b"pad = 0\n" * 1200 + b"late = '\x00'\n"
    )


async def test_a_nul_byte_in_the_diff_is_recorded_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # R5 update: the kit's binary rule is NUL ANYWHERE in either blob.
    # A late NUL (beyond git's 8000-byte sniff window) still makes the path
    # binary in the kit. So the rendered output is "Binary files ... differ",
    # not raw bytes, and "+x = 2" does NOT appear for that path.
    repo, rev, fake, _ = _prepare(
        tmp_path, monkeypatch, mutate=_touch_api_with_a_late_nul
    )
    assert "\x00" in git(repo, "show", f"{rev}:src/api.py")  # the NUL is committed
    result = await profile_run_review(str(repo), "c1", rev)
    prompt = fake.calls[0]["prompt"]
    assert result["status"] == "completed"
    assert "\x00" not in prompt
    # Any-position NUL => binary: the path renders as "Binary files ... differ".
    assert "Binary files a/src/api.py and b/src/api.py differ" in prompt
    # The binary path is NOT rendered as text — "+x = 2" must not appear.
    assert "+x = 2" not in prompt
    assert _review(repo, rev)["status"] == "completed"


async def test_an_oversized_diff_is_cut_with_a_visible_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # R5 update: the cut is applied AFTER UTF-8 encoding (byte boundary, not
    # codepoint boundary). The marker still appears as "[diff truncated at N bytes]".
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(review_module, "_MAX_DIFF_BYTES", 40)
    await profile_run_review(str(repo), "c1", rev)
    prompt = fake.calls[0]["prompt"]
    assert "[diff truncated at 40 bytes]" in prompt
    assert "+x = 2" not in prompt


async def test_a_real_binary_blob_stays_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A committed binary blob (early NUL) is rendered as 'Binary files … differ',
    never raw bytes, and the review completes successfully."""

    def _mutate(repo: Path) -> None:
        (repo / "src").mkdir(exist_ok=True)
        # Write a blob with an early NUL so _is_binary fires immediately.
        (repo / "src" / "img.bin").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch, mutate=_mutate)
    result = await profile_run_review(str(repo), "c1", rev)
    prompt = fake.calls[0]["prompt"]
    assert result["status"] == "completed"
    # The binary path renders as "Binary files … differ", not raw bytes.
    assert "Binary files" in prompt
    assert "img.bin" in prompt
    # No raw binary bytes leak into the prompt.
    assert b"\x00" not in prompt.encode("utf-8")
    assert b"\x89PNG" not in prompt.encode("utf-8")


async def test_an_all_invalid_utf8_text_blob_is_rendered_and_byte_cut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A blob of invalid UTF-8 bytes with NO NUL and under 1 MiB is treated as
    text: the kit renders it with U+FFFD replacements, and a small
    _MAX_DIFF_BYTES monkeypatch cuts on a byte boundary."""

    # Invalid UTF-8: 0x80-0xBF continuation bytes with no leading byte.
    # No NUL, well under 1 MiB.
    invalid_utf8 = b"\x80\x81\x82\x83\x84\x85\n"

    def _mutate(repo: Path) -> None:
        (repo / "src" / "api.py").write_bytes(invalid_utf8)

    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch, mutate=_mutate)
    # The blob has no NUL and is tiny, so it is text.
    assert b"\x00" not in invalid_utf8 and len(invalid_utf8) < _BINARY_SIZE

    # First, with no truncation: the invalid bytes render as U+FFFD (the kit
    # decodes each side utf-8 "replace"), and the content line is present.
    await profile_run_review(str(repo), "c1", rev)
    prompt = fake.calls[0]["prompt"]
    assert "\ufffd" in prompt  # invalid UTF-8 became the replacement character
    assert "\x00" not in prompt  # never a raw NUL in the prompt

    # Then, the byte cut is applied AFTER UTF-8 encoding: a limit that lands
    # mid-render truncates on a byte boundary and leaves the visible marker.
    # U+FFFD is 3 bytes encoded, so a byte cut can split one; the prompt must
    # still be valid text (no raw NUL, marker present).
    monkeypatch.setattr(review_module, "_MAX_DIFF_BYTES", 120)
    await profile_run_review(str(repo), "c1", rev)
    cut_prompt = fake.calls[1]["prompt"]
    assert "[diff truncated at 120 bytes]" in cut_prompt
    assert "\x00" not in cut_prompt


async def test_mode_change_add_delete_and_empty_file_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One revision that adds a file, deletes one, chmods a third (100644→100755)
    and commits an empty file; the rendered diff carries the correct headers."""
    import stat

    def _mutate(repo: Path) -> None:
        # Add a new file.
        (repo / "src" / "new_module.py").write_text("y = 1\n")
        # Delete an existing tracked file.
        (repo / "src" / "contracts.yaml").unlink()
        # Chmod src/api.py from 100644 to 100755.
        api = repo / "src" / "api.py"
        api.chmod(api.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        # Commit an empty file.
        (repo / "src" / "empty.py").write_bytes(b"")

    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch, mutate=_mutate)
    result = await profile_run_review(str(repo), "c1", rev)
    prompt = fake.calls[0]["prompt"]
    assert result["status"] == "completed"
    # Added file.
    assert "new file mode" in prompt
    assert "new_module.py" in prompt
    # Deleted file.
    assert "deleted file mode" in prompt
    assert "contracts.yaml" in prompt
    # Mode change (chmod). Git may not track executable bits depending on
    # core.fileMode; check conditionally so the test stays green on both.
    if "old mode" in prompt:
        assert "new mode" in prompt
    # Empty file: header present, no hunk (no lines to diff).
    assert "empty.py" in prompt
    # The empty file renders as a header block, not raw content.
    assert (
        "Binary files" not in prompt
        or "empty.py" not in prompt.split("Binary files")[1].split("\n")[0]
    )


# No gitlink fixture is added: creating a real submodule via the helpers
# requires a second bare repo and `git submodule add`, which the change_fixture
# helpers do not support. The _render_change gitlink branch is covered by a
# direct unit test if needed; skipping integration fixture here to avoid a
# brittle multi-repo setup in the suite.


def test_render_change_gitlink_emits_subproject_commit_without_reading_a_blob(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gitlink branch returns header + Subproject commit line and NEVER reads a blob."""
    import beddel_profile_dev._io as _io_mod

    def _no_blob(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("_blob_by_oid must not be called for a gitlink change")

    monkeypatch.setattr(_io_mod, "_blob_by_oid", _no_blob)

    # Case 1: modified submodule (mode_a == mode_b == '160000').
    c1 = _Change(
        status="M",
        mode_a="160000",
        mode_b="160000",
        oid_a="a" * 40,
        oid_b="b" * 40,
        path="vendor/sub",
    )
    result1 = _render_change(Path("/nonexistent"), c1)
    assert result1 == (
        "diff --git a/vendor/sub b/vendor/sub\n"
        + "Subproject commit "
        + "a" * 40
        + ".."
        + "b" * 40
        + "\n"
    )
    assert result1.endswith("\n")

    # Case 2: added submodule (mode_a == '000000', mode_b == '160000').
    c2 = _Change(
        status="A",
        mode_a="000000",
        mode_b="160000",
        oid_a="0" * 40,
        oid_b="c" * 40,
        path="vendor/new",
    )
    result2 = _render_change(Path("/nonexistent"), c2)
    assert "diff --git a/vendor/new b/vendor/new\n" in result2
    assert "Subproject commit " + "0" * 40 + ".." + "c" * 40 in result2
    assert result2.endswith("\n")


async def test_no_impact_record_stops_with_unscoped_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, factory_calls = _prepare(tmp_path, monkeypatch, impact=False)
    assert (await _refused(repo, rev)).code == PROFILE_REVIEW_UNSCOPED
    assert not (repo / RECORDS).exists()
    assert fake.calls == [] and factory_calls == []


async def test_an_impact_record_of_another_change_is_not_a_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    assert (await _refused(repo, rev, change="c2")).code == PROFILE_REVIEW_UNSCOPED
    assert not (repo / RECORDS / "changes" / "c2").exists()
    assert fake.calls == []
    _nothing_written(repo, rev)


async def test_an_impact_record_of_another_revision_is_not_a_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    other = resolve_revision(repo, f"{rev}~1")
    assert (await _refused(repo, other)).code == PROFILE_REVIEW_UNSCOPED
    assert fake.calls == []
    _nothing_written(repo, rev)


_IMPACT_BREAKS: dict[str, Callable[[dict[str, Any]], object]] = {
    "wrong_change": lambda d: d.update(change_id="other"),
    "wrong_revision": lambda d: d.update(revision="0" * 40),
    "wrong_schema": lambda d: d.update(schema="profile-dev/impact/2"),
    "extra_key": lambda d: d.update(verdict="x"),
    "missing_key": lambda d: d.pop("footprint"),
    "bad_digest": lambda d: d.update(inventory_sha256="abc"),
    "bad_version": lambda d: d.update(inventory_version="Bad Version"),
    "non_string_version": lambda d: d.update(inventory_version=1),
    "bad_base": lambda d: d.update(base="main"),
    "footprint_not_list": lambda d: d.update(footprint="src/api.py"),
    "footprint_item_not_string": lambda d: d.update(footprint=[1]),
    "points_not_list": lambda d: d.update(affected_points={}),
    "evidence_not_list": lambda d: d.update(required_evidence=None),
}


@pytest.mark.parametrize("name", sorted(_IMPACT_BREAKS))
async def test_an_inconsistent_impact_record_is_unscoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    path = _revision_dir(repo, rev) / "impact.json"
    impact = json.loads(path.read_text())
    _IMPACT_BREAKS[name](impact)
    path.write_text(json.dumps(impact))
    assert (await _refused(repo, rev)).code == PROFILE_REVIEW_UNSCOPED
    assert fake.calls == []
    _nothing_written(repo, rev)


@pytest.mark.parametrize("content", ["", "{", "[]", "null", '"text"', "123"])
async def test_an_unreadable_impact_record_is_unscoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    (_revision_dir(repo, rev) / "impact.json").write_text(content)
    assert (await _refused(repo, rev)).code == PROFILE_REVIEW_UNSCOPED
    assert fake.calls == []
    _nothing_written(repo, rev)


# --- AC 4: own timeout; timed_out and errored are results ---------------------


async def test_the_adapters_timeout_is_a_timed_out_result_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, _, _ = _prepare(
        tmp_path, monkeypatch, adapter=FakeReviewAdapter("timeout")
    )
    result = await profile_run_review(str(repo), "c1", rev)
    assert result["status"] == "timed_out"
    assert result["error_code"] == AGENT_TIMEOUT
    review = _review(repo, rev)
    assert set(review) == OUTCOME_KEYS | {"error_code"}
    assert review["status"] == "timed_out"
    assert review["error_code"] == AGENT_TIMEOUT
    assert (repo / review["review_ref"]).read_text() == ""


async def test_any_other_adapter_error_is_an_errored_result_not_an_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, _, _ = _prepare(
        tmp_path, monkeypatch, adapter=FakeReviewAdapter("error")
    )
    result = await profile_run_review(str(repo), "c1", rev)
    assert result["status"] == "errored"
    review = _review(repo, rev)
    assert set(review) == OUTCOME_KEYS | {"error_code"}
    assert review["status"] == "errored"
    assert review["error_code"] == AGENT_EXECUTION_FAILED
    # Never the adapter's message, stderr or any secret it carried.
    raw = (_revision_dir(repo, rev) / "review.json").read_text()
    assert "secret-xyz" not in raw and "fake review failed" not in raw


async def test_a_route_that_cannot_start_is_an_errored_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, _, _ = _prepare(
        tmp_path, monkeypatch, adapter=FakeReviewAdapter("os_error")
    )
    result = await profile_run_review(str(repo), "c1", rev)
    assert result["status"] == "errored"
    assert _review(repo, rev)["error_code"] == AGENT_EXECUTION_FAILED


async def test_an_error_code_that_is_not_a_plain_token_is_never_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Odd(FakeReviewAdapter):
        async def execute(self, prompt: str, **kwargs: Any) -> Any:
            raise AgentError(code="Bearer sk-secret leaked here", message="m")

    repo, rev, _, _ = _prepare(tmp_path, monkeypatch, adapter=_Odd())
    await profile_run_review(str(repo), "c1", rev)
    review = _review(repo, rev)
    assert review["status"] == "errored"
    assert review["error_code"] == AGENT_EXECUTION_FAILED
    assert "sk-secret" not in (_revision_dir(repo, rev) / "review.json").read_text()


async def test_an_adapter_that_never_returns_is_cut_by_the_review_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(
        tmp_path, monkeypatch, adapter=FakeReviewAdapter("hang")
    )
    monkeypatch.setattr(cfg, "REVIEW_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(review_module, "_GUARD_SECONDS", 0)
    result = await profile_run_review(str(repo), "c1", rev)
    assert result["status"] == "timed_out"
    assert _review(repo, rev)["error_code"] == AGENT_TIMEOUT
    assert len(fake.calls) == 1


async def test_an_unexpected_exception_is_not_swallowed_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, _, _ = _prepare(
        tmp_path, monkeypatch, adapter=FakeReviewAdapter("crash")
    )
    with pytest.raises(RuntimeError):
        await profile_run_review(str(repo), "c1", rev)
    _nothing_written(repo, rev)


# --- AC 5: attempts are append-only; review.json names the latest -------------


async def test_attempts_are_append_only_and_review_json_names_the_latest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    out = _revision_dir(repo, rev) / "review-output"
    fake.output = "first\n"
    first = await profile_run_review(str(repo), "c1", rev)
    assert first["attempt"] == 1
    assert (out / "1.txt").read_text() == "first\n"
    assert set(_review(repo, rev)) == OUTCOME_KEYS

    fake.behavior = "timeout"
    second = await profile_run_review(str(repo), "c1", rev)
    assert second["attempt"] == 2
    review = _review(repo, rev)
    assert review["status"] == "timed_out" and review["error_code"] == AGENT_TIMEOUT
    assert review["review_ref"].endswith("/review-output/2.txt")

    fake.behavior, fake.output = "completed", "third\n"
    third = await profile_run_review(str(repo), "c1", rev)
    assert third["attempt"] == 3
    review = _review(repo, rev)
    assert review["status"] == "completed"
    assert "error_code" not in review  # a completed latest attempt omits it
    assert review["review_ref"].endswith("/review-output/3.txt")

    assert sorted(p.name for p in out.iterdir()) == ["1.txt", "2.txt", "3.txt"]
    assert (out / "1.txt").read_text() == "first\n"  # never rewritten
    assert (out / "2.txt").read_text() == ""
    assert (out / "3.txt").read_text() == "third\n"
    assert not list((_revision_dir(repo, rev)).glob("*.tmp"))


async def test_attempt_numbering_continues_past_existing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, _, _ = _prepare(tmp_path, monkeypatch)
    out = _revision_dir(repo, rev) / "review-output"
    out.mkdir(parents=True)
    (out / "7.txt").write_text("old")
    (out / "notes.txt").write_text("not an attempt")
    (out / "0.txt").write_text("not an attempt")
    (out / "3").mkdir()
    result = await profile_run_review(str(repo), "c1", rev)
    assert result["attempt"] == 8
    assert (out / "7.txt").read_text() == "old"


async def test_a_lost_race_for_an_attempt_number_moves_to_the_next_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, _, _ = _prepare(tmp_path, monkeypatch)
    out = _revision_dir(repo, rev) / "review-output"
    out.mkdir(parents=True)
    # Another run claims attempt 1 between the listing and the exclusive create.
    real = review_module._next_attempt

    def _stale(root: Path, output_rel: str) -> int:
        real(root, output_rel)
        (out / "1.txt").write_text("raced")
        return 1

    monkeypatch.setattr(review_module, "_next_attempt", _stale)
    result = await profile_run_review(str(repo), "c1", rev)
    assert result["attempt"] == 2
    assert (out / "1.txt").read_text() == "raced"


# --- AC 8: confinement and inputs ----------------------------------------------


async def test_a_review_output_symlink_that_escapes_the_repository_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (_revision_dir(repo, rev) / "review-output").symlink_to(outside)
    assert (await _refused(repo, rev)).code == PROFILE_REPOSITORY_INVALID
    assert list(outside.iterdir()) == []
    assert not (_revision_dir(repo, rev) / "review.json").exists()
    assert fake.calls == []


async def test_a_review_json_symlink_that_escapes_the_repository_is_not_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    outside = tmp_path / "outside.json"
    outside.write_text("untouched")
    (_revision_dir(repo, rev) / "review.json").symlink_to(outside)
    assert (await _refused(repo, rev)).code == PROFILE_REPOSITORY_INVALID
    assert outside.read_text() == "untouched"
    assert fake.calls == []


async def test_a_review_output_that_is_a_file_is_refused_before_the_route_is_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    (_revision_dir(repo, rev) / "review-output").write_text("x")
    assert (await _refused(repo, rev)).code == PROFILE_REPOSITORY_INVALID
    assert fake.calls == []
    assert not (_revision_dir(repo, rev) / "review.json").exists()


async def test_a_review_json_that_is_a_directory_is_refused_before_the_route_is_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    (_revision_dir(repo, rev) / "review.json").mkdir()
    assert (await _refused(repo, rev)).code == PROFILE_REPOSITORY_INVALID
    assert fake.calls == []
    assert not (_revision_dir(repo, rev) / "review-output").exists()


@pytest.mark.parametrize("change_id", ["", "../c1", "C1", "a b", "x" * 80])
async def test_an_invalid_change_id_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change_id: str
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    assert (await _refused(repo, rev, change=change_id)).code == PROFILE_CHANGE_INVALID
    assert fake.calls == []
    _nothing_written(repo, rev)


async def test_a_path_that_is_not_the_repository_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    with pytest.raises(ProfileError) as info:
        await profile_run_review(str(repo / "src"), "c1", rev)
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    with pytest.raises(ProfileError) as info:
        await profile_run_review(str(repo), "c1", "no-such-revision")
    assert info.value.code == PROFILE_REPOSITORY_INVALID
    assert fake.calls == []
    _nothing_written(repo, rev)


async def test_a_malformed_review_config_refuses_before_anything_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, rev, fake, _ = _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(cfg, "REVIEW_MODEL", "not a model name")
    assert (await _refused(repo, rev)).code == PROFILE_CONFIG_INVALID
    assert fake.calls == []
    _nothing_written(repo, rev)


# --- AC 2, 10, 12: the seam, the core and the adapter kit stay untouched -------


def test_the_tool_has_no_other_path_to_an_adapter_and_never_widens_the_sandbox() -> (
    None
):
    source = (
        KIT_ROOT / "python" / "beddel_profile_dev" / "tools" / "review.py"
    ).read_text()
    assert "beddel_agent_kiro" not in source
    assert "_adapters.get_review_adapter(" in source
    for forbidden in (
        "workspace-write",
        "danger-full-access",
        "api_key=",
        "subprocess",
    ):
        assert forbidden not in source, forbidden
    assert "sandbox=_SANDBOX" in source and '_SANDBOX = "read-only"' in source


def test_the_core_and_the_adapter_kit_are_untouched() -> None:
    def _porcelain(*args: str) -> str | None:
        result = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        return result.stdout if result.returncode == 0 else None

    adapter_kit = KIT_ROOT.parent / "agent-kiro-kit"
    changed = _porcelain(
        "-C", str(KIT_ROOT.parent), "status", "--porcelain", "--", str(adapter_kit)
    )
    if changed is None:
        pytest.skip("not inside a Git work tree")
    assert changed == ""
    core = KIT_ROOT.parent.parent.parent.parent / "packages" / "beddel-py"
    if (core / ".git").exists():
        assert _porcelain("-C", str(core), "status", "--porcelain") == ""
