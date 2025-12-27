# Components

## Core Components

### Parser (`src/core/parser.ts`)

**Responsibility:** Load and parse YAML workflow definitions securely.

**Key Interfaces:**
- `loadYaml(path: string): Promise<ParsedYaml>`

**Dependencies:** `js-yaml`

**Technology Stack:** Uses `FAILSAFE_SCHEMA` to prevent function instantiation.

---

### WorkflowExecutor (`src/core/workflow.ts`)

**Responsibility:** Execute workflow steps sequentially, managing context and variable storage.

**Key Interfaces:**
- `constructor(yaml: ParsedYaml)`
- `execute(input: any): Promise<Response | Record<string, unknown>>`

**Dependencies:** `handlerRegistry` (primitives)

**Technology Stack:** Pure TypeScript, no external dependencies.

---

### Variable Resolver (`src/core/variable-resolver.ts`)

**Responsibility:** Resolve `$input.*` and `$stepResult.*` variable references.

**Key Interfaces:**
- `resolveVariables(template: any, context: ExecutionContext): any`

**Dependencies:** None

**Technology Stack:** Pure TypeScript.

---

## Primitives

### Primitive Handler Registry (`src/primitives/index.ts`)

**Responsibility:** Register and lookup primitive handlers by step type.

**Key Interfaces:**
- `handlerRegistry: Record<string, PrimitiveHandler>`
- `registerPrimitive(type: string, handler: PrimitiveHandler): void`

**Built-in Primitives:**
- `chat` — Frontend streaming interface
- `llm` — Workflow LLM calls (non-streaming)
- `output-generator` — JSON transform
- `call-agent` — Sub-agent invocation

---

### LLM Core (`src/primitives/llm-core.ts`)

**Responsibility:** Shared utilities for `chat` and `llm` primitives.

**Key Interfaces:**
- `mapTools(toolDefinitions): ToolSet` — Maps YAML tool definitions to SDK tools
- `registerCallback(name: string, fn: CallbackFn): void` — Register lifecycle callbacks
- `callbackRegistry: Record<string, CallbackFn>` — Stores registered callbacks
- `LlmConfig` — Type definition for LLM step configuration

**Dependencies:** `ai`, `toolRegistry`

---

### Chat Primitive (`src/primitives/chat.ts`)

**Responsibility:** Frontend chat interface with streaming responses.

**Behavior:**
- **Always streams** — Returns `Response` via `toUIMessageStreamResponse()`
- Converts `UIMessage[]` (from `useChat`) to `ModelMessage[]`
- Supports `onFinish` and `onError` lifecycle callbacks

**Key Interfaces:**
- `chatPrimitive(config: StepConfig, context: ExecutionContext): Promise<Response>`

**Dependencies:** `ai` (streamText, convertToModelMessages), `providerRegistry`, `toolRegistry`, `callbackRegistry`

**Use for:** API routes serving `useChat` frontend hooks.

---

### LLM Primitive (`src/primitives/llm.ts`)

**Responsibility:** Workflow LLM calls with complete results for chaining.

**Behavior:**
- **Never streams** — Returns `{ text, usage }` object
- Uses `ModelMessage[]` format directly (no conversion)
- Result stored in `context.variables` for subsequent steps

**Key Interfaces:**
- `llmPrimitive(config: StepConfig, context: ExecutionContext): Promise<Record<string, unknown>>`

**Dependencies:** `ai` (generateText), `providerRegistry`, `toolRegistry`

**Use for:** Internal workflows, `call-agent`, multi-step pipelines.

---

### Call Agent Primitive (`src/primitives/call-agent.ts`)

**Responsibility:** Invoke another YAML workflow as a subroutine.

**Behavior:**
- Loads and executes another agent's workflow
- Passes resolved input to the sub-agent
- Returns sub-agent's result for workflow chaining

**Key Interfaces:**
- `callAgentPrimitive(config: StepConfig, context: ExecutionContext): Promise<Response | Record<string, unknown>>`

**Dependencies:** `loadYaml`, `WorkflowExecutor`, `resolveVariables`

---

### Design Decision: Semantic Primitive Separation

**Why `chat` converts messages and `llm` doesn't:**

The AI SDK v6 has two message formats:
- `UIMessage[]` — Frontend format from `useChat` hook (with `parts` array)
- `ModelMessage[]` — Backend format for `streamText`/`generateText` (with `content`)

| Primitive | Input Format | Conversion | Reason |
|-----------|--------------|------------|--------|
| `chat` | `UIMessage[]` | `convertToModelMessages()` | Data comes from `useChat` frontend |
| `llm` | `ModelMessage[]` | None | Data comes from workflow steps or YAML |

**Why no `stream` property in YAML:**

The streaming behavior is **semantically determined by the primitive type**, not a configuration flag:
- `type: "chat"` → Always streams (for responsive frontend UX)
- `type: "llm"` → Never streams (result needed for workflow chaining)

This design is cleaner than a `stream: true/false` flag because:
1. Prevents misconfiguration (e.g., streaming in a multi-step workflow)
2. Makes intent explicit in the YAML
3. Aligns with AI SDK v6 patterns (`streamText` vs `generateText`)

---

### Output Primitive (`src/primitives/output.ts`)

**Responsibility:** Deterministic JSON transform using variable resolution.

**Key Interfaces:**
- `outputPrimitive(config: StepConfig, context: ExecutionContext): Promise<Record<string, unknown>>`

**Dependencies:** `resolveVariables`

---

## Providers

### Provider Registry (`src/providers/index.ts`)

**Responsibility:** Register and provide LLM provider implementations.

**Key Interfaces:**
- `providerRegistry: Record<string, ProviderImplementation>`
- `registerProvider(name: string, implementation: ProviderImplementation): void`
- `createModel(provider: string, config: ProviderConfig): LanguageModel`

**Built-in Providers:**

| Provider | Package | Environment Variables |
|----------|---------|----------------------|
| `google` | `@ai-sdk/google` | `GEMINI_API_KEY` |
| `bedrock` | `@ai-sdk/amazon-bedrock` | `AWS_REGION`, AWS credentials |
| `openrouter` | `@ai-sdk/openai` | `OPENROUTER_API_KEY` |

---

## Tools

### Tool Registry (`src/tools/index.ts`)

**Responsibility:** Register and provide tool implementations for LLM primitives.

**Key Interfaces:**
- `toolRegistry: Record<string, ToolImplementation>`
- `registerTool(name: string, implementation: ToolImplementation): void`

**Built-in Tools:**
- `calculator` — Evaluate mathematical expressions
- `getCurrentTime` — Get current ISO timestamp

---

## Server

### Server Handler (`src/server/handler.ts`)

**Responsibility:** Factory for creating Next.js API route handlers.

**Key Interfaces:**
- `createBeddelHandler(options?: BeddelHandlerOptions): BeddelHandler`

**Options:**
- `agentsPath` — Directory for user agents (default: `'src/agents'`)
- `disableBuiltinAgents` — Disable built-in agents (default: `false`)

---

## Built-in Agents (`src/agents/`)

Pre-configured agents bundled with the package:

| Agent | Type | Description |
|-------|------|-------------|
| `assistant.yaml` | `chat` | Google Gemini streaming assistant |
| `assistant-bedrock.yaml` | `chat` | Amazon Bedrock assistant |
| `assistant-openrouter.yaml` | `chat` | OpenRouter free tier assistant |
| `text-generator.yaml` | `llm` | Text generation (non-streaming) |
| `multi-step-assistant.yaml` | `call-agent` + `llm` | 4-step analysis pipeline |

---

## Component Diagram

```mermaid
graph TB
    subgraph "Entry Points"
        Index["index.ts"]
        Server["server.ts"]
        Client["client.ts (types)"]
    end
    
    subgraph "Core"
        Parser["parser.ts"]
        Executor["workflow.ts"]
        VarResolver["variable-resolver.ts"]
    end
    
    subgraph "Primitives"
        Registry["index.ts (handlerRegistry)"]
        LLMCore["llm-core.ts (shared)"]
        ChatPrim["chat.ts (streaming)"]
        LLMPrim["llm.ts (blocking)"]
        OutputPrim["output.ts"]
        CallAgent["call-agent.ts"]
    end
    
    subgraph "Providers"
        ProvReg["index.ts (providerRegistry)"]
        Google["google"]
        Bedrock["bedrock"]
        OpenRouter["openrouter"]
    end
    
    subgraph "Tools"
        ToolReg["index.ts (toolRegistry)"]
        Calc["calculator"]
        Time["getCurrentTime"]
    end
    
    subgraph "Built-in Agents"
        Assistant["assistant.yaml"]
        TextGen["text-generator.yaml"]
        MultiStep["multi-step-assistant.yaml"]
    end
    
    Index --> Parser
    Index --> Executor
    Index --> Registry
    Server --> Handler["handler.ts"]
    Handler --> Parser
    Handler --> Executor
    Handler --> Assistant
    Executor --> Registry
    Executor --> VarResolver
    Registry --> ChatPrim
    Registry --> LLMPrim
    Registry --> OutputPrim
    Registry --> CallAgent
    ChatPrim --> LLMCore
    LLMPrim --> LLMCore
    LLMCore --> ToolReg
    ChatPrim --> ProvReg
    LLMPrim --> ProvReg
    CallAgent --> Parser
    CallAgent --> Executor
    ProvReg --> Google
    ProvReg --> Bedrock
    ProvReg --> OpenRouter
```
