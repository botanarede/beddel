# agent-a2a-kit

A2A Protocol kit for the Beddel SDK — bidirectional agent communication.

- **Client (outbound)**: `A2AAgentAdapter` implements the `IAgentAdapter` port, enabling communication with any A2A-compliant agent via the official `a2a-sdk` client.
- **Server (inbound)**: `BeddelA2AExecutor` exposes Beddel workflows as A2A-compliant agents.
- **Discovery**: `discover_agent` fetches the Agent Card with typed response.

## Dependencies

- `a2a-sdk>=1.0,<2.0` — Official Google A2A Protocol SDK (includes httpx, protobuf, pydantic)

Optional (for server mode):
- `a2a-sdk[http-server]>=1.0` — A2A server framework

## Installation

```bash
pip install "a2a-sdk>=1.0,<2.0"
```

## Authentication Setup

`A2AAgentAdapter` supports bearer token authentication for secured A2A endpoints:

```python
# Direct token
adapter = A2AAgentAdapter(
    agent_url="https://agent.example.com",
    auth_token="your-bearer-token",
)

# Environment variable fallback (A2A_AGENT_URL, A2A_AUTH_TOKEN)
adapter = A2AAgentAdapter()

# No auth (local / unsecured agents)
adapter = A2AAgentAdapter(
    agent_url="http://localhost:8080",
)
```

## Usage

```python
from beddel_agent_a2a import A2AAgentAdapter, discover_agent

# Discover agent capabilities via Agent Card (typed response)
card = await discover_agent("https://agent.example.com")
print(card.name, card.skills)

# Create adapter and execute a task
adapter = A2AAgentAdapter(
    agent_url="https://agent.example.com",
)

# Synchronous execution (collects full response)
result = await adapter.execute(
    prompt="Summarize the quarterly report",
)
print(result.output)

# Streaming execution (yields events as they arrive)
async for event in adapter.stream(prompt="Analyze this data"):
    if event["type"] == "status":
        print(f"Status: {event['state']}")
    elif event["type"] == "artifact":
        print(f"Output: {event['parts']}")
    elif event["type"] == "message":
        print(f"Message: {event['text']}")
```

## Agent Discovery

A2A agents expose an Agent Card describing their capabilities. The `discover_agent` helper fetches this with automatic path fallback:

- Primary: `/.well-known/agent-card.json` (current A2A spec)
- Fallback: `/.well-known/agent.json` (legacy compatibility)

```python
from beddel_agent_a2a import discover_agent
from a2a.types import AgentCard

card: AgentCard = await discover_agent("https://agent.example.com")

# Typed access to agent capabilities
print(f"Agent: {card.name}")
print(f"Skills: {[s.name for s in card.skills]}")
print(f"Version: {card.version}")
```

## Supported Operations

| Operation | Method | Description |
|-----------|--------|-------------|
| `execute()` | `message/send` | Send a message and collect the full response |
| `stream()` | `message/send` (streaming) | Send a message and yield events as they arrive |
| `discover_agent()` | GET Agent Card | Fetch typed Agent Card with path fallback |

## Protocol Details

This kit uses the A2A protocol `message/send` method via the official SDK client.
The SDK handles JSON-RPC transport, SSE streaming, and response parsing internally.

| Protocol Method | SDK Mechanism | Adapter Method |
|-----------------|---------------|----------------|
| `message/send` | `Client.send_message()` (non-streaming) | `execute()` |
| `message/send` | `Client.send_message()` (streaming) | `stream()` |

## Testing

```bash
cd kits/agent-a2a-kit
PYTHONPATH=python:$PYTHONPATH pytest tests/ -q
```
