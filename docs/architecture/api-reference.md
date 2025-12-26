# API Reference

> **Beddel Protocol v1.0.0** — Complete API documentation for all public exports.

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
  return result; // Streaming response
}
return Response.json(result); // Blocking result
```

**Constructor:** `new WorkflowExecutor(yaml: ParsedYaml)`

**Methods:**
- `execute(input: unknown): Promise<Response | Record<string, unknown>>`

---

### Registries

#### `handlerRegistry: Record<string, PrimitiveHandler>`

Map of primitive step types to their handler functions.

**Built-in handlers:**
- `llm` — AI text generation (streaming/blocking)
- `output-generator` — Deterministic JSON transform
- `call-agent` — Sub-agent invocation (placeholder)

#### `toolRegistry: Record<string, ToolImplementation>`

Map of tool names to their implementations for LLM function calling.

**Built-in tools:**
- `calculator` — Evaluate mathematical expressions
- `getCurrentTime` — Get current ISO timestamp

#### `providerRegistry: Record<string, ProviderImplementation>`

Map of provider names to their implementations for LLM model creation.

**Built-in providers:**
- `google` — Google Gemini via `@ai-sdk/google` (requires `GEMINI_API_KEY`)
- `bedrock` — Amazon Bedrock via `@ai-sdk/amazon-bedrock` (auto-detects AWS credentials)

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

Register a lifecycle callback for streaming hooks.

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

const model = createModel('google', { model: 'gemini-1.5-flash' });
// Or use bedrock
const bedrockModel = createModel('bedrock', { model: 'anthropic.claude-3-haiku-20240307-v1:0' });
```

**Throws:** Error if provider is not found, listing available providers.

---

## `beddel/server`

### `createBeddelHandler(options?: BeddelHandlerOptions)`

Factory function for creating Next.js API route handlers.

```typescript
// app/api/beddel/chat/route.ts
import { createBeddelHandler } from 'beddel/server';

export const POST = createBeddelHandler({
  agentsPath: 'src/agents'  // Optional, default: 'src/agents'
});
```

**Options:**

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `agentsPath` | `string` | `'src/agents'` | Directory containing YAML agent files |

**Request Body:**

The request body accepts messages in AI SDK v6 `UIMessage[]` format (from `useChat`):

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

> **AI SDK v6 Compatibility:** The handler automatically converts `UIMessage[]` (frontend format with `parts`) to `ModelMessage[]` (backend format with `content`) using `convertToModelMessages()`. The streaming response uses `toUIMessageStreamResponse()` for proper `useChat` integration.

---

## `beddel/client`

Type-only exports safe for client-side bundles (no Node.js dependencies).

### Types

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

## Type Definitions

### `ParsedYaml`

```typescript
interface ParsedYaml {
  metadata: YamlMetadata;
  workflow: WorkflowStep[];
}
```

### `YamlMetadata`

```typescript
interface YamlMetadata {
  name: string;
  version: string;
}
```

### `WorkflowStep`

```typescript
interface WorkflowStep {
  id: string;
  type: string;  // 'llm' | 'output-generator' | 'call-agent' | custom
  config: StepConfig;
  result?: string;  // Variable name to store step result
}
```

### `StepConfig`

```typescript
interface StepConfig {
  [key: string]: unknown;  // Step-specific configuration
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

### `ToolImplementation`

```typescript
interface ToolImplementation {
  description: string;
  parameters: z.ZodSchema;
  execute: (args: Record<string, unknown>) => Promise<Record<string, unknown>>;
}
```

### `CallbackFn`

```typescript
type CallbackFn = (payload: Record<string, unknown>) => void | Promise<void>;
```

### `ProviderImplementation`

```typescript
interface ProviderImplementation {
  createModel: (config: ProviderConfig) => LanguageModel;
}
```

### `ProviderConfig`

```typescript
interface ProviderConfig {
  model: string;
  [key: string]: unknown;
}
```

---

## AI SDK v6 Compatibility

Beddel is fully compatible with Vercel AI SDK v6 message formats:

### Message Format Conversion

| Source | Format | Structure |
|--------|--------|-----------|
| Frontend (`useChat`) | `UIMessage[]` | `{ role, parts: [{ type: "text", text }] }` |
| Backend (`streamText`) | `ModelMessage[]` | `{ role, content }` |

The LLM primitive automatically handles this conversion:

```typescript
// Internal conversion flow
const rawMessages = resolveVariables(config.messages, context) as UIMessage[];
const messages = await convertToModelMessages(rawMessages);
```

### Streaming Response

For streaming mode, `toUIMessageStreamResponse()` returns the correct format for `useChat`:

```typescript
// Streaming mode returns UI-compatible stream
return result.toUIMessageStreamResponse();
```

---

## Change Log

| Date | Version | Description |
|------|---------|-------------|
| 2024-12-24 | 1.0.0 | Initial API reference |
| 2024-12-24 | 1.0.1 | AI SDK v6 compatibility: UIMessage/ModelMessage conversion |
| 2024-12-25 | 1.0.2 | Provider registry: registerProvider, createModel, bedrock support |
