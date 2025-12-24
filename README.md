# Beddel Protocol

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![npm version](https://img.shields.io/badge/npm-1.0.0-brightgreen.svg)](https://www.npmjs.com/package/beddel)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org/)
[![AI SDK](https://img.shields.io/badge/AI%20SDK-v6-purple.svg)](https://sdk.vercel.ai/)

**Beddel Protocol** is a declarative **Sequential Pipeline Executor** that parses YAML workflow definitions and executes steps sequentially. Built on the Vercel AI SDK v6, it provides native streaming support and extensible primitives.

## Features

- 🔄 **Sequential Pipeline Execution** — Define workflows as YAML, execute steps in order
- 🌊 **Native Streaming** — First-class `streamText` support with `useChat` compatibility
- 🔌 **Extensible Primitives** — Register custom step types, tools, and callbacks
- 🔒 **Security First** — YAML parsing with `FAILSAFE_SCHEMA` prevents code execution
- 📦 **Bundle Separation** — Three entry points for server, client, and full API access

## Installation

```bash
npm install beddel
# or
pnpm add beddel
# or
yarn add beddel
```

## Quick Start

### 1. Create API Route

```typescript
// app/api/beddel/chat/route.ts
import { createBeddelHandler } from 'beddel/server';

export const POST = createBeddelHandler({
  agentsPath: 'src/agents'  // Optional, default: 'src/agents'
});
```

### 2. Create YAML Agent

```yaml
# src/agents/assistant.yaml
metadata:
  name: "Streaming Assistant"
  version: "1.0.0"

workflow:
  - id: "chat-interaction"
    type: "llm"
    config:
      model: "gemini-2.0-flash-exp"
      stream: true
      system: "You are a helpful assistant."
      messages: "$input.messages"
```

### 3. Set Environment Variable

```bash
GEMINI_API_KEY=your_api_key_here
```

### 4. Use with React (useChat)

```tsx
'use client';
import { useChat } from '@ai-sdk/react';

export default function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat({
    api: '/api/beddel/chat',
    body: { agentId: 'assistant' },
  });

  return (
    <div>
      {messages.map((m) => (
        <div key={m.id}>{m.role}: {m.content}</div>
      ))}
      <form onSubmit={handleSubmit}>
        <input value={input} onChange={handleInputChange} />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}
```

## Entry Points

| Import Path | Purpose | Environment |
|-------------|---------|-------------|
| `beddel` | Full API: `loadYaml`, `WorkflowExecutor`, registries | Server only |
| `beddel/server` | `createBeddelHandler` for Next.js API routes | Server only |
| `beddel/client` | Type-only exports (browser-safe) | Client/Server |

> ⚠️ **Important:** Never import `beddel` or `beddel/server` in client components. Use `beddel/client` for type imports.

## Extensibility

Beddel follows the **Expansion Pack Pattern** for extensibility:

### Register Custom Primitives

```typescript
import { registerPrimitive } from 'beddel';

registerPrimitive('http-fetch', async (config, context) => {
  const response = await fetch(config.url);
  return { data: await response.json() };
});
```

### Register Custom Tools

```typescript
import { registerTool } from 'beddel';
import { z } from 'zod';

registerTool('weatherLookup', {
  description: 'Get weather for a city',
  parameters: z.object({ city: z.string() }),
  execute: async ({ city }) => fetchWeather(city),
});
```

### Register Lifecycle Callbacks

```typescript
import { registerCallback } from 'beddel';

registerCallback('persistConversation', async ({ text, usage }) => {
  await db.saveMessage(text, usage);
});
```

## YAML Workflow Structure

```yaml
metadata:
  name: "Agent Name"
  version: "1.0.0"

workflow:
  - id: "step-1"
    type: "llm"
    config:
      model: "gemini-2.0-flash-exp"
      stream: true
      system: "System prompt"
      messages: "$input.messages"
      tools:
        - name: "calculator"
      onFinish: "callbackName"
    result: "stepOutput"
```

### Variable Resolution

| Pattern | Description | Example |
|---------|-------------|---------|
| `$input.*` | Access request input | `$input.messages` |
| `$stepResult.varName.*` | Access step result | `$stepResult.llmOutput.text` |

## Built-in Tools

| Tool | Description |
|------|-------------|
| `calculator` | Evaluate mathematical expressions |
| `getCurrentTime` | Get current ISO timestamp |

## AI SDK v6 Compatibility

Beddel is fully compatible with Vercel AI SDK v6:

- **Frontend:** `useChat` sends `UIMessage[]` with `{ parts: [...] }` format
- **Backend:** `streamText`/`generateText` expects `ModelMessage[]` with `{ content: ... }`
- **Automatic Conversion:** `convertToModelMessages()` bridges the gap
- **Streaming:** `toUIMessageStreamResponse()` returns the correct format for `useChat`

## Technology Stack

| Category | Technology | Version |
|----------|------------|---------|
| Language | TypeScript | 5.x |
| Runtime | Node.js / Edge | 20+ |
| AI Core | `ai` | 6.x |
| AI Provider | `@ai-sdk/google` | 3.x |
| Validation | `zod` | 3.x |
| YAML Parser | `js-yaml` | 4.x |

## Documentation

Detailed documentation is available in [`docs/`](./docs/):

- [API Reference](./docs/architecture/api-reference.md)
- [Components](./docs/architecture/components.md)
- [Core Workflows](./docs/architecture/core-workflows.md)
- [High-Level Architecture](./docs/architecture/high-level-architecture.md)

## License

[MIT](LICENSE)
