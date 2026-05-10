# @beddel/serve-express

Express.js HTTP server adapter for the Beddel TypeScript SDK. Exposes workflow execution via a REST API with optional Server-Sent Events (SSE) streaming.

## Install

```bash
pnpm add @beddel/serve-express
```

## Usage

```typescript
import { PrimitiveRegistry, WorkflowExecutor, registerBuiltins, parseWorkflow } from '@beddel/core';
import { createBeddelServer } from '@beddel/serve-express';

const registry = new PrimitiveRegistry();
registerBuiltins(registry);
const executor = new WorkflowExecutor(registry, { llmProvider: myProvider });

const workflows = new Map();
workflows.set('hello', parseWorkflow(`
  id: hello
  name: Hello
  steps:
    - id: greet
      primitive: llm
      config:
        model: gpt-4o-mini
        prompt: "Say hello to $input.name"
`));

const app = await createBeddelServer({
  executor,
  workflows,
  cors: true,
});

app.listen(3000, () => console.log('Beddel server on :3000'));
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/workflows` | List registered workflows |
| `POST` | `/api/v1/workflows/:id/execute` | Execute a workflow |
| `POST` | `/api/v1/workflows/:id/stream` | Execute with SSE streaming |

## kit.yaml

```yaml
name: serve-express-kit
targets:
  typescript:
    package: "@beddel/serve-express"
    dependencies:
      - "express: ^4.21"
    tools:
      - name: serve-express
        target: "./src/server.ts:createBeddelServer"
```

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `executor` | `WorkflowExecutor` | required | Beddel workflow executor instance |
| `workflows` | `Map<string, Workflow>` | required | Workflow registry |
| `port` | `number` | `3000` | Server port |
| `basePath` | `string` | `"/api/v1"` | API base path |
| `cors` | `boolean` | `false` | Enable CORS headers |
