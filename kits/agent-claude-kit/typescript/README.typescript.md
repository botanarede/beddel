# @beddel/agent-claude

Anthropic Claude agent adapter for the Beddel TypeScript SDK.

## Overview

Implements the `IAgentAdapter` port by composing `@anthropic-ai/sdk` directly (per AD-1).
Supports tool_use loops, structured output via JSON-mode, and sandbox permission filtering.

## Install

```bash
pnpm add @beddel/agent-claude
```

## Usage

```typescript
import { ClaudeAgentAdapter } from '@beddel/agent-claude';

const adapter = new ClaudeAgentAdapter({
  apiKey: process.env.ANTHROPIC_API_KEY,
  model: 'claude-sonnet-4',
  maxTurns: 25,
  timeoutMs: 300_000,
});

const result = await adapter.execute('Analyze this code', {
  tools: ['read_file', 'write_file'],
  sandbox: 'workspace-write',
});
console.log(result.output);
```

## kit.yaml

```yaml
name: agent-claude-kit
version: "0.1.0"
adapters:
  - port: IAgentAdapter
    implementation: ClaudeAgentAdapter
```

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `apiKey` | `string` | `process.env.ANTHROPIC_API_KEY` | Anthropic API key |
| `model` | `string` | `"claude-sonnet-4"` | Default model |
| `maxTurns` | `number` | `25` | Max tool-use loop iterations |
| `timeoutMs` | `number` | `300000` | Request timeout in milliseconds |
| `fileMutationTools` | `string[]` | `["write_file","edit_file","create_file"]` | Tools tracked for filesChanged |

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| BEDDEL-ADAPT-505 | ClaudeMaxTurnsExceeded | Tool-use cycle exceeded `maxTurns` |
| BEDDEL-ADAPT-506 | ClaudeStructuredOutputInvalid | Response failed Zod validation |
| BEDDEL-ADAPT-507 | ClaudeApiKeyMissing | No API key provided |
| BEDDEL-ADAPT-508 | ClaudeRateLimited | HTTP 429 from Anthropic |
| BEDDEL-ADAPT-509 | ClaudeTimeout | Request exceeded `timeoutMs` |
