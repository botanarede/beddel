# API Reference

> **Beddel Protocol v1.0.4** — Complete API documentation for all public exports.

---

## Entry Points

| Import Path | Purpose |
|-------------|---------|
| `beddel` | Full server API — core functions, registries, and extensibility |
| `beddel/server` | Server handler factory for Next.js API routes |
| `beddel/client` | Type-only exports for client-side usage |

---

## `beddel` (Main Entry)

### Core Functions

#### `loadYaml(path: string): Promise<ParsedYaml>`

Load and parse a YAML workflow file securely using `FAILSAFE_SCHEMA`.

```typescript
import { loadYaml } from 'beddel';

const yaml = await loadYaml('./src/agents/assistant.yaml');
console.log(yaml.metadata.name); // "Streaming Assistant"
```

#### `resolveVariables(template: unknown, context: ExecutionContext): unknown`

Resolve variable references (`$input.*`, `$stepResult.*`) in templates.

```typescript
import { resolveVariables } from 'beddel';

const resolved = resolveVariables('$input.messages', context);
```

---

### Classes

#### `WorkflowExecutor`

Sequential pipeline executor for YAML workflows.

```typescript
import { WorkflowExecutor, loadYaml } from 'beddel';

const yaml = await loadYaml('./src/agents/assistant.yaml');
const executor = new WorkflowExecutor(yaml);

// Execute with input data
const result = await executor.execute({ messages: [...] });

if (result instanceof Response) {
  return result; // Streaming response (from 'chat' primitive)
}
return Response.json(result); // Blocking result (from 'llm' primitive)
```

**Constructor:** `new WorkflowExecutor(yaml: ParsedYaml)`

**Methods:**
- `execute(input: unknown): Promise<Response | Record<string, unknown>>`

---

### Registries

#### `handlerRegistry: Record<string, PrimitiveHandler>`

Map of primitive step types to their handler functions.

**Built-in handlers:**
- `chat` — Frontend chat interface (always streaming, converts UIMessage)
- `llm` — Workflow LLM calls (never streaming, uses ModelMessage directly)
- `output-generator` — Deterministic JSON transform
- `call-agent` — Sub-agent invocation
- `mcp-tool` — External MCP server tool execution

#### `toolRegistry: Record<string, ToolImplementation>`

Map of tool names to their implementations for LLM function calling.

**Built-in tools:**
- `calculator` — Evaluate mathematical expressions
- `getCurrentTime` — Get current ISO timestamp

#### `providerRegistry: Record<string, ProviderImplementation>`

Map of provider names to their implementations for LLM model creation.

**Built-in providers:**
- `google` — Google Gemini via `@ai-sdk/google` (requires `GEMINI_API_KEY`)
- `bedrock` — Amazon Bedrock via `@ai-sdk/amazon-bedrock` (requires AWS credentials)
- `openrouter` — OpenRouter via `@ai-sdk/openai` (requires `OPENROUTER_API_KEY`, 400+ models)

---

### Extensibility Functions

#### `registerPrimitive(type: string, handler: PrimitiveHandler): void`

Register a custom primitive handler.

```typescript
import { registerPrimitive } from 'beddel';

registerPrimitive('http-fetch', async (config, context) => {
  const response = await fetch(config.url);
  return { data: await response.json() };
});
```

#### `registerTool(name: string, implementation: ToolImplementation): void`

Register a custom tool for LLM function calling.

```typescript
import { registerTool } from 'beddel';
import { z } from 'zod';

registerTool('weatherLookup', {
  description: 'Get weather for a city',
  parameters: z.object({ city: z.string() }),
  execute: async ({ city }) => fetchWeather(city),
});
```

#### `registerCallback(name: string, callback: CallbackFn): void`

Register a lifecycle callback for streaming hooks (used by `chat` primitive).

```typescript
import { registerCallback } from 'beddel';

registerCallback('persistConversation', async ({ text, usage }) => {
  await db.saveMessage(text, usage);
});
```

#### `registerProvider(name: string, implementation: ProviderImplementation): void`

Register a custom LLM provider for dynamic model selection.

```typescript
import { registerProvider } from 'beddel';
import { createOpenAI } from '@ai-sdk/openai';

registerProvider('openai', {
  createModel: (config) => {
    const openai = createOpenAI({ apiKey: process.env.OPENAI_API_KEY });
    return openai(config.model || 'gpt-4');
  },
});
```

#### `createModel(provider: string, config: ProviderConfig): LanguageModel`

Create a LanguageModel instance from a registered provider.

```typescript
import { createModel } from 'beddel';

const model = createModel('google', { model: 'gemini-2.0-flash-exp' });
const bedrockModel = createModel('bedrock', { model: 'anthropic.claude-3-haiku-20240307-v1:0' });
const openrouterModel = createModel('openrouter', { model: 'qwen/qwen3-coder:free' });
```

---

## `beddel/server`

### `createBeddelHandler(options?: BeddelHandlerOptions)`

Factory function for creating Next.js API route handlers.

```typescript
// app/api/beddel/chat/route.ts
import { createBeddelHandler } from 'beddel/server';

export const POST = createBeddelHandler({
  agentsPath: 'src/agents',      // Optional, default: 'src/agents'
  disableBuiltinAgents: false,   // Optional, default: false
});
```

**Options:**

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `agentsPath` | `string` | `'src/agents'` | Directory containing YAML agent files |
| `disableBuiltinAgents` | `boolean` | `false` | Disable built-in agents bundled with package |

**Request Body (for `chat` primitive):**

```json
{
  "agentId": "assistant",
  "messages": [
    {
      "role": "user",
      "parts": [{ "type": "text", "text": "Hello!" }]
    }
  ]
}
```

**Request Body (for `llm` primitive / workflows):**

```json
{
  "agentId": "text-generator",
  "messages": [
    { "role": "user", "content": "Generate text about cats" }
  ]
}
```

---

## `beddel/client`

Type-only exports safe for client-side bundles (no Node.js dependencies).

```typescript
import type {
  ParsedYaml,
  WorkflowStep,
  StepConfig,
  YamlMetadata,
  ExecutionContext,
  PrimitiveHandler,
} from 'beddel/client';
```

---

## Primitives

### `chat` Primitive

Frontend chat interface. **Always streams** responses for responsive UX.

**Use when:**
- Input comes from `useChat` frontend hook
- Messages are in `UIMessage` format (with `parts` array)

**Behavior:**
- Converts `UIMessage[]` to `ModelMessage[]` automatically
- Returns streaming `Response` via `toUIMessageStreamResponse()`
- Supports `onFinish` and `onError` lifecycle callbacks

```yaml
workflow:
  - id: "chat"
    type: "chat"
    config:
      provider: "google"
      model: "gemini-2.0-flash-exp"
      system: "You are a helpful assistant."
      messages: "$input.messages"
      onFinish: "saveConversation"
```

### `llm` Primitive

Workflow LLM calls. **Never streams** — returns complete result for workflow chaining.

**Use when:**
- Building multi-step workflows
- Result needs to be passed to next step
- Called from `call-agent` or other workflow steps

**Behavior:**
- Uses `ModelMessage[]` format directly (no conversion)
- Returns `{ text, usage }` object
- Result stored in `context.variables` for subsequent steps

```yaml
workflow:
  - id: "generate"
    type: "llm"
    config:
      provider: "google"
      model: "gemini-2.0-flash-exp"
      system: "Generate creative text."
      messages:
        - role: "user"
          content: "$input.prompt"
    result: "generatedText"
```

### `call-agent` Primitive

Invoke another agent's workflow as a sub-routine.

**Use when:**
- Composing complex workflows from simpler agents
- Reusing agent logic across multiple workflows

```yaml
workflow:
  - id: "generate-text"
    type: "call-agent"
    config:
      agentId: "text-generator"
      input:
        messages: "$input.messages"
    result: "generatedText"
```

### `output-generator` Primitive

Deterministic JSON transform using variable resolution.

```yaml
workflow:
  - id: "format-output"
    type: "output-generator"
    config:
      template:
        text: "$stepResult.generatedText.text"
        status: "completed"
    result: "finalOutput"
```

### `mcp-tool` Primitive

Connect to external MCP servers via SSE and execute tools.

**Use when:**
- Integrating with GitMCP for documentation fetching
- Connecting to Context7 or other MCP services
- Building agents that need external tool access

**Behavior:**
- Lazy loads MCP SDK (optional dependency)
- Connects via SSE transport
- Supports tool discovery via `list_tools`
- Returns `{ success, data, toolNames?, error? }`

**Config Options:**

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `url` | `string` | Yes | MCP server URL (SSE endpoint) |
| `tool` | `string` | Yes | Tool name to execute (or `list_tools`) |
| `arguments` | `object` | No | Arguments to pass to the tool |
| `timeout` | `number` | No | Timeout in ms (default: 30000) |

```yaml
workflow:
  - id: "fetch-docs"
    type: "mcp-tool"
    config:
      url: "https://gitmcp.io/vercel/ai"
      tool: "fetch_ai_documentation"
      arguments: {}
    result: "mcpDocs"
```

**Multi-step Example (MCP + Chat):**

```yaml
workflow:
  # Step 1: Fetch documentation from GitMCP
  - id: "fetch-docs"
    type: "mcp-tool"
    config:
      url: "https://gitmcp.io/owner/repo"
      tool: "fetch_repo_documentation"
      arguments: {}
    result: "mcpDocs"

  # Step 2: Respond using the fetched documentation
  - id: "respond"
    type: "chat"
    config:
      provider: "google"
      model: "gemini-2.0-flash-exp"
      system: |
        You have access to documentation:
        $stepResult.mcpDocs.data
      messages: "$input.messages"
```

---

## Built-in Agents

| Agent ID | Provider | Description |
|----------|----------|-------------|
| `assistant` | Google | Streaming chat assistant |
| `assistant-bedrock` | Bedrock | Llama 3.2 assistant |
| `assistant-openrouter` | OpenRouter | Free tier assistant |
| `assistant-gitmcp` | Google + MCP | Documentation assistant via GitMCP |
| `text-generator` | Google | Text generation (non-streaming) |
| `multi-step-assistant` | Google | 4-step analysis pipeline |

---

## Type Definitions

### `ParsedYaml`

```typescript
interface ParsedYaml {
  metadata: YamlMetadata;
  workflow: WorkflowStep[];
}
```

### `WorkflowStep`

```typescript
interface WorkflowStep {
  id: string;
  type: string;  // 'chat' | 'llm' | 'output-generator' | 'call-agent' | custom
  config: StepConfig;
  result?: string;
}
```

### `ExecutionContext`

```typescript
interface ExecutionContext {
  input: unknown;
  variables: Map<string, unknown>;
}
```

### `PrimitiveHandler`

```typescript
type PrimitiveHandler = (
  config: StepConfig,
  context: ExecutionContext
) => Promise<Response | Record<string, unknown>>;
```

---

## Change Log

| Date | Version | Description |
|------|---------|-------------|
| 2024-12-24 | 1.0.0 | Initial API reference |
| 2024-12-24 | 1.0.1 | AI SDK v6 compatibility |
| 2024-12-25 | 1.0.2 | Provider registry, bedrock support |
| 2024-12-26 | 1.0.3 | OpenRouter provider, built-in agents |
| 2024-12-27 | 1.0.4 | Separated `chat` and `llm` primitives, implemented `call-agent` |
| 2024-12-28 | 1.0.5 | Added `mcp-tool` primitive, `assistant-gitmcp` agent, system prompt variable resolution |
