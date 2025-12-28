# Source Tree

```
packages/beddel/
├── src/
│   ├── index.ts                  # Main server exports (Node.js deps)
│   ├── server.ts                 # Server handler barrel export
│   ├── client.ts                 # Client exports (types only, browser-safe)
│   ├── agents/                   # Built-in agents (bundled with package)
│   │   ├── index.ts              # Built-in agents registry
│   │   ├── assistant.yaml        # Google Gemini streaming assistant
│   │   ├── assistant-bedrock.yaml # Amazon Bedrock assistant
│   │   ├── assistant-openrouter.yaml # OpenRouter assistant
│   │   ├── text-generator.yaml   # Text generation (non-streaming)
│   │   ├── multi-step-assistant.yaml # 4-step analysis pipeline
│   │   └── assistant-gitmcp.yaml # GitMCP documentation assistant
│   ├── core/
│   │   ├── parser.ts             # YAML parsing (FAILSAFE_SCHEMA)
│   │   ├── workflow.ts           # WorkflowExecutor class
│   │   └── variable-resolver.ts  # $variable.path resolution
│   ├── primitives/
│   │   ├── index.ts              # Handler registry (handlerRegistry)
│   │   ├── llm-core.ts           # Shared utilities (mapTools, callbacks)
│   │   ├── chat.ts               # Frontend streaming primitive
│   │   ├── llm.ts                # Workflow blocking primitive
│   │   ├── output.ts             # JSON transform primitive
│   │   ├── call-agent.ts         # Sub-agent invocation primitive
│   │   └── mcp-tool.ts           # MCP server tool execution primitive
│   ├── providers/
│   │   └── index.ts              # Provider registry (google, bedrock, openrouter)
│   ├── server/
│   │   └── handler.ts            # createBeddelHandler factory
│   ├── tools/
│   │   └── index.ts              # Tool registry (calculator, getCurrentTime)
│   └── types/
│       └── index.ts              # Type definitions
├── docs/
│   ├── architecture/             # Architecture documentation
│   └── prd/                      # Product requirements
├── package.json
└── tsconfig.json
```

---

## Bundle Separation

Beddel exports three distinct bundles to support different runtime environments:

| Import Path | Entry File | Contents | Use Case |
|-------------|------------|----------|----------|
| `beddel` | `index.ts` | Full API: `loadYaml`, `WorkflowExecutor`, registries | Internal usage, custom handlers |
| `beddel/server` | `server.ts` | `createBeddelHandler`, `BeddelHandlerOptions` | Next.js API Routes |
| `beddel/client` | `client.ts` | Types only: `ParsedYaml`, `ExecutionContext`, etc. | Client Components |

> [!IMPORTANT]
> The `beddel` and `beddel/server` entry points use Node.js APIs (`fs/promises`).  
> **Never import these in client/browser code.** Use `beddel/client` for type imports.

---

## Primitives Structure

```
primitives/
├── index.ts          # Registry and exports
├── llm-core.ts       # Shared: mapTools, callbacks, LlmConfig type
├── chat.ts           # type: "chat" — streaming, converts UIMessage
├── llm.ts            # type: "llm" — blocking, uses ModelMessage
├── output.ts         # type: "output-generator" — JSON transform
├── call-agent.ts     # type: "call-agent" — sub-agent invocation
└── mcp-tool.ts       # type: "mcp-tool" — MCP server integration
```

### Primitive Comparison

| Primitive | Streaming | Message Format | Use Case |
|-----------|-----------|----------------|----------|
| `chat` | Always | UIMessage → ModelMessage | Frontend (`useChat`) |
| `llm` | Never | ModelMessage (direct) | Workflows, pipelines |
| `output-generator` | Never | N/A | JSON transform |
| `call-agent` | Depends | Passes through | Sub-agent composition |
| `mcp-tool` | Never | N/A | External MCP servers |

---

## Built-in Agents

Agents bundled with the package, available without configuration:

| File | Type | Provider | Description |
|------|------|----------|-------------|
| `assistant.yaml` | `chat` | Google | Streaming chat assistant |
| `assistant-bedrock.yaml` | `chat` | Bedrock | Llama 3.2 assistant |
| `assistant-openrouter.yaml` | `chat` | OpenRouter | Free tier assistant |
| `assistant-gitmcp.yaml` | `mcp-tool` + `chat` | Google + MCP | Documentation assistant via GitMCP |
| `text-generator.yaml` | `llm` | Google | Text generation |
| `multi-step-assistant.yaml` | `call-agent` + `llm` | Google | 4-step pipeline |

**Resolution Order:**
1. User agents (`src/agents/*.yaml`) — allows override
2. Built-in agents (package) — fallback

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
