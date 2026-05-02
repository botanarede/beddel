# guardrail-model-armor-kit

Model Armor guardrail strategy for the Beddel SDK. Provides a `ModelArmorGuardrailStrategy` that validates inputs and outputs against Google Cloud Model Armor for prompt injection detection and content policy enforcement.

## Dependencies

- `google-auth>=2.0` — Google authentication (ADC)
- `google-cloud-modelarmor>=0.1.0` — Google Cloud Model Armor client library
- `httpx>=0.27.0` — HTTP client for API communication

## YAML Configuration

```yaml
steps:
  - name: "safe-llm-call"
    primitive: "guardrail"
    config:
      strategy: model_armor
      sensitivity: medium
      check_input: true
      check_output: true
      fallback_on_error: pass
```

## Sensitivity Levels

| Level | Behavior |
|-------|----------|
| `low` | Only blocks high-confidence prompt injection attempts |
| `medium` | Balanced detection (default) |
| `high` | Aggressive filtering, may produce false positives |

## Fallback Behavior

Controls what happens when the Model Armor API is unavailable:

| Mode | Behavior |
|------|----------|
| `pass` (default) | API failures log a warning and allow the request through |
| `block` | API failures reject the request by policy |

## Authentication Setup

`ModelArmorGuardrailStrategy` uses Application Default Credentials (ADC). No separate API key is required. Set up credentials using one of:

```bash
# Local development — user credentials
gcloud auth application-default login

# Service account (CI/CD, Cloud Run)
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

## Usage

```python
from beddel_guardrail_model_armor import ModelArmorGuardrailStrategy

strategy = ModelArmorGuardrailStrategy(
    project_id="my-gcp-project",
    location="us-central1",
    sensitivity="medium",
    fallback_on_error="pass",
)

# Validate user input before sending to LLM
result = await strategy.validate_input("Tell me about Python")
if not result.passed:
    print(f"Blocked: {result.reason}")

# Validate LLM output before returning to user
result = await strategy.validate_output(llm_response)
if not result.passed:
    print(f"Filtered: {result.reason}")
```

## Error Codes

| Code | Constant | Description |
|------|----------|-------------|
| `BEDDEL-GUARD-250` | `MODEL_ARMOR_UNAVAILABLE` | Model Armor API unavailable, fallback applied |
| `BEDDEL-GUARD-251` | `PROMPT_INJECTION_DETECTED` | Prompt injection detected in input |
| `BEDDEL-GUARD-252` | `POLICY_VIOLATION_DETECTED` | Policy violation detected in output |

## Testing

```bash
cd repo/kits/guardrail-model-armor-kit
python -m pytest tests/ -x
```
