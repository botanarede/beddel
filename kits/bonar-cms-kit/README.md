# bonar-cms-kit

Self-contained Solution Kit for the bonar-cms (Bota na Rede) multi-tenant CMS.
Encapsulates tenant configuration lifecycle, schema validation, static site
build, and Firebase deploy inside a single portable Beddel kit.

## Status (CMS.1)

Implemented:

- `create_tenant`, `read_tenant`, `update_tenant`, `list_tenants` — tenant
  config CRUD tools backed by kit-internal `node/tenants/*.json` files.

Planned (later stories in Epic CMS):

- `validate_tenant` (CMS.2) — Zod schema validation via Node.js bridge
- `generate_tenant` (CMS.3) — LLM-powered tenant config generation
- `build_site` (CMS.4) — Next.js static export
- `deploy_site`, `provision_firebase` (CMS.5) — Firebase Hosting deploy + gcloud provisioning
- `preview_site`, `stop_preview` (CMS.6) — local dev server lifecycle
- Bundled workflows + integration tests (CMS.7)

See `docs/prd/40-epic-cms-bonar-cms-kit.md` and
`docs/architecture/bonar-cms-kit.md` for full design.

## Install

```bash
beddel kit install bonar-cms-kit
```

## Development

```bash
source src/beddel-py/.venv/bin/activate
cd repo/kits/bonar-cms-kit
pytest tests/ -v
ruff check .
ruff format --check .
```
