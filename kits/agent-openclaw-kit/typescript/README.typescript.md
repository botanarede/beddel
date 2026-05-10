# @beddel/agent-openclaw

OpenClaw Gateway HTTP agent adapter for the Beddel TypeScript SDK.

## Overview

Implements the `IAgentAdapter` port by sending `POST /v1/chat/completions` to the
OpenClaw Gateway HTTP API using Node 20's builtin `fetch`. Zero runtime dependencies.

## Install

```bash
pnpm add @beddel/agent-openclaw
```

## Usage

```typescript
import { OpenClawAgentAdapter } from '@beddel/agent-openclaw';

const adapter = new OpenClawAgentAdapter({
  gatewayUrl: 'http://localhost:3000',
  agent: 'architect',
  model: 'gpt-4o',
  timeoutMs: 120_000,
});

const result = await adapter.execute('Analyze this codebase');
console.log(result.output);
```

## kit.yaml

```yaml
name: agent-openclaw-kit
version: "0.1.0"
adapters:
  - port: IAgentAdapter
    implementation: OpenClawAgentAdapter
```

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `gatewayUrl` | `string` | `"http://localhost:3000"` | OpenClaw Gateway base URL |
| `agent` | `string` | `"main"` | Agent selection (`main`, `architect`, `digger`, etc.) |
| `model` | `string` | `undefined` | Default model override |
| `timeoutMs` | `number` | `120000` | Request timeout in milliseconds |

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| BEDDEL-ADAPT-500 | OpenClawConnectionFailed | Cannot reach OpenClaw Gateway |
| BEDDEL-ADAPT-501 | OpenClawTimeout | Gateway request exceeded `timeoutMs` |
| BEDDEL-ADAPT-502 | OpenClawHttpError | Gateway returned a non-2xx response |
| BEDDEL-ADAPT-503 | OpenClawInvalidResponse | Response body was not parseable |
| BEDDEL-ADAPT-504 | OpenClawStreamParseFailed | SSE stream emitted a malformed event |
