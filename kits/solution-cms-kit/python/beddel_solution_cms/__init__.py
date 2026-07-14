"""Solution CMS Kit — self-contained multi-tenant CMS orchestration.

Wraps tenant configuration lifecycle (CRUD), validation, generation, static
site build, and Firebase deploy. The Python layer provides Beddel-native
tool contracts; a kit-internal Node.js monorepo (under ``node/``) provides
the CMS runtime.

This story (CMS.1) implements the scaffold and the tenant CRUD tools only.
Other submodules (validation, generation, build, deploy, dev) are added in
later stories.
"""

from __future__ import annotations

__all__ = [
    "CMSError",
    "get_kit_root",
    "get_tenants_dir",
    "list_tenant_ids",
    "load_tenant",
    "save_tenant",
]


def __getattr__(name: str) -> object:
    if name == "CMSError":
        from beddel_solution_cms._errors import CMSError

        return CMSError
    if name in {
        "get_kit_root",
        "get_tenants_dir",
        "list_tenant_ids",
        "load_tenant",
        "save_tenant",
    }:
        from beddel_solution_cms import tenant_context

        return getattr(tenant_context, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
