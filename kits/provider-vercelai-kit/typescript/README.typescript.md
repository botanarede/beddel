# @beddel/provider-vercelai

Vercel AI SDK multi-provider LLM adapter for the Beddel TypeScript SDK. Implements the `ILLMProvider` port interface, enabling workflows to use any Vercel AI SDK-supported provider (OpenAI, Anthropic, Google, etc.) without changing workflow YAML.

## Install

```bash
pnpm add @beddel/provider-vercelai
```

## Usage

```typescript
import { PrimitiveRegistry, WorkflowExecutor, registerBuiltins, parseWorkflow } from '@beddel/core';
import { VercelAIAdapter } from '@beddel/provider-vercelai';

const registry = new PrimitiveRegistry();
registerBuiltins(registry);

const executor = new WorkflowExecutor(registry, {
  llmProvider: new VercelAIAdapter(),
});

const workflow = parseWorkflow(`
  id: hello
  name: Hello
  steps:
    - id: greet
      primitive: llm
      config:
        model: openai:gpt-4o-mini
        prompt: "Say hello"
`);

const result = await executor.execute(workflow);
```

## kit.yaml

```yaml
name: provider-vercelai-kit
version: "0.1.0"
description: "Vercel AI SDK multi-provider LLM adapter for TypeScript"
targets:
  typescript:
    package: "@beddel/provider-vercelai"
    dependencies:
      - "ai: ^4.0"
      - "@ai-sdk/openai: ^1.0"
    adapters:
      - port: ILLMProvider
        target: "./src/adapter.ts:VercelAIAdapter"
```

## Supported Providers

| Provider | Model prefix | API key env var |
|----------|-------------|-----------------|
| OpenAI | `openai:` | `OPENAI_API_KEY` |
| Anthropic | `anthropic:` | `ANTHROPIC_API_KEY` |
| Google | `google:` | `GOOGLE_GENERATIVE_AI_API_KEY` |

Model strings without a provider prefix default to OpenAI.
