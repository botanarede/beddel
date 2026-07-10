"""Unit tests for beddel_bonar_cms.tenant_context."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from beddel.domain.errors import BeddelError
from beddel_bonar_cms import tenant_context
from beddel_bonar_cms._errors import CMS_INVALID_TENANT_ID, CMS_TENANT_NOT_FOUND


def test_get_kit_root_resolves_to_kit_directory() -> None:
    root = tenant_context.get_kit_root()
    assert root.name == "bonar-cms-kit"
    assert (root / "kit.yaml").exists()


def test_get_tenants_dir_points_to_node_tenants() -> None:
    tenants_dir = tenant_context.get_tenants_dir()
    assert tenants_dir == tenant_context.get_kit_root() / "node" / "tenants"


@pytest.mark.parametrize(
    "tenant_id",
    ["cafe-bela-vista", "a", "a1-b2", "tenant123"],
)
def test_validate_tenant_id_accepts_valid_kebab_case(tenant_id: str) -> None:
    tenant_context.validate_tenant_id(tenant_id)  # does not raise


@pytest.mark.parametrize(
    "tenant_id",
    [
        "Cafe-Bela-Vista",  # uppercase
        "cafe_bela_vista",  # underscores
        "cafe bela vista",  # spaces
        "-cafe-bela",  # leading hyphen
        "cafe-bela-",  # trailing hyphen
        "cafe--bela",  # double hyphen
        "",  # empty
    ],
)
def test_validate_tenant_id_rejects_invalid(tenant_id: str) -> None:
    with pytest.raises(BeddelError) as exc_info:
        tenant_context.validate_tenant_id(tenant_id)
    assert exc_info.value.code == CMS_INVALID_TENANT_ID


def test_save_and_load_tenant_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenants_dir = tmp_path / "tenants"
    monkeypatch.setattr(tenant_context, "get_tenants_dir", lambda: tenants_dir)

    data = {"site": {"name": "Cafe Bela Vista", "domain": "cafebelavista.com"}}
    tenant_context.save_tenant("cafe-bela-vista", data)

    saved_path = tenants_dir / "cafe-bela-vista.json"
    assert saved_path.exists()
    assert json.loads(saved_path.read_text(encoding="utf-8")) == data

    loaded = tenant_context.load_tenant("cafe-bela-vista")
    assert loaded == data


def test_save_tenant_creates_tenants_dir_if_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenants_dir = tmp_path / "does" / "not" / "exist"
    monkeypatch.setattr(tenant_context, "get_tenants_dir", lambda: tenants_dir)
    assert not tenants_dir.exists()

    tenant_context.save_tenant("new-tenant", {"site": {}})

    assert tenants_dir.exists()
    assert (tenants_dir / "new-tenant.json").exists()


def test_load_tenant_raises_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenants_dir = tmp_path / "tenants"
    tenants_dir.mkdir()
    monkeypatch.setattr(tenant_context, "get_tenants_dir", lambda: tenants_dir)

    with pytest.raises(BeddelError) as exc_info:
        tenant_context.load_tenant("missing-tenant")
    assert exc_info.value.code == CMS_TENANT_NOT_FOUND


def test_load_tenant_raises_invalid_id_before_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenants_dir = tmp_path / "tenants"
    monkeypatch.setattr(tenant_context, "get_tenants_dir", lambda: tenants_dir)

    with pytest.raises(BeddelError) as exc_info:
        tenant_context.load_tenant("Invalid_ID")
    assert exc_info.value.code == CMS_INVALID_TENANT_ID
    # No directory should have been created/touched for an invalid ID.
    assert not tenants_dir.exists()


def test_list_tenant_ids_excludes_template_and_sorts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenants_dir = tmp_path / "tenants"
    tenants_dir.mkdir()
    monkeypatch.setattr(tenant_context, "get_tenants_dir", lambda: tenants_dir)

    for name in ["template", "foo", "bar"]:
        (tenants_dir / f"{name}.json").write_text("{}", encoding="utf-8")

    assert tenant_context.list_tenant_ids() == ["bar", "foo"]


def test_list_tenant_ids_returns_empty_when_dir_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenants_dir = tmp_path / "does-not-exist"
    monkeypatch.setattr(tenant_context, "get_tenants_dir", lambda: tenants_dir)

    assert tenant_context.list_tenant_ids() == []
