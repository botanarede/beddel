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

## Delivery stages

A Delivery stage declares trust through the step's `config.sandbox` value:

- `read-only` uses `--trust-tools=`.
- `workspace-write` uses `-a`.
- Headless mode ignores `sandbox` and uses the adapter's `trust_tools`; the
  default is `--trust-all-tools`.

Every invocation pins `--agent-engine v3` and passes `--agent`: `tools[0]` or
constructor `agent` (`beddel-delivery`).

The step's `timeout` is the stage time bound. When `beddel run` builds this
adapter with no constructor arguments, the adapter timeout is 600 seconds, so
the step timeout must be at most 600 seconds. A step timeout kills and reaps
the `kiro-cli` process. The subprocess inherits the repository cwd and
environment and receives closed stdin. Login comes from the existing
`kiro-cli` login or `KIRO_API_KEY` in the environment; credentials are never
passed as command-line arguments.

The CLI does not report changed files, so `files_changed` is always `[]` and a
Delivery stage reads repository changes separately. Adapter errors use
`BEDDEL-AGENT-701` for execution failures and `BEDDEL-AGENT-702` for adapter
timeouts. A step timeout is raised as `BEDDEL-EXEC-005`; under the default FAIL
strategy the step failure `BEDDEL-EXEC-002` wraps it as its cause.

### Delivery agent and hooks

Operator install/verify: `PYTHONPATH=<kit>/python python3 -m beddel_agent_kiro.agent_config install|verify`; supports `--home`, `--pointers`, `--replace`.
Pointer `<pointers>/<sha256(realpath(cwd))>.json`; policy `beddel.kiro-hook-policy/1`, first-match-wins, no rules deny all; Python 3.11+; errors `KIRO_AGENT_INVALID`/`KIRO_CLI_MISSING`.
Log schema `beddel.kiro-hook/1`: `v`, `ts`, `seq`, `session_id`, `event`, `tool_name`, `tool_class`, `cmd_head`, `input_sha256`, `input_len`, `response_sha256`, `response_len`, `decision`, `rule_id`, `policy_sha256`, `hook_ms`.

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
| `agent` | `str` | `"beddel-delivery"` | Agent when `tools` is absent |
| `pointers_dir` | `Path \| None` | `None` | Hook pointer directory |

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

If `cli_path` is not provided, the adapter discovers an already-installed
`kiro-cli` via:

1. Default path: `~/.local/bin/kiro-cli`
2. PATH lookup: `shutil.which("kiro-cli")`

If both fail, `KIRO_CLI_MISSING`; manual text. No auto-install/network call.

## Running Tests

Run the kit tests from the kit directory with the Beddel SDK installed:

```bash
pytest -q
```
