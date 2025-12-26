# Source Tree

```
packages/beddel/
├── src/
│   ├── index.ts                  # Main server exports (Node.js deps)
│   ├── server.ts                 # Server handler barrel export
│   ├── client.ts                 # Client exports (types only, browser-safe)
│   ├── core/
│   │   ├── parser.ts             # YAML parsing (FAILSAFE_SCHEMA)
│   │   ├── workflow.ts           # WorkflowExecutor class
│   │   └── variable-resolver.ts  # $variable.path resolution
│   ├── primitives/
│   │   ├── index.ts              # Handler registry (handlerRegistry)
│   │   ├── llm.ts                # streamText/generateText wrapper
│   │   └── output.ts             # JSON transform primitive
│   ├── providers/
│   │   └── index.ts              # Provider registry (google, bedrock)
│   ├── server/
│   │   └── handler.ts            # createBeddelHandler factory
│   ├── tools/
│   │   └── index.ts              # Tool registry (calculator, getCurrentTime)
│   └── types/
│       └── index.ts              # Type definitions (PrimitiveHandler, ExecutionContext, etc.)
├── examples/
│   └── agents/
│       └── assistant.yaml        # Sample streaming assistant agent
├── docs/
│   ├── prd/                      # Sharded PRD documents
│   │   ├── index.md
│   │   ├── goals-context.md
│   │   ├── requirements.md
│   │   ├── technical-assumptions.md
│   │   └── epic-list.md
│   └── architecture/             # Sharded Architecture documents
│       ├── index.md
│       ├── high-level-architecture.md
│       ├── tech-stack.md
│       ├── components.md
│       ├── source-tree.md
│       ├── core-workflows.md
│       └── api-reference.md
├── package.json
└── tsconfig.json
```

---

## Bundle Separation

Beddel exports three distinct bundles to support different runtime environments:

| Import Path | Entry File | Contents | Use Case |
|-------------|------------|----------|----------|
| `beddel` | `index.ts` | Full API: `loadYaml`, `WorkflowExecutor`, `handlerRegistry`, `toolRegistry`, `providerRegistry`, `registerPrimitive`, `registerTool`, `registerProvider` | Internal Beddel usage, custom handlers |
| `beddel/server` | `server.ts` | `createBeddelHandler`, `BeddelHandlerOptions` | Next.js API Routes (Consumer) |
| `beddel/client` | `client.ts` | Types only: `ParsedYaml`, `ExecutionContext`, `PrimitiveHandler`, etc. | Client Components, type-checking |

> [!IMPORTANT]
> The `beddel` and `beddel/server` entry points use Node.js APIs (`fs/promises`).  
> **Never import these in client/browser code.** Use `beddel/client` for type imports.

---

## package.json exports

```json
{
  "exports": {
    ".": {
      "import": "./dist/index.js",
      "types": "./dist/index.d.ts"
    },
    "./server": {
      "import": "./dist/server.js",
      "types": "./dist/server.d.ts"
    },
    "./client": {
      "import": "./dist/client.js",
      "types": "./dist/client.d.ts"
    }
  }
}
```

---

## Notes

- **Consumer application** places YAML agents in `src/agents/` (configurable via `agentsPath`)
- **API route** lives in `app/api/beddel/chat/route.ts` using `createBeddelHandler`
- **`call-agent` primitive** is registered as a placeholder — implementation coming soon
- **No test folder shown** — tests should be co-located or in `__tests__/` per project preference

