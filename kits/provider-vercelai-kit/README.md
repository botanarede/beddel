# provider-vercelai-kit

Vercel AI SDK multi-provider LLM adapter for TypeScript.

## Language targets

| Language    | Status | Notes |
| ----------- | ------ | ----- |
| Python      | `unavailable` | Unavailable — peer kit: [`provider-litellm-kit`](../provider-litellm-kit/) |
| TypeScript  | `implemented` | Package: `@beddel/provider-vercelai` |

## Layout

- `python/README.md` — stub documenting why no implementation exists in this language
- `typescript/src/` — TypeScript source + `package.json`

## Manifest

See [`kit.yaml`](./kit.yaml) for the full contract surface (tools, adapters, contracts, workflows) and language-specific declarations.

## See also

- [`spec/PROTOCOL.md`](../../spec/PROTOCOL.md) — kit protocol version and field semantics
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — how to contribute kits and promote planned targets to implemented
