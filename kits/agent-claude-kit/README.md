# agent-claude-kit

Claude Agent SDK adapter for the Beddel SDK. Implements the `IAgentAdapter` port to execute prompts via the Claude Agent SDK subprocess wrapper.

## Dependencies

- `claude-agent-sdk>=0.2.0`

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `python/` directory to your Python path:

```bash
export PYTHONPATH="kits/agent-claude-kit/python:$PYTHONPATH"
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

## Vertex AI ADC (Application Default Credentials)

Use Claude through Google Cloud billing — no Anthropic API key needed.

### Prerequisites

1. A Google Cloud project with the Vertex AI API enabled
2. Application Default Credentials configured:
   ```bash
   gcloud auth application-default login
   ```
3. Environment variables set:
   ```bash
   export ANTHROPIC_VERTEX_PROJECT_ID="your-gcp-project-id"
   export CLOUD_ML_REGION="us-east5"  # optional, defaults to us-east5
   ```

### Usage with Vertex AI

```python
from beddel_agent_claude.adapter import ClaudeAgentAdapter

# Option 1: Pass project/region explicitly
adapter = ClaudeAgentAdapter(
    model="claude-sonnet-4",
    vertex_project="your-gcp-project-id",
    vertex_region="us-east5",
)

# Option 2: Use environment variables (ANTHROPIC_VERTEX_PROJECT_ID, CLOUD_ML_REGION)
adapter = ClaudeAgentAdapter(model="claude-sonnet-4")

# Execute — env vars are propagated to the subprocess automatically
result = await adapter.execute("Refactor the auth module")
```

The adapter sets `CLAUDE_CODE_USE_VERTEX=1`, `ANTHROPIC_VERTEX_PROJECT_ID`, and `CLOUD_ML_REGION` in the subprocess environment. The Claude Agent SDK then authenticates via ADC.

### Additional Options

```python
adapter = ClaudeAgentAdapter(
    model="claude-sonnet-4",
    vertex_project="my-project",
    vertex_region="us-east5",
    system_prompt="You are a senior Python developer.",
    thinking="adaptive",   # adaptive | enabled | disabled
    effort="high",         # low | medium | high
)
```

### Bundled Flow

Run Claude via Vertex AI using the bundled Beddel workflow:

```bash
beddel run --bundled run-claude-vertex -i prompt="Analyze the auth module"
```

## Running Tests

```bash
cd kits/agent-claude-kit
python -m pytest tests/ -x
```
