"""Unit tests for beddel_solution_cms.tools.crud."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from beddel.domain.errors import BeddelError
from beddel_solution_cms.tools import crud
from beddel_solution_cms._errors import (
    CMS_INVALID_TENANT_ID,
    CMS_TENANT_EXISTS,
    CMS_TENANT_NOT_FOUND,
)


@pytest.fixture(autouse=True)
def _tenants_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect all tenant CRUD I/O into an isolated tmp_path directory."""
    tenants_dir = tmp_path / "tenants"
    tenants_dir.mkdir()

    monkeypatch.setattr(crud, "get_tenants_dir", lambda: tenants_dir)
    monkeypatch.setattr(
        "beddel_solution_cms.tenant_context.get_tenants_dir", lambda: tenants_dir
    )
    return tenants_dir


class TestDeepMerge:
    def test_merges_nested_dicts(self) -> None:
        base = {"site": {"name": "Old", "domain": "old.com"}}
        changes = {"site": {"name": "New"}}
        merged = crud._deep_merge(base, changes)
        assert merged == {"site": {"name": "New", "domain": "old.com"}}

    def test_does_not_mutate_base(self) -> None:
        base = {"site": {"name": "Old"}}
        changes = {"site": {"name": "New"}}
        crud._deep_merge(base, changes)
        assert base == {"site": {"name": "Old"}}

    def test_replaces_lists_entirely(self) -> None:
        base = {"tags": ["a", "b"]}
        changes = {"tags": ["c"]}
        merged = crud._deep_merge(base, changes)
        assert merged == {"tags": ["c"]}

    def test_adds_new_top_level_keys(self) -> None:
        base = {"site": {"name": "X"}}
        changes = {"pages": {"home": {}}}
        merged = crud._deep_merge(base, changes)
        assert merged == {"site": {"name": "X"}, "pages": {"home": {}}}


class TestCreateTenant:
    def test_creates_new_tenant(self, _tenants_dir: Path) -> None:
        config = {"site": {"name": "Cafe Bela Vista", "domain": "cafebelavista.com"}}
        result = crud.create_tenant("cafe-bela-vista", config)

        assert result["success"] is True
        assert result["tenant_id"] == "cafe-bela-vista"
        saved_path = _tenants_dir / "cafe-bela-vista.json"
        assert saved_path.exists()
        assert json.loads(saved_path.read_text(encoding="utf-8")) == config
        assert result["path"] == str(saved_path)

    def test_raises_if_tenant_exists(self, _tenants_dir: Path) -> None:
        crud.create_tenant("cafe-bela-vista", {"site": {}})

        with pytest.raises(BeddelError) as exc_info:
            crud.create_tenant("cafe-bela-vista", {"site": {"name": "Overwrite"}})
        assert exc_info.value.code == CMS_TENANT_EXISTS

        # Original file must remain untouched.
        saved = json.loads(
            (_tenants_dir / "cafe-bela-vista.json").read_text(encoding="utf-8")
        )
        assert saved == {"site": {}}

    def test_raises_on_invalid_tenant_id(self, _tenants_dir: Path) -> None:
        with pytest.raises(BeddelError) as exc_info:
            crud.create_tenant("Invalid_ID", {"site": {}})
        assert exc_info.value.code == CMS_INVALID_TENANT_ID
        assert list(_tenants_dir.glob("*.json")) == []


class TestReadTenant:
    def test_reads_existing_tenant(self, _tenants_dir: Path) -> None:
        config = {"site": {"name": "Cafe"}}
        crud.create_tenant("cafe", config)

        assert crud.read_tenant("cafe") == config

    def test_raises_if_not_found(self, _tenants_dir: Path) -> None:
        with pytest.raises(BeddelError) as exc_info:
            crud.read_tenant("missing")
        assert exc_info.value.code == CMS_TENANT_NOT_FOUND


class TestUpdateTenant:
    def test_deep_merges_and_saves(self, _tenants_dir: Path) -> None:
        crud.create_tenant("cafe", {"site": {"name": "Old", "domain": "old.com"}})

        updated = crud.update_tenant("cafe", {"site": {"name": "New"}})

        assert updated == {"site": {"name": "New", "domain": "old.com"}}
        on_disk = json.loads((_tenants_dir / "cafe.json").read_text(encoding="utf-8"))
        assert on_disk == updated

    def test_raises_if_tenant_not_found(self, _tenants_dir: Path) -> None:
        with pytest.raises(BeddelError) as exc_info:
            crud.update_tenant("missing", {"site": {"name": "X"}})
        assert exc_info.value.code == CMS_TENANT_NOT_FOUND
        assert list(_tenants_dir.glob("*.json")) == []


class TestListTenants:
    def test_lists_all_tenants_sorted_with_metadata(self, _tenants_dir: Path) -> None:
        crud.create_tenant("zeta", {"site": {"name": "Zeta Bar", "domain": "zeta.com"}})
        crud.create_tenant(
            "alpha", {"site": {"name": "Alpha Cafe", "domain": "alpha.com"}}
        )

        result = crud.list_tenants()

        assert [t["id"] for t in result["tenants"]] == ["alpha", "zeta"]
        alpha = result["tenants"][0]
        assert alpha["name"] == "Alpha Cafe"
        assert alpha["domain"] == "alpha.com"
        assert "last_modified" in alpha and isinstance(alpha["last_modified"], str)

    def test_excludes_template(self, _tenants_dir: Path) -> None:
        (_tenants_dir / "template.json").write_text("{}", encoding="utf-8")
        crud.create_tenant("real-tenant", {"site": {"name": "Real"}})

        result = crud.list_tenants()

        assert [t["id"] for t in result["tenants"]] == ["real-tenant"]

    def test_returns_empty_list_when_no_tenants(self, _tenants_dir: Path) -> None:
        assert crud.list_tenants() == {"tenants": []}

    def test_defaults_name_domain_to_empty_string_when_absent(
        self, _tenants_dir: Path
    ) -> None:
        crud.create_tenant("bare", {"pages": {}})

        result = crud.list_tenants()

        bare = result["tenants"][0]
        assert bare["name"] == ""
        assert bare["domain"] == ""

    def test_skips_unreadable_tenant_file(self, _tenants_dir: Path) -> None:
        crud.create_tenant("good", {"site": {"name": "Good"}})
        (_tenants_dir / "broken.json").write_text("{not valid json", encoding="utf-8")

        result = crud.list_tenants()

        assert [t["id"] for t in result["tenants"]] == ["good"]
