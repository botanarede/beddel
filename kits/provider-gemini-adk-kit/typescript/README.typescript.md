# @beddel/provider-gemini-adk

Google Gemini ADK direct LLM adapter for the Beddel TypeScript SDK. Implements the `ILLMProvider` port interface for direct Gemini API access via `@google/generative-ai`, without the Vercel AI SDK indirection.

## Install

```bash
pnpm add @beddel/provider-gemini-adk
```

## Usage

```typescript
import { PrimitiveRegistry, WorkflowExecutor, registerBuiltins, parseWorkflow } from '@beddel/core';
import { GeminiADKAdapter } from '@beddel/provider-gemini-adk';

const registry = new PrimitiveRegistry();
registerBuiltins(registry);

const executor = new WorkflowExecutor(registry, {
  llmProvider: new GeminiADKAdapter(), // uses GEMINI_API_KEY env var
});

const workflow = parseWorkflow(`
  id: hello
  name: Hello
  steps:
    - id: greet
      primitive: llm
      config:
        model: gemini-2.0-flash
        prompt: "Say hello"
`);

const result = await executor.execute(workflow);
```

## kit.yaml

```yaml
name: provider-gemini-adk-kit
version: "0.1.0"
description: "Google Gemini ADK direct LLM adapter for TypeScript"
targets:
  typescript:
    package: "@beddel/provider-gemini-adk"
    dependencies:
      - "@google/generative-ai: ^0.24"
    adapters:
      - port: ILLMProvider
        target: "./src/adapter.ts:GeminiADKAdapter"
```

## Configuration

| Env var | Description |
|---------|-------------|
| `GEMINI_API_KEY` | Primary API key |
| `GOOGLE_API_KEY` | Fallback API key |

Model names can optionally include a `google:` or `gemini:` prefix, which is stripped before forwarding to the API.
