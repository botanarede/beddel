# KIT_PROTOCOL_VERSION

`2026-05-09`

The Beddel Kit Protocol governs how kits declare cross-language targets in their
`kit.yaml` manifests and how SDKs (currently `beddel-py` and `beddel-ts`) consume
those declarations. The version string is a date in ISO-8601 format, following
the [Model Context Protocol](https://modelcontextprotocol.io) versioning
convention.

---

## Contract Summary

This repository (`botanarede/beddel`) is the **single source of truth** for:

- The shared specification (`spec/`) — JSON Schemas, port contracts, fixtures.
- The unified kit catalog (`kits/`) — every kit declares **both** `targets.python`
  and `targets.typescript` blocks.
- The protocol versioning (this file).

Consumer SDKs (`beddel-py` at <https://github.com/botanarede/beddel-py>,
`beddel-ts` at <https://github.com/botanarede/beddel-ts>) **read** kits and
spec at install time. They do not own the kits or the spec. They publish the
adapter glue, parsers, and runtime that make the contracts executable.

This separation lets us:

1. Add a kit once and have both SDKs see the declaration immediately.
2. Mark a kit as `planned` in one language and `implemented` in another, without
   the consuming SDK needing to lie about availability.
3. Evolve the spec (schemas, contracts) without coordinating two repository releases.

---

## Manifest Schema Extensions (introduced in `2026-05-09`)

The schema at [`spec/kits/kit-manifest.schema.json`](./kits/kit-manifest.schema.json)
adds an optional `KitLanguageTarget` block under each language key in
`targets.{python,typescript}`. All four fields below are optional — manifests
written before `2026-05-09` continue to validate without changes.

| Field                  | Type    | When required                          | Purpose                                                                                                  |
| ---------------------- | ------- | -------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `status`               | enum    | recommended for all kits               | One of `implemented`, `planned`, `unavailable`. Drives validation gates and SDK fallback behavior.       |
| `implementation_path`  | string  | when `status: planned`                 | Repo-relative path to the planned entry point. Helps the standardization agent generate scaffolding.    |
| `unavailable_reason`   | string  | when `status: unavailable`             | Human-readable rationale. **Should** name the peer kit (e.g. "see `serve-express-kit`").                 |
| `dev_note`             | string  | optional                               | Free-form note for contributors — library choice rationale, prior-art pointers, ecosystem caveats.       |

### Example: dual-implemented kit

```yaml
targets:
  python:
    status: implemented
    module: beddel_observability_otel
    dependencies: ["opentelemetry-api>=1.0"]
  typescript:
    status: implemented
    package: "@beddel/observability-otel"
    dependencies: ["@opentelemetry/api: ^1.9"]
```

### Example: Python-only with planned TypeScript

```yaml
targets:
  python:
    status: implemented
    module: beddel_tools_http
    dependencies: ["httpx>=0.27"]
  typescript:
    status: planned
    implementation_path: ./typescript/src/http.ts
```

### Example: framework-specific kit (peer pair)

```yaml
# serve-fastapi-kit/kit.yaml
targets:
  python:
    status: implemented
    module: beddel_serve_fastapi
  typescript:
    status: unavailable
    unavailable_reason: "FastAPI is a Python-only ASGI framework. See peer kit serve-express-kit."

# serve-express-kit/kit.yaml
targets:
  python:
    status: unavailable
    unavailable_reason: "Express is a JS-only HTTP framework. See peer kit serve-fastapi-kit."
  typescript:
    status: implemented
    package: "@beddel/serve-express"
```

---

## Capabilities Matrix

The two consumer SDKs currently read these manifest fields:

| Field                                  | `beddel-py` reads | `beddel-ts` reads | Notes                                                                                  |
| -------------------------------------- | ----------------- | ----------------- | -------------------------------------------------------------------------------------- |
| `name`, `version`, `description`       | ✅                | ✅                | Required by both.                                                                      |
| `dependencies` (top-level)             | ✅                | ✅                | Currently advisory; install via `beddel kit install <name>` or pnpm respectively.      |
| `tools[].target`                       | ✅                | ✅                | Module-path resolution per language.                                                   |
| `adapters[].target` / `implementation` | ✅                | ✅                | Both formats supported.                                                                |
| `targets.python.module`                | ✅                | —                 | Python distribution module name.                                                       |
| `targets.python.dependencies`          | ✅                | —                 | Authoritative for Python install resolution.                                           |
| `targets.typescript.package`           | —                 | ✅                | NPM package name.                                                                      |
| `targets.typescript.dependencies`      | —                 | ✅                | Authoritative for TS install resolution.                                               |
| `targets.{python,typescript}.status`   | partial (planned) | partial (planned) | Read by both but not yet enforced; planned to gate `kit install` in a follow-up story. |

The "partial (planned)" entries in the last row mean: as of protocol version
`2026-05-09`, both SDKs ignore the `status` field at runtime. The
`validate-kits.yml` GitHub Actions workflow enforces it. SDK enforcement
(refusing to install a kit declared `unavailable` for the consuming language) is
a follow-up commitment for protocol version `2026-MM-DD` (next bump).

---

## Versioning Policy

`KIT_PROTOCOL_VERSION` follows the date-string convention from the Model Context
Protocol:

- **Patch / additive** (no version bump required): adding new optional fields,
  new enum members that fall back gracefully, new $defs that are not referenced
  by required-field paths.
- **Minor** (date string update): adding new required-when-conditional fields
  (e.g. requiring `unavailable_reason` when `status: unavailable`), changing
  semantics of existing fields, adding a top-level required field.
- **Major** (date string + compatibility statement): breaking changes — removing
  a field, changing a field's type, renaming a target language key.

The current change (introducing `KitLanguageTarget` with four optional fields)
is technically additive. We bump the version to `2026-05-09` anyway because:

1. The new fields encode contract semantics (peer-kit unavailability,
   planned-implementation paths) that downstream tooling will rely on.
2. A clear baseline lets future bumps reference "anything ≥ 2026-05-09 has
   `status` available".

---

## Compatibility Statement

| Protocol version | Compatible `beddel-py` | Compatible `beddel-ts` |
| ---------------- | ---------------------- | ---------------------- |
| `2026-05-09`     | ≥ 0.1.8                | ≥ 0.1.0                |

Earlier `beddel-py` versions (≤ 0.1.7) lack the slim-core `kit_index` introduced
by Epic K2 and cannot consume manifests from this catalog reliably. Earlier
`beddel-ts` versions do not exist as published artifacts (TS-1 is in progress).

---

## References

- [Model Context Protocol versioning](https://github.com/modelcontextprotocol/specification) — date-string format precedent.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — how to add or evolve a kit.
- [`spec/kits/kit-manifest.schema.json`](./kits/kit-manifest.schema.json) — formal schema.
- [`.github/workflows/validate-kits.yml`](../.github/workflows/validate-kits.yml) — CI enforcement.
