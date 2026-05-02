# agent-a2a-kit

A2A Protocol agent adapter for the Beddel SDK. Provides an `A2AAgentAdapter` that implements the `IAgentAdapter` port, enabling communication with any A2A-compliant agent via the standard Agent-to-Agent protocol. Includes agent discovery via the `.well-known/agent.json` Agent Card endpoint.

## Dependencies

- `httpx>=0.27.0` — Async HTTP client for A2A protocol communication
- `a2a-sdk>=0.2.0` — Google A2A Protocol SDK

## Installation

```bash
pip install httpx a2a-sdk
```

## Authentication Setup

`A2AAgentAdapter` supports bearer token authentication for secured A2A endpoints. Configure auth using one of:

```python
# Direct token
adapter = A2AAgentAdapter(
    agent_url="https://agent.example.com",
    auth_token="your-bearer-token",
)

# No auth (local / unsecured agents)
adapter = A2AAgentAdapter(
    agent_url="http://localhost:8080",
)
```

For production deployments, store tokens in environment variables and pass them at construction time.

## Usage

```python
from beddel_agent_a2a.adapter import A2AAgentAdapter
from beddel_agent_a2a.discovery import discover_agent

# Discover agent capabilities via Agent Card
card = await discover_agent("https://agent.example.com")
print(card.name, card.skills)

# Create adapter and send a task
adapter = A2AAgentAdapter(
    agent_url="https://agent.example.com",
)

response = await adapter.call(
    prompt="Summarize the quarterly report",
    context={"document_id": "q4-2025"},
)
print(response.output)
```

## Agent Discovery

A2A agents expose an Agent Card at `/.well-known/agent.json` describing their capabilities, supported skills, and authentication requirements. The `discover_agent` helper fetches and parses this card:

```python
from beddel_agent_a2a.discovery import discover_agent

card = await discover_agent("https://agent.example.com")

# Inspect agent capabilities
print(f"Agent: {card.name}")
print(f"Skills: {card.skills}")
print(f"Auth required: {card.authentication}")
```

## Supported Operations

| Operation | Description |
|-----------|-------------|
| `call` | Send a task to an A2A agent and receive a response |
| `discover_agent` | Fetch the Agent Card from an A2A endpoint |

## Testing

```bash
cd kits/agent-a2a-kit
python -m pytest tests/ -x
```
