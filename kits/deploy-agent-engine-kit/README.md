# deploy-agent-engine-kit

Deploy Beddel flows to Vertex AI Agent Engine.

## Dependencies

- `google-adk>=2.0.0,<3.0.0` (ADK 2.x GA)
- `google-cloud-aiplatform[adk,agent_engines]>=1.148.0`

## Integrations

| Name | Description |
|------|-------------|
| deploy_flow_to_agent_engine | Deploy a Beddel flow YAML to Agent Engine (in-process) |
| check_adc | Check ADC configuration and return project/error info |

## Usage

### Check ADC configuration

```python
from beddel_deploy_agent_engine import check_adc

result = check_adc()
if not result["configured"]:
    print(f"ADC not configured: {result['error']}")
    print("Run: gcloud auth application-default login")
```

### Deploy a flow to Agent Engine

```python
from pathlib import Path
from beddel_deploy_agent_engine import deploy_flow_to_agent_engine

result = deploy_flow_to_agent_engine(
    flow_path=Path("workflows/sum-two-numbers.yaml"),
    project="my-gcp-project",
    region="us-central1",
    staging_bucket="gs://my-staging-bucket",
)

print(f"Deployed: {result.resource_name}")
print(f"Console: {result.console_url}")
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_CLOUD_PROJECT` | `your-project-id` | GCP project ID |
| `CLOUD_ML_REGION` | `us-central1` | Vertex AI region |
| `STAGING_BUCKET` | `gs://beddel-workflows` | Required by `vertexai.init()` for staging |
