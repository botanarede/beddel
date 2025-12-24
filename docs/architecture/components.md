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

### Primitive Handler Registry (`src/primitives/index.ts`)

**Responsibility:** Register and lookup primitive handlers by step type.

**Key Interfaces:**
- `handlerRegistry: Record<string, PrimitiveHandler>`
- `registerPrimitive(type: string, handler: PrimitiveHandler): void`

**Dependencies:** `llm`, `output-generator`, `call-agent` primitives

**Technology Stack:** Registry pattern implementation.

---

### LLM Primitive (`src/primitives/llm.ts`)

**Responsibility:** Execute LLM calls with dual-mode support (streaming/blocking) and lifecycle hooks.

**Key Interfaces:**
- `llmPrimitive(config: StepConfig, context: ExecutionContext): Promise<Response | object>`
- `mapTools(toolDefinitions): ToolSet` - Maps YAML tool definitions to SDK tools
- `registerCallback(name: string, fn: CallbackFn): void` - Register lifecycle callbacks
- `callbackRegistry: Record<string, CallbackFn>` - Stores registered callbacks

**Dependencies:** `ai`, `@ai-sdk/google`, `toolRegistry`, `callbackRegistry`

**Technology Stack (AI SDK v6):**
- `streamText()` for streaming mode → `result.toUIMessageStreamResponse()`
- `generateText()` for blocking mode → `{ text, usage }`
- `convertToModelMessages()` for UIMessage[] → ModelMessage[] conversion
- `dynamicTool()` for registry-based tool creation
- `stopWhen: stepCountIs(5)` for multi-step tool loops
- `onFinish` / `onError` lifecycle callbacks

**AI SDK v6 Message Format Compatibility:**
- Frontend (`useChat`) sends `UIMessage[]` with `{ parts: [...] }` format
- Backend (`streamText`/`generateText`) expects `ModelMessage[]` with `{ content: ... }`
- `convertToModelMessages()` bridges this gap automatically
- `toUIMessageStreamResponse()` returns the correct stream format for `useChat`

---

### Output Primitive (`src/primitives/output.ts`)

**Responsibility:** Deterministic JSON transform using variable resolution.

**Key Interfaces:**
- `outputPrimitive(config: StepConfig, context: ExecutionContext): Promise<Record<string, unknown>>`

**Dependencies:** `resolveVariables`

**Technology Stack:** Pure TypeScript.

---

### Call Agent Primitive (Placeholder)

**Responsibility:** Invoke another YAML workflow as a subroutine.

**Status:** 🚧 Coming Soon — currently registered as placeholder handler.

---

### Tool Registry (`src/tools/index.ts`)

**Responsibility:** Register and provide tool implementations for LLM primitives.

**Key Interfaces:**
- `toolRegistry: Record<string, ToolImplementation>`
- `registerTool(name: string, implementation: ToolImplementation): void`
- `ToolImplementation: { description, parameters (Zod), execute }`

**Built-in Tools:**
- `calculator` - Evaluate mathematical expressions
- `getCurrentTime` - Get current ISO timestamp

**Dependencies:** `zod`

**Technology Stack:** Zod schemas for parameter validation.

---

### Server Handler (`src/server/handler.ts`)

**Responsibility:** Factory for creating Next.js API route handlers.

**Key Interfaces:**
- `createBeddelHandler(options?: BeddelHandlerOptions): (request: NextRequest) => Promise<Response>`
- `BeddelHandlerOptions: { agentsPath?: string }`

**Dependencies:** `loadYaml`, `WorkflowExecutor`, `next/server`

**Technology Stack:** Next.js App Router API Routes.

**Usage:**
```typescript
// app/api/beddel/chat/route.ts
import { createBeddelHandler } from 'beddel/server';

export const POST = createBeddelHandler({
  agentsPath: 'src/agents'  // Default: 'src/agents'
});
```

---

## Extensibility APIs

Beddel follows the **Expansion Pack Pattern** for extensibility:

### `registerPrimitive(type, handler)`

Add custom step types to the workflow engine.

```typescript
import { registerPrimitive } from 'beddel';

registerPrimitive('http-fetch', async (config, context) => {
  const response = await fetch(config.url);
  return { data: await response.json() };
});
```

### `registerTool(name, implementation)`

Add custom tools for LLM function calling.

```typescript
import { registerTool } from 'beddel';
import { z } from 'zod';

registerTool('weatherLookup', {
  description: 'Get weather for a city',
  parameters: z.object({ city: z.string() }),
  execute: async ({ city }) => fetchWeather(city),
});
```

### `registerCallback(name, fn)`

Add lifecycle hooks for streaming completion.

```typescript
import { registerCallback } from 'beddel';

registerCallback('persistConversation', async ({ text, usage }) => {
  await db.saveMessage(text, usage);
});
```

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
        LLMPrim["llm.ts"]
        OutputPrim["output.ts"]
        CallAgent["call-agent (placeholder)"]
    end
    
    subgraph "Tools"
        ToolReg["index.ts (toolRegistry)"]
        Calc["calculator"]
        Time["getCurrentTime"]
    end
    
    subgraph "Server"
        Handler["handler.ts"]
    end
    
    Index --> Parser
    Index --> Executor
    Index --> Registry
    Index --> ToolReg
    Server --> Handler
    Handler --> Parser
    Handler --> Executor
    Executor --> Registry
    Executor --> VarResolver
    Registry --> LLMPrim
    Registry --> OutputPrim
    Registry --> CallAgent
    LLMPrim --> ToolReg
    ToolReg --> Calc
    ToolReg --> Time
```

