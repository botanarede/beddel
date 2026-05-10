# @beddel/observability-langfuse

Langfuse-backed ITracer adapter for the Beddel TypeScript SDK.

## Overview

Implements the `ITracer` port using `langfuse@^3` for full-fidelity LLM observability
with span trees, cost tracking, and latency histograms in the Langfuse dashboard.

Gracefully degrades: all tracing methods catch exceptions silently so that tracing
never breaks the workflow.

## Install

```bash
pnpm add @beddel/observability-langfuse
```

## Usage

```typescript
import { LangfuseTracerAdapter } from '@beddel/observability-langfuse';

const tracer = new LangfuseTracerAdapter({
  publicKey: process.env.LANGFUSE_PUBLIC_KEY,
  secretKey: process.env.LANGFUSE_SECRET_KEY,
  baseUrl: 'https://cloud.langfuse.com',
});

const span = tracer.startSpan('my-workflow', { model: 'gpt-4o' });
// ... do work ...
tracer.endSpan(span, { tokens: 150 });

await tracer.shutdown();
```

## kit.yaml

```yaml
name: observability-langfuse-kit
version: "0.1.0"
adapters:
  - port: ITracer
    implementation: LangfuseTracerAdapter
```

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `publicKey` | `string` | `process.env.LANGFUSE_PUBLIC_KEY` | Langfuse public key |
| `secretKey` | `string` | `process.env.LANGFUSE_SECRET_KEY` | Langfuse secret key |
| `baseUrl` | `string` | `"https://cloud.langfuse.com"` | Langfuse server URL |
| `flushOnShutdown` | `boolean` | `true` | Flush spans on shutdown |

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| BEDDEL-ADAPT-541 | LangfuseInitFailed | Cannot initialize Langfuse client |
| BEDDEL-ADAPT-542 | LangfuseSpanCreateFailed | Span creation failed |
| BEDDEL-ADAPT-543 | LangfuseServerUnreachable | Langfuse server not reachable |
| BEDDEL-ADAPT-544 | LangfuseShutdownFailed | Flush/shutdown failed |
