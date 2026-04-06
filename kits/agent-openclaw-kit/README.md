# agent-openclaw-kit

OpenClaw Gateway agent adapter for the Beddel SDK. Implements the `IAgentAdapter` port to execute prompts via an OpenClaw Gateway HTTP API.

## Dependencies

- `httpx>=0.27`

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `src/` directory to your Python path:

```bash
export PYTHONPATH="kits/agent-openclaw-kit/src:$PYTHONPATH"
```

Or install the Beddel SDK with the openclaw extra (when available):

```bash
pip install beddel[openclaw]
```

## Usage

```python
from beddel_agent_openclaw.adapter import OpenClawAgentAdapter

adapter = OpenClawAgentAdapter(
    gateway_url="http://localhost:3000",
    agent="main",
    timeout=120,
)

# Execute a prompt
result = await adapter.execute("Analyze the codebase")
print(result.output)

# Stream events
async for event in adapter.stream("Summarize changes"):
    print(event)
```

## Running Tests

```bash
cd kits/agent-openclaw-kit
python -m pytest tests/ -x
```
