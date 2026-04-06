# agent-kiro-kit

Kiro CLI agent adapter for the Beddel SDK. Implements the `IAgentAdapter` port to execute prompts via the Kiro CLI subprocess.

## Dependencies

None — uses subprocess only (no pip dependencies).

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `src/` directory to your Python path:

```bash
export PYTHONPATH="kits/agent-kiro-kit/src:$PYTHONPATH"
```

## Usage

```python
from beddel_agent_kiro.adapter import KiroCLIAgentAdapter

adapter = KiroCLIAgentAdapter(
    model="claude-sonnet-4.6",
    timeout=600,
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
cd kits/agent-kiro-kit
python -m pytest tests/ -x
```
