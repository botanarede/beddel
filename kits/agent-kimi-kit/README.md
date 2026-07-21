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

bridge = KimiApprovalBridge(gate=my_approval_gate, mode="manual", timeout=60.0)
```

Modes:
- `auto` — risk-based policy: LOW and recognized MEDIUM actions are approved; unrecognized MEDIUM, HIGH, and CRITICAL are denied.
- `manual` — delegates every decision to the provided `IApprovalGate` implementation.
- `yolo` — approve all requests unconditionally (opt-in unsafe escape hatch).

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `MOONSHOT_API_KEY` | Yes | Moonshot platform API key |

## Production Security

### Default Approval Mode

The default `approval_mode` is `"manual"`, which means **all agent actions are denied by default** unless an `IApprovalGate` implementation is provided to make decisions. This is the safest default for production deployments.

| Mode | Behavior |
|------|----------|
| `manual` (default) | All requests denied unless gate approves. Timeout → deny. |
| `auto` | Risk-based policy: LOW/recognized MEDIUM → approve; HIGH → deny. |
| `yolo` | Approve everything (opt-in unsafe escape hatch). |

### Container Isolation (MANDATORY)

**Container isolation is MANDATORY for production deployments.** The Kimi agent's `work_dir` parameter is NOT a filesystem boundary — the agent can access files outside it via absolute paths. Deploy the adapter inside an isolated container (Docker, gVisor, etc.) to enforce actual filesystem boundaries.

### Tool Restrictions (agent_file)

Use the `agent_file` parameter to load a custom agent YAML config that restricts which tools the Kimi agent can use:

```python
from beddel_agent_kimi import KimiAgentAdapter
from beddel_agent_kimi.agent_config import get_production_agent_file

# Production-safe: dangerous tools disabled
adapter = KimiAgentAdapter(
    agent_file=get_production_agent_file(),
    # approval_mode="manual" is already the default
)
```

The bundled `production-agent.yaml` disables these dangerous tools:

| Tool | Risk | Status |
|------|------|--------|
| `Shell` | Arbitrary command execution | **Disabled** |
| `ReadMediaFile` | CVE-2026-25990 via Pillow | **Disabled** |
| `FetchURL` | Network exfiltration | **Disabled** |
| `SearchWeb` | Network access | **Disabled** |
| `Task` | Subagent bypasses tool restrictions | **Disabled** |
| `ReadFile` | File read (container-isolated) | Enabled |
| `Glob` | File discovery (container-isolated) | Enabled |
| `Grep` | File search (container-isolated) | Enabled |
| `WriteFile` | File write (**approval-gated**) | Enabled |
| `StrReplaceFile` | File edit (**approval-gated**) | Enabled |

> **Note on approval scope:** In manual mode, the SDK only emits `ApprovalRequest` for write operations (`WriteFile`, `StrReplaceFile`). Read operations (`ReadFile`, `Glob`, `Grep`) are allowed without approval — they accept absolute paths, so **container isolation is the actual filesystem boundary**, not the approval gate. The `work_dir` parameter is NOT a security boundary.

### Custom Agent Config

Create your own agent YAML to customize available tools:

```yaml
version: 1
agent:
  extend: "default"
  name: "my-custom-agent"
  tools:
    - "kimi_cli.tools.file:ReadFile"
    - "kimi_cli.tools.file:WriteFile"
    # Add only the tools you need
```

Pass it to the adapter:

```python
from pathlib import Path

adapter = KimiAgentAdapter(agent_file=Path("my-agent.yaml"))
```

### Production Deployment Checklist

Follow these steps before deploying agent-kimi-kit to production:

1. **Container isolation** — Run the adapter inside Docker, Firecracker, or equivalent container runtime. The `work_dir` parameter is NOT a filesystem boundary.

2. **Agent file configuration** — Use the bundled production config to disable dangerous tools:
   ```python
   from beddel_agent_kimi.agent_config import get_production_agent_file
   adapter = KimiAgentAdapter(agent_file=get_production_agent_file())
   ```

3. **Approval mode verification** — Confirm `approval_mode="manual"` (the default). Inject an `IApprovalGate` implementation to handle write approval requests.

4. **Environment variable** — Set `MOONSHOT_API_KEY` securely (secrets manager, not in code/env files committed to VCS).

5. **Network egress restriction** — Restrict outbound network from the container to only `api.moonshot.ai` (port 443). Block all other egress to prevent data exfiltration even if agent config is bypassed.

6. **Verify tool restrictions** — After deployment, confirm Shell, ReadMediaFile, FetchURL, SearchWeb, and Task are NOT available to the agent by checking logs on first session creation.

7. **Monitor dependency** — `kimi-agent-sdk==0.0.5` has a transitive dev-only CVE (CVE-2026-25046 via kimi-cli). Monitor upstream for SDK ≥0.1.0 which should drop this dependency. Review by Q4 2026.

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
