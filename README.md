# Beddel Protocol

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![npm version](https://img.shields.io/badge/npm-1.0.4-brightgreen.svg)](https://www.npmjs.com/package/beddel)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org/)
[![AI SDK](https://img.shields.io/badge/AI%20SDK-v6-purple.svg)](https://sdk.vercel.ai/)

**Beddel Protocol** is a declarative **Sequential Pipeline Executor** that parses YAML workflow definitions and executes steps sequentially. Built on the Vercel AI SDK v6, it provides native streaming support and extensible primitives.

## Features

- 🔄 **Sequential Pipeline Execution** — Define workflows as YAML, execute steps in order
- 🌊 **Native Streaming** — First-class `streamText` support via `chat` primitive with `useChat` compatibility
- 🔌 **Extensible Primitives** — Register custom step types, tools, and callbacks
- 🔒 **Security First** — YAML parsing with `FAILSAFE_SCHEMA` prevents code execution
- 📦 **Bundle Separation** — Three entry points for server, client, and full API access
- 🌐 **Multi-Provider** — Built-in support for Google Gemini, Amazon Bedrock, and OpenRouter (400+ models)
- 🔀 **Semantic Primitives** — `chat` for streaming frontend, `llm` for blocking workflows

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

#### Example 1: Google Gemini (Default Provider)

```yaml
# src/agents/assistant.yaml
metadata:
  name: "Streaming Assistant"
  version: "1.0.0"

workflow:
  - id: "chat-interaction"
    type: "chat"
    config:
      provider: "google"
      model: "gemini-2.0-flash-exp"
      system: "You are a helpful assistant."
      messages: "$input.messages"
```

#### Example 2: Amazon Bedrock (Llama 3.2)

```yaml
# src/agents/assistant-bedrock.yaml
metadata:
  name: "Bedrock Assistant"
  version: "1.0.0"
  description: "Simple assistant using Llama 3.2 1B (lightweight)"

workflow:
  - id: "chat"
    type: "chat"
    config:
      provider: "bedrock"
      model: "us.meta.llama3-2-1b-instruct-v1:0"
      system: |
        You are a helpful, friendly assistant. Be concise and direct.
        Answer in the same language the user writes to you.
      messages: "$input.messages"
```

#### Example 3: OpenRouter (400+ Models)

```yaml
# src/agents/assistant-openrouter.yaml
metadata:
  name: "OpenRouter Assistant"
  version: "1.0.0"

workflow:
  - id: "chat"
    type: "chat"
    config:
      provider: "openrouter"
      model: "qwen/qwen3-14b:free"  # or any model from openrouter.ai/models
      system: "You are a helpful assistant."
      messages: "$input.messages"
```

### 3. Set Environment Variables

```bash
# For Google Gemini
GEMINI_API_KEY=your_api_key_here

# For Amazon Bedrock
AWS_REGION=us-east-1
AWS_BEARER_TOKEN_BEDROCK=your_bedrock_api_key
# Or use standard AWS credentials:
# AWS_ACCESS_KEY_ID=your_access_key
# AWS_SECRET_ACCESS_KEY=your_secret_key

# For OpenRouter
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 4. Use with React (useChat)

```tsx
'use client';
import { useChat } from '@ai-sdk/react';

export default function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat({
    api: '/api/beddel/chat',
    body: { agentId: 'assistant' },  // or 'assistant-bedrock'
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

## Built-in Providers

| Provider | Environment Variables | Default Model |
|----------|----------------------|---------------|
| `google` | `GEMINI_API_KEY` | `gemini-1.5-flash` |
| `bedrock` | `AWS_REGION`, `AWS_BEARER_TOKEN_BEDROCK` (or AWS credentials) | `anthropic.claude-3-haiku-20240307-v1:0` |
| `openrouter` | `OPENROUTER_API_KEY` | `qwen/qwen3-14b:free` |

> **Note:** The Bedrock provider requires `AWS_REGION` to be set (defaults to `us-east-1` if not provided).

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
    type: "chat"          # or "llm" for non-streaming workflows
    config:
      model: "gemini-2.0-flash-exp"
      system: "System prompt"
      messages: "$input.messages"
      tools:
        - name: "calculator"
      onFinish: "callbackName"
    result: "stepOutput"
```

### Primitive Types

| Type | Behavior | Use Case |
|------|----------|----------|
| `chat` | Always streaming, converts UIMessage | Frontend chat interfaces (`useChat`) |
| `llm` | Never streaming, returns complete result | Multi-step workflows, variable passing |
| `call-agent` | Invokes another agent | Sub-agent orchestration |
| `output-generator` | JSON template transform | Structured output generation |
| `mcp-tool` | Connects to MCP servers via SSE | External tool integration (GitMCP, Context7) |

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
- **Automatic Conversion:** `chat` primitive uses `convertToModelMessages()` to bridge the gap
- **Streaming:** `chat` primitive returns `toUIMessageStreamResponse()` for `useChat`
- **Blocking:** `llm` primitive uses `generateText()` for workflow steps

## Technology Stack

| Category | Technology | Version |
|----------|------------|---------|
| Language | TypeScript | 5.x |
| Runtime | Node.js / Edge | 20+ |
| AI Core | `ai` | 6.x |
| AI Provider | `@ai-sdk/google` | 3.x |
| AI Provider | `@ai-sdk/amazon-bedrock` | 4.x |
| AI Provider | `@ai-sdk/openai` | 1.x |
| MCP Client | `@modelcontextprotocol/sdk` | 1.x |
| Validation | `zod` | 3.x |
| YAML Parser | `js-yaml` | 4.x |

## Documentation

Detailed documentation is available in [`docs/`](./docs/):

- [API Reference](./docs/architecture/api-reference.md)
- [Components](./docs/architecture/components.md)
- [Core Workflows](./docs/architecture/core-workflows.md)
- [High-Level Architecture](./docs/architecture/high-level-architecture.md)

## Newsletter

[![Subscribe on Substack](https://img.shields.io/badge/Subscribe-Substack-orange?style=for-the-badge&logo=substack)](https://beddelprotocol.substack.com/subscribe)

## License

[MIT](LICENSE)
