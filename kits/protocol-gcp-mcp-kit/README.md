# protocol-gcp-mcp-kit

Google Managed MCP Server client adapter for the Beddel SDK. Provides a multi-server `GCPMCPClient` that implements the `IMCPClient` port, connecting to Google's remote MCP servers via SSE transport with Application Default Credentials (ADC) authentication.

## Dependencies

- `mcp>=1.0` — MCP SDK for SSE transport
- `google-auth>=2.0` — Google authentication (ADC, OAuth2 bearer tokens)

## Supported Google Managed MCP Servers

| Server | Endpoint Pattern | Example Tools |
|--------|-----------------|---------------|
| BigQuery | `.../mcpServers/bigquery` | `query`, `list_tables`, `get_schema` |
| Google Maps | `.../mcpServers/google-maps` | `geocode`, `directions`, `places_search` |
| Cloud SQL | `.../mcpServers/cloudsql-mysql` | `execute_query`, `list_databases` |
| Firestore | `.../mcpServers/firestore` | `get_document`, `query_collection` |
| Spanner | `.../mcpServers/spanner` | `execute_sql`, `read_rows` |
| Cloud Storage | `.../mcpServers/cloud-storage` | `list_objects`, `get_object` |

Endpoint pattern: `https://mcp.googleapis.com/v1alpha/projects/{project}/locations/global/mcpServers/{server}`

## Authentication Setup

`GCPMCPClient` uses Application Default Credentials (ADC). Set up credentials using one of:

```bash
# Local development — user credentials
gcloud auth application-default login

# Service account (CI/CD, Cloud Run)
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

The client automatically refreshes OAuth2 tokens and injects `Authorization: Bearer <token>` headers into SSE connections.

## Usage

```python
from beddel_protocol_gcp_mcp.client import GCPMCPClient

client = GCPMCPClient(
    servers=[
        {
            "name": "bigquery",
            "endpoint": "https://mcp.googleapis.com/v1alpha/projects/my-project/locations/global/mcpServers/bigquery",
        },
        {
            "name": "google-maps",
            "endpoint": "https://mcp.googleapis.com/v1alpha/projects/my-project/locations/global/mcpServers/google-maps",
        },
    ],
)

await client.connect("")
tools = await client.list_tools()       # Aggregated from all servers
result = await client.call_tool("query", {"sql": "SELECT 1"})
await client.disconnect()
```

## Testing

```bash
cd kits/protocol-gcp-mcp-kit
python -m pytest tests/ -x
```
