# @beddel/observability-otel

OpenTelemetry tracing adapter for the Beddel TypeScript SDK. Implements the `ITracer` port interface, enabling automatic span creation for workflow steps, LLM calls, and error recording.

## Install

```bash
pnpm add @beddel/observability-otel @opentelemetry/api
pnpm add -D @opentelemetry/sdk-node @opentelemetry/sdk-trace-base
```

## Usage

```typescript
import { PrimitiveRegistry, WorkflowExecutor, registerBuiltins } from '@beddel/core';
import { OTelTracer } from '@beddel/observability-otel';

const registry = new PrimitiveRegistry();
registerBuiltins(registry);

const executor = new WorkflowExecutor(registry, {
  tracer: new OTelTracer('my-service'),
});
```

## kit.yaml

```yaml
name: observability-otel-kit
targets:
  typescript:
    package: "@beddel/observability-otel"
    dependencies:
      - "@opentelemetry/api: ^1.9"
    adapters:
      - port: ITracer
        target: "./ts/tracer.ts:OTelTracer"
```

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `tracerName` | `string` | `"beddel"` | OpenTelemetry tracer name |

The OTel SDK must be initialized in your application (e.g., via `@opentelemetry/sdk-node`). The tracer gracefully degrades to no-ops if OTel is not available.
