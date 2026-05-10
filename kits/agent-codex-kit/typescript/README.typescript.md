# @beddel/agent-codex

OpenAI Codex Docker subprocess agent adapter for the Beddel TypeScript SDK.

## Overview

Implements the `IAgentAdapter` port by spawning `docker run --rm -i {image} codex exec --json --full-auto` and parsing JSONL events from stdout. Zero runtime dependencies (`node:child_process` + `node:readline`).

## Install

```bash
pnpm add @beddel/agent-codex
```

## Usage

```typescript
import { CodexAgentAdapter } from '@beddel/agent-codex';

const adapter = new CodexAgentAdapter({
  apiKey: process.env.OPENAI_API_KEY,
  model: 'gpt-5.3-codex',
  dockerImage: 'codex-universal:latest',
  timeoutMs: 300_000,
});

const result = await adapter.execute('Fix the bug in src/main.ts', {
  sandbox: 'workspace-write',
});
console.log(result.output);
```

## kit.yaml

```yaml
name: agent-codex-kit
version: "0.1.0"
adapters:
  - port: IAgentAdapter
    implementation: CodexAgentAdapter
```

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `apiKey` | `string` | `process.env.OPENAI_API_KEY` | OpenAI API key |
| `model` | `string` | `"gpt-5.3-codex"` | Codex model |
| `dockerImage` | `string` | `"codex-universal:latest"` | Docker image |
| `timeoutMs` | `number` | `300000` | Subprocess timeout |
| `repoPath` | `string` | `undefined` | Repo path to mount |

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| BEDDEL-ADAPT-535 | CodexExecFailed | Non-zero exit code |
| BEDDEL-ADAPT-536 | CodexExecTimeout | Subprocess exceeded timeout |
| BEDDEL-ADAPT-537 | CodexDockerUnavailable | Docker not available |
| BEDDEL-ADAPT-538 | CodexInvalidJsonl | Malformed JSONL line |
| BEDDEL-ADAPT-539 | CodexContainerOOM | Container OOM-killed |
| BEDDEL-ADAPT-540 | CodexAppServerConnectionFailed | (Reserved) |
