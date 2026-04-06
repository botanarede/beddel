# agent-codex-kit

Codex agent adapter for the Beddel SDK. Implements the `IAgentAdapter` port to execute prompts via a Codex Docker subprocess.

## Dependencies

None — uses Docker subprocess only (no pip dependencies).

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `src/` directory to your Python path:

```bash
export PYTHONPATH="kits/agent-codex-kit/src:$PYTHONPATH"
```

## Prerequisites

- Docker must be installed and accessible on the host
- The Codex Docker image must be available locally (default: `codex-universal:latest`)

## Usage

```python
from beddel_agent_codex.adapter import CodexAgentAdapter

adapter = CodexAgentAdapter(
    model="gpt-5.3-codex",
    docker_image="codex-universal:latest",
    timeout=300,
    workspace_dir="/path/to/project",
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
cd kits/agent-codex-kit
python -m pytest tests/ -x
```
