# agent-kimi-kit

Kimi K3 agent adapter for Beddel workflows via `kimi-agent-sdk` Session API.

## Public API

### KimiAgentAdapter

Implements `IAgentAdapter` — autonomous code agent execution with model tier routing and KAOS sandbox passthrough.

```python
from beddel_agent_kimi import KimiAgentAdapter

adapter = KimiAgentAdapter(timeout=300)
result = await adapter.execute("Analyze codebase", model="powerful")
print(result.output)
```

#### `execute(prompt, *, model, sandbox, tools, output_schema) -> AgentResult`

Executes a prompt via a Kimi Session. Creates session, submits prompt, collects output, cleans up.

#### `stream(prompt, *, model, sandbox, tools) -> AsyncGenerator[dict, None]`

Streams events from a Kimi agent session. Yields structured event dicts:
- `{"type": "text", "content": "..."}` — incremental text output
- `{"type": "approval_request", "message": "...", "approved": bool}` — agent needs permission
- `{"type": "complete", "output": "...", "exit_code": 0}` — final aggregated output

### KimiSwarmStrategy

Implements `ICoordinationStrategy` — multi-agent coordination via Kimi's native AgentSwarm tool.

```python
from beddel_agent_kimi import KimiSwarmStrategy

strategy = KimiSwarmStrategy(swarm_concurrency=16, model="powerful")
result = await strategy.coordinate(agents, task, context)
print(result.output)
```

#### `coordinate(agents, task, context) -> CoordinationResult`

Orchestrates work by creating a parent Session and prompting it to invoke AgentSwarm with task.subtasks as items. Supports up to 128 concurrent sub-agents.

### KimiApprovalBridge

Bridges Kimi `ApprovalRequest` wire messages to Beddel's `IApprovalGate` port.

```python
from beddel_agent_kimi import KimiApprovalBridge

bridge = KimiApprovalBridge(gate=my_approval_gate, mode="gate", timeout=60.0)
```

Modes: `auto` (always approve), `gate` (delegate to IApprovalGate), `deny` (always deny).

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `MOONSHOT_API_KEY` | Yes | Moonshot platform API key |

## Model Tiers

| Beddel Tier | Kimi Model | Use Case |
|-------------|------------|----------|
| `fast` | kimi-k2.6 | Quick analysis, low-latency |
| `balanced` | kimi-k2.7-code-highspeed | Code generation, planning |
| `code` | kimi-k2.7-code | Deep code tasks |
| `powerful` | kimi-k3 | Frontier reasoning, complex orchestration |

## Sandbox Levels

| Level | KAOS Mode | Effect |
|-------|-----------|--------|
| `read-only` | read_only | File read only |
| `workspace-write` | workspace | Write within workspace |
| `danger-full-access` | unrestricted | Full system access |

## Dependencies

- `kimi-agent-sdk>=0.1.0`
- Python 3.11+
