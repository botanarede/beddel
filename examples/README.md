# Beddel Example Flows

Advanced workflow examples that require additional kits beyond the defaults
installed by `beddel init`.

These flows are **not bundled** with `pip install beddel` — they serve as
reference implementations for users who have installed the required kits.

## Claude (Vertex AI)

Requires: `agent-claude-kit`, Google Cloud ADC

| Flow | Description |
|------|-------------|
| `claude/code-review.yaml` | Three-layer adversarial code review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) |
| `claude/run-prompt.yaml` | Execute a prompt via Claude on Vertex AI with structured output |

### Setup

```bash
# Install the required kit
beddel kit install agent-claude-kit

# Configure Google Cloud credentials
gcloud auth application-default login
export ANTHROPIC_VERTEX_PROJECT_ID=your-project-id

# Run a flow
beddel run repo/examples/claude/run-prompt.yaml -i prompt="Hello from Claude"
```

## Adding Examples

When adding new example flows:

1. Place them under a subdirectory named after the primary kit they require
2. Include `requires_kits` in the flow YAML
3. Document prerequisites in this README
