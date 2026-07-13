# agent-kiro-kit

Kiro CLI agent adapter for the Beddel SDK. Implements the `IAgentAdapter` port to execute prompts via the Kiro CLI subprocess.

## Dependencies

None — uses subprocess only (no pip dependencies).

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `python/` directory to your Python path:

```bash
export PYTHONPATH="kits/agent-kiro-kit/python:$PYTHONPATH"
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

## Headless Mode (CI/CD)

For containers, CI/CD pipelines, and headless environments where browser-based SSO is unavailable, set the `KIRO_API_KEY` environment variable. The adapter automatically detects it and activates headless mode.

### Environment Variable

```bash
export KIRO_API_KEY="your-kiro-api-key"
```

When `KIRO_API_KEY` is set, the adapter appends `--no-interactive` and `--trust-all-tools` to all CLI invocations. The API key is never passed as a CLI argument — the subprocess inherits the environment.

### Constructor Parameters

```python
from beddel_agent_kiro.adapter import KiroCLIAgentAdapter

# Option 1: rely on KIRO_API_KEY env var (auto-detected)
adapter = KiroCLIAgentAdapter()

# Option 2: explicit api_key (overrides env var)
adapter = KiroCLIAgentAdapter(api_key="your-key")

# Option 3: restrict tool trust (instead of trust-all)
adapter = KiroCLIAgentAdapter(
    api_key="your-key",
    trust_tools=["read", "grep", "glob"],
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | `"claude-sonnet-4.6"` | Default model for CLI invocations |
| `cli_path` | `Path \| None` | `None` | Explicit path to `kiro-cli` binary |
| `timeout` | `int` | `600` | Max execution time in seconds |
| `api_key` | `str \| None` | `None` | API key for headless mode (falls back to `KIRO_API_KEY` env var) |
| `trust_tools` | `list[str] \| None` | `None` | Tool categories to trust in headless mode (`None` = trust all) |

### Docker Example

```dockerfile
FROM python:3.12-slim

# Install kiro-cli
RUN curl -fsSL https://cli.kiro.dev/install | bash

# Set API key (use secrets in production)
ENV KIRO_API_KEY=your-key-here

COPY . /app
WORKDIR /app
RUN pip install beddel

CMD ["python", "run_workflow.py"]
```

### GitHub Actions Example

```yaml
jobs:
  run-workflow:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install kiro-cli
        run: curl -fsSL https://cli.kiro.dev/install | bash
      - name: Run workflow
        env:
          KIRO_API_KEY: ${{ secrets.KIRO_API_KEY }}
        run: python run_workflow.py
```

### Trust Modes

| `trust_tools` value | CLI flag | Description |
|---------------------|----------|-------------|
| `None` (default) | `--trust-all-tools` | Trust all tool categories |
| `["read", "grep"]` | `--trust-tools=read,grep` | Trust only read and grep |
| `["read", "write", "shell"]` | `--trust-tools=read,write,shell` | Trust read, write, and shell |

### Binary Auto-Discovery

When `cli_path` is not provided, the adapter discovers `kiro-cli` via:

1. Default path: `~/.local/bin/kiro-cli`
2. PATH lookup: `shutil.which("kiro-cli")`
3. Auto-install: `curl -fsSL https://cli.kiro.dev/install | bash`

If all steps fail, an `AgentError(BEDDEL-AGENT-701)` is raised.

## Running Tests

```bash
cd repo/kits/agent-kiro-kit
PYTHONPATH="python:../../src/beddel-py/tests" python -m pytest tests/ -x
```
