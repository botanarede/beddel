# antigravity-sdk-kit

Google Antigravity SDK (`google-adk`) bridge kit for the Beddel SDK. Implements the `IAgentAdapter` port to run in-process ADK agents through the `agent-exec` primitive, and exposes 7 standalone tools for granular access to Antigravity features (custom tools, MCP passthrough, sub-agent delegation, session persistence, usage tracking, safety checks).

Direction: **ADK → Beddel** (Antigravity capabilities exposed to Beddel workflows). This is the inverse of `bridge-adk-kit`, which exposes Beddel workflows *to* ADK.

## Overview

Unlike the Claude Agent SDK adapter (`agent-claude-kit`), which spawns a subprocess, the Antigravity SDK runs **in-process** as a native async Python library via ADK's `Runner.run_async()`. The adapter:

- Implements `IAgentAdapter.execute()` / `IAgentAdapter.stream()` via structural subtyping (no explicit inheritance)
- Maps Beddel's `sandbox` levels (`read-only` / `workspace-write` / `danger-full-access`) onto ADK safety policies (`deny_all` / `workspace_only` / `allow`)
- Supports MCP passthrough (stdio + SSE transports), real ADK sub-agent delegation, lifecycle hooks, tracing spans, and optional `IStateStore`-backed session persistence

See `docs/architecture/35-antigravity-sdk-kit.md` in the main repo for the full architecture (component diagram, defense-in-depth safety model, error codes).

## Installation

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `python/` directory to your Python path:

```bash
export PYTHONPATH="repo/kits/antigravity-sdk-kit/python:$PYTHONPATH"
```

Install the runtime dependency:

```bash
pip install "google-adk>=2.0.0,<3.0.0" "pydantic>=2.0"
```

## Quickstart

```python
from beddel_antigravity_sdk.adapter import AntigravityAgentAdapter

adapter = AntigravityAgentAdapter(
    model="gemini-2.5-flash",
    timeout=300,
    safety_policy="deny_all",
)

# Execute a prompt (in-process, no subprocess)
result = await adapter.execute("Summarize the last release notes", sandbox="read-only")
print(result.output)

# Stream events as they arrive
async for event in adapter.stream("Draft a changelog entry"):
    print(event)
```

Or run one of the bundled example workflows (see below):

```bash
beddel run --file repo/kits/antigravity-sdk-kit/workflows/hello-world.yaml -i topic="the Beddel SDK"
```

## Configuration Reference

All parameters accepted by `AntigravityAgentAdapter.__init__`:

| Param | Type | Default | Description |
|---|---|---|---|
| `model` | `str` | `"gemini-2.5-flash"` | Default model identifier for Antigravity SDK invocations. |
| `timeout` | `int` | `300` | Maximum execution time in seconds before the session is aborted (`AGENT_TIMEOUT` / `AGENT_STREAM_INTERRUPTED`). |
| `safety_policy` | `str` | `"deny_all"` | Default safety policy (`deny_all` \| `workspace_only` \| `allow`), used when `sandbox` is not passed to `execute()`/`stream()`. |
| `mcp_servers` | `list[dict] \| None` | `None` | MCP server config dicts (`{"name", "transport": "stdio"\|"sse", ...}`), lazily resolved into `McpStdioServer`/`McpSseServer` objects at call time. |
| `tools` | `list[Any] \| None` | `None` | Tool objects/callables passed to the ADK `Agent`. Also the registry used by `antigravity_tool_exec`. |
| `enable_subagents` | `bool` | `False` | Master switch for sub-agent delegation. Must be `True` for `sub_agents` config and `antigravity_subagent` to take effect. |
| `save_dir` | `str \| None` | `None` | Directory for file-based session persistence (`AntigravitySession.save()`/`.load()`). Used when `state_store` is not configured. |
| `skills_paths` | `list[str] \| None` | `None` | Optional list of skill file paths to load. |
| `lifecycle_hooks` | `dict[str, Any] \| None` | `None` | Callback map. Recognized keys: `on_session_start`, `on_session_end`, `pre_tool_call_decide`, `post_tool_call`, `on_tool_error`. Sync or async callables; exceptions are logged and swallowed (never break execution). |
| `sub_agents` | `list[dict] \| None` | `None` | Sub-agent config dicts (`{"name", "model"?, "instruction"?, "tools"?}`), lazily resolved into real ADK `Agent` instances at call time. Mirrors the `mcp_servers` config-dict-list pattern. |
| `state_store` | `Any \| None` | `None` | Optional `IStateStore`-shaped instance (duck-typed). When set, `antigravity_session_save`/`antigravity_session_load` use `AntigravityStateSync` instead of file-based persistence. |
| `tracer` | `Any \| None` | `None` | Optional `ITracer`-shaped instance (duck-typed). Emits `antigravity.execute` / `antigravity.stream` spans. Tracing failures are logged, never propagated. |

`execute()` / `stream()` per-call parameters:

| Param | Type | Default | Description |
|---|---|---|---|
| `prompt` | `str` | — | The instruction/task sent as the ADK user message (not the system instruction). |
| `model` | `str \| None` | `None` | Overrides the adapter's configured `model` for this call. |
| `sandbox` | `str` | `"read-only"` | Overrides the adapter's `safety_policy` for this call (`read-only` → `deny_all`, `workspace-write` → `workspace_only`, `danger-full-access` → `allow`). |
| `tools` | `list[str] \| None` | `None` | Overrides the adapter's `tools` list for this call. |
| `output_schema` | `dict \| None` | `None` (`execute()` only) | JSON Schema dict for structured output (stored; full Pydantic conversion is a future enhancement). |

## Tool Reference

All 7 tools are registered in `kit.yaml` and receive a `ToolContext` (session + adapter reference) as their first argument.

| Tool | Category | Description |
|---|---|---|
| `antigravity_tool_exec` | agent | Execute a registered Antigravity custom tool by name. Enforces the safety-policy check via `antigravity_safety_check` before invocation (defense-in-depth, inner layer). |
| `antigravity_mcp_call` | mcp | Call an MCP tool via a configured `mcp_servers` entry (stdio or SSE transport). |
| `antigravity_subagent` | agent | Delegate a task to a sub-agent. If `agent_name` matches a configured `sub_agents` entry, runs a standalone ADK session against that named child `Agent`; otherwise falls back to `adapter.execute()`. Requires `enable_subagents=True`. |
| `antigravity_session_save` | persistence | Persist conversation state. Uses `AntigravityStateSync` (via `IStateStore`) when `state_store` is configured on the adapter, otherwise file-based JSON at `save_dir`. |
| `antigravity_session_load` | persistence | Load a previous conversation by `conversation_id`, via the same state-store-or-file-based dual path as `antigravity_session_save`. |
| `antigravity_usage` | observability | Retrieve accumulated token usage/cost metrics from the current session. |
| `antigravity_safety_check` | guardrail | Evaluate whether a tool invocation is allowed under the adapter's current safety policy (fail-closed on unknown policies). |

## Example Workflows

Three example workflows are bundled in `workflows/` and referenced in `kit.yaml`:

- **`hello-world.yaml`** — Minimal single-step `agent-exec` example: send a prompt through the `antigravity` adapter and print the result. Good starting point for wiring the adapter into the `agent_registry`.
- **`mcp-pipeline.yaml`** — Multi-step pipeline: a `schedule` trigger (Beddel's native `IEventTrigger`, per architecture §35.8 — Antigravity's own `every()`/`on_file_change()` helpers are intentionally NOT exposed), a standalone `antigravity_tool_exec` call, an `antigravity_mcp_call` passthrough call, and a final `agent-exec` step that synthesizes both results.
- **`vds-orchestrator.yaml`** — Simplified version of the Viver de Samba multi-agent marketing pipeline (the epic's target use case): a `researcher` sub-agent gathers highlights, a `writer` sub-agent drafts a social post, and the session is persisted via `antigravity_session_save`. Demonstrates the `sub_agents`/`antigravity_subagent` delegation feature added in Story K5.5.

Each workflow file documents its own host wiring requirements (adapter registration, tool registry entries, MCP/sub-agent config) in a header comment block.

Run any of them with:

```bash
beddel run --file repo/kits/antigravity-sdk-kit/workflows/hello-world.yaml -i topic="..."
beddel run --file repo/kits/antigravity-sdk-kit/workflows/mcp-pipeline.yaml
beddel run --file repo/kits/antigravity-sdk-kit/workflows/vds-orchestrator.yaml -i event_topic="..."
```

## Architecture Notes

- **Bridge, not native**: Antigravity runs in-process (unlike `agent-claude-kit`, which spawns a subprocess).
- **Scoped sessions**: `AntigravitySession` state is ephemeral within one `agent-exec` step; cross-step persistence requires an explicit `antigravity_session_save`/`antigravity_session_load` call, or `AntigravityStateSync` when a Beddel `IStateStore` is wired via `state_store`.
- **Triggers replaced, not wrapped**: Use Beddel's native `IEventTrigger` (workflow `metadata.trigger`) instead of Antigravity's `every()`/`on_file_change()` helpers — this provides cron-capable scheduling, retry/circuit-breaker, and event sourcing that Antigravity's own helpers don't offer.
- **MCP passthrough**: Antigravity manages MCP server connections internally during `agent-exec`; standalone tool-level calls go through `antigravity_mcp_call`, which resolves the same `mcp_servers` config dicts on demand.
- **Defense in depth**: Beddel's sandbox (outer layer) and Antigravity's `safety_policy` (inner layer) are both enforced — most restrictive wins. A Beddel-level denial never reaches Antigravity; an Antigravity-level denial propagates back as an `AgentError`.
- **Sub-agent delegation**: `sub_agents` config dicts are lazily resolved into real ADK `Agent` instances only when a run actually happens (`_build_sub_agents()` / `_build_sub_agent(name)`), keeping `google-adk` import-free at adapter-construction time.

## Error Codes

| Code | Description |
|---|---|
| `BEDDEL-AGENT-700` | `google-adk` not installed |
| `BEDDEL-AGENT-701` | Agent execution error |
| `BEDDEL-AGENT-702` | Execution timeout |
| `BEDDEL-AGENT-703` | Stream interrupted |
| `BEDDEL-AGENT-751` | Antigravity execution failed (tool/subagent level) |
| `BEDDEL-AGENT-753` | Safety policy denied the call |
| `BEDDEL-AGENT-754` | MCP server connection/call failed |
| `BEDDEL-AGENT-755` | Conversation ID not found in `save_dir` |

## Running Tests

```bash
cd repo/kits/antigravity-sdk-kit
python -m pytest tests/ -x --timeout=30
```

Lint (from repo root):

```bash
ruff check repo/kits/antigravity-sdk-kit/
ruff format --check repo/kits/antigravity-sdk-kit/
```

`mypy` is not required for kits under `repo/` (only for `src/beddel-py/`). Type hints remain mandatory on all public APIs.
