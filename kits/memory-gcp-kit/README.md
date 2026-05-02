# memory-gcp-kit

GCP Agent Engine Memory Bank adapter for the Beddel SDK. Provides a `GCPMemoryProvider` that implements the `IMemoryProvider` port, enabling persistent episodic memory storage via Google Cloud's Agent Engine Memory Bank with Application Default Credentials (ADC) authentication.

## Dependencies

- `google-cloud-aiplatform>=1.80.0` — Google Cloud AI Platform SDK (includes Agent Engine Memory Bank)

## Installation

```bash
pip install google-cloud-aiplatform
```

## Authentication Setup

`GCPMemoryProvider` uses Application Default Credentials (ADC). Set up credentials using one of:

```bash
# Local development — user credentials
gcloud auth application-default login

# Service account (CI/CD, Cloud Run)
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

The provider automatically uses ADC to authenticate with the GCP Agent Engine Memory Bank API.

## Usage

```python
from beddel_memory_gcp.provider import GCPMemoryProvider

provider = GCPMemoryProvider(
    project="my-gcp-project",
    location="us-central1",
)

# Store a memory entry
await provider.set(
    key="task-summary",
    value="Completed data pipeline refactor",
    scope={"agent_id": "planner-agent"},
)

# Retrieve a memory entry
entry = await provider.get(
    key="task-summary",
    scope={"agent_id": "planner-agent"},
)

# Search memories by semantic similarity
results = await provider.search(
    query="pipeline refactor",
    scope={"agent_id": "planner-agent"},
    limit=5,
)

# List episodes for a scope
episodes = await provider.list_episodes(
    scope={"agent_id": "planner-agent"},
)
```

## Memory Profiles

Memory entries are scoped using profile dictionaries:

| Profile | Scope Dict | Use Case |
|---------|-----------|----------|
| Agent-level | `{"agent_id": "planner-agent"}` | Per-agent memory isolation |
| User-level | `{"user_id": "user-123"}` | Per-user memory across agents |

Scopes map to Agent Engine Memory Bank resource paths, ensuring memory isolation between agents and users.

## Supported Operations

| Operation | Description |
|-----------|-------------|
| `get` | Retrieve a memory entry by key and scope |
| `set` | Store or update a memory entry |
| `search` | Semantic similarity search within a scope |
| `list_episodes` | List all episodes for a given scope |

## Testing

```bash
cd kits/memory-gcp-kit
python -m pytest tests/ -x
```
