# bonar-cms-kit

Self-contained Solution Kit for the **bonar-cms** (Bota na Rede) multi-tenant CMS platform. Encapsulates the full tenant lifecycle — configuration generation, schema validation, static site build, Firebase deploy, and local preview — inside a single portable Beddel kit.

## Overview

The kit provides 11 Python tools organized by concern and 3 bundled workflows for common pipelines. The Python layer provides Beddel-native tool contracts; an internal Node.js monorepo (`node/`) contains the CMS runtime (Zod schemas, React components, Next.js static site generator, Firebase deployment).

**Architecture**: Python orchestrator wrapping a self-contained Node.js monorepo.

## Installation

```bash
beddel kit install bonar-cms-kit
```

After installation, the Node.js dependencies must be bootstrapped:

```bash
cd <kit-path>/node
pnpm install --frozen-lockfile
```

## Tool Reference

### Generation

| Tool | Description |
|------|-------------|
| `generate_tenant` | AI-powered tenant config generation from a natural language business briefing. Delegates to the workflow-level LLM primitive. |

### Validation

| Tool | Description |
|------|-------------|
| `validate_tenant` | Validates tenant JSON against `@botanarede/schema` (Zod) via Node.js subprocess bridge. |

### CRUD

| Tool | Description |
|------|-------------|
| `create_tenant` | Write new tenant config JSON to the kit-internal tenants directory. |
| `read_tenant` | Load tenant config by ID. |
| `update_tenant` | Merge partial updates into existing tenant config (deep merge). |
| `list_tenants` | List all tenant IDs with metadata. |

### Build

| Tool | Description |
|------|-------------|
| `build_site` | Next.js static export for a tenant (`next build` via SafeSubprocessRunner). |

### Deploy

| Tool | Description |
|------|-------------|
| `deploy_site` | Firebase Hosting deploy for a tenant (requires `firebase` CLI + ADC). |
| `provision_firebase` | Create Firebase project + enable Hosting API via `gcloud` CLI. |

### Dev

| Tool | Description |
|------|-------------|
| `preview_site` | Start a local Next.js dev server for a tenant (long-running, returns PID). |
| `stop_preview` | Stop a running preview dev server by PID (SIGTERM). |

## Workflow Reference

All workflows live in `workflows/` and follow the Beddel workflow YAML format.

### onboarding-novo-cliente

Full new client pipeline: provision Firebase → generate tenant config (LLM) → validate → save → build → deploy.

**Inputs**: `briefing` (string), `project_id` (string), `tenant_id` (string)

```bash
beddel run workflows/onboarding-novo-cliente.yaml \
  --input briefing="Café na praia, estilo tropical" \
  --input project_id="meu-cafe-firebase" \
  --input tenant_id="cafe-praia"
```

### deploy-tenant

Build + deploy for an existing tenant: read config → validate → build static export → deploy to Firebase Hosting.

**Inputs**: `tenant_id` (string), `project_id` (string)

### update-tenant

Modify tenant configuration and redeploy: read → merge changes → validate → build → deploy.

**Inputs**: `tenant_id` (string), `project_id` (string), `changes` (dict)

## Architecture Notes

- **Self-contained**: The kit owns all Node.js source code internally at `node/`. No external monorepo references.
- **Python orchestrator**: All tools are Python functions using `SafeSubprocessRunner` for Node.js/CLI calls.
- **Long-running exception**: `preview_site` uses `subprocess.Popen` directly (non-blocking).
- **Error handling**: Kit-local `CMSError` extends `BeddelError` with `CMS_*` error codes.
- **Subprocess safety**: No `shell=True`, explicit environment variables, timeout enforcement, tenant ID sanitization.
- **Tenant ID format**: `^[a-zA-Z0-9][a-zA-Z0-9\-]*$` (kebab-case, path-traversal safe).

## Development

```bash
# Activate venv (required)
source src/beddel-py/.venv/bin/activate

# Run tests
cd repo/kits/bonar-cms-kit
pytest tests/ -v

# Lint
ruff check python/ tests/
ruff format --check python/ tests/
```

## References

- PRD: `docs/prd/40-epic-cms-bonar-cms-kit.md`
- Architecture: `docs/architecture/bonar-cms-kit.md`
- Kit manifest: `kit.yaml`
