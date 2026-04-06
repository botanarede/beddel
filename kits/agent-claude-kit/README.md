# agent-claude-kit

Claude Agent SDK adapter for the Beddel SDK. Implements the `IAgentAdapter` port to execute prompts via the Claude Agent SDK subprocess wrapper.

## Dependencies

- `claude-agent-sdk>=0.1`

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `src/` directory to your Python path:

```bash
export PYTHONPATH="kits/agent-claude-kit/src:$PYTHONPATH"
```

Or install the Beddel SDK with the claude extra (when available):

```bash
pip install beddel[claude]
```

## Usage

```python
from beddel_agent_claude.adapter import ClaudeAgentAdapter

adapter = ClaudeAgentAdapter(
    model="claude-sonnet-4",
    max_turns=25,
    timeout=300,
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
cd kits/agent-claude-kit
python -m pytest tests/ -x
```
