# bridge-adk-kit

ADK Bridge — wraps Beddel workflows as ADK FunctionTools.

## Dependencies

- `google-adk>=1.0.0,<2.0.0`

## Integrations

| Name | Description |
|------|-------------|
| BeddelADKTool | Wraps a Beddel YAML workflow as an ADK FunctionTool |
| create_adk_agent | Factory for creating ADK agents with Beddel workflow tools |

## Usage

Install with the bridge-adk extra:

```bash
pip install beddel[bridge-adk]
```

### Wrapping a workflow as an ADK tool

```python
from beddel.domain.executor import WorkflowExecutor
from beddel.domain.registry import PrimitiveRegistry
from beddel_bridge_adk import BeddelADKTool

registry = PrimitiveRegistry()
executor = WorkflowExecutor(registry)

tool = BeddelADKTool(
    workflow_path="workflows/summarize.yaml",
    executor=executor,
    name="summarize",
    description="Summarize input text using a Beddel workflow",
)

adk_tool = tool.as_adk_tool()
```

### Creating an ADK agent with Beddel tools

```python
from beddel_bridge_adk import BeddelADKTool, create_adk_agent

agent = create_adk_agent(
    name="my_agent",
    model="gemini-2.0-flash",
    tools=[tool],
    instruction="You are a helpful assistant.",
)
```
