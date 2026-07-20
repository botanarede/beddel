# agent-kimi-kit

Kimi K3 agent adapter for Beddel workflows via `kimi-agent-sdk` Session API.

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
| `read-only` | read-only | File read only |
| `workspace-write` | workspace-scoped | Write within workspace |
| `danger-full-access` | unrestricted | Full access |

## Usage

```python
from beddel_agent_kimi import KimiAgentAdapter

adapter = KimiAgentAdapter(timeout=300)
result = await adapter.execute("Analyze codebase", model="powerful")
print(result.output)
```

## Dependencies

- `kimi-agent-sdk>=0.1.0`
- Python 3.11+
