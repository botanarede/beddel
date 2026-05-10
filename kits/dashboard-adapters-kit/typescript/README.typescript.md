# @beddel/dashboard-adapters

Dashboard pipeline adapters normalizing agent events to Pipeline Protocol SSE format.

## Overview

Provides three backend-specific pipeline adapters that translate agent execution events
into a unified `PipelineEvent` format for real-time SSE streaming to the Beddel dashboard:

- **OpenClawPipelineAdapter** — translates OpenClaw Gateway SSE events.
- **ClaudePipelineAdapter** — translates Anthropic Messages API streaming events.
- **CodexPipelineAdapter** — translates Codex JSONL events.

Each adapter extends `AgentPipelineAdapter` base class with a `translate()` method and
`toSSE()` for SSE formatting. Optional Langfuse trace URL enrichment.

## Install

```bash
pnpm add @beddel/dashboard-adapters
```

## Usage

```typescript
import { OpenClawPipelineAdapter } from '@beddel/dashboard-adapters';

const adapter = new OpenClawPipelineAdapter('openclaw-main', 'https://langfuse.com/trace/123');

for await (const rawEvent of openClawStream) {
  const pipelineEvent = adapter.translate(rawEvent);
  if (pipelineEvent) {
    res.write(adapter.toSSE(pipelineEvent));
  }
}
```

## Pipeline Protocol Event Types

| Type | Description |
|------|-------------|
| `pipeline.started` | Agent execution has started |
| `pipeline.step_started` | A new step/block started |
| `pipeline.step_completed` | A step/block completed |
| `pipeline.output` | Text/content output from the agent |
| `pipeline.tool_use` | Agent invoked a tool |
| `pipeline.error` | An error occurred |
| `pipeline.completed` | Agent execution completed |

## Error Codes

| Code | Name | Description |
|------|------|-------------|
| BEDDEL-ADAPT-513 | PipelineTranslationFailed | Event cannot be translated |
| BEDDEL-ADAPT-514–519 | (Reserved) | Future pipeline error codes |
