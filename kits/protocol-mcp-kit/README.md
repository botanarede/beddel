# protocol-mcp-kit

MCP (Model Context Protocol) client adapters for the Beddel SDK. Provides stdio and SSE transport clients that implement the `IMCPClient` port, plus a JSON Schema validator for tool arguments.

## Dependencies

- `mcp>=1.0` — MCP SDK for stdio and SSE transports
- `jsonschema>=4.0` — JSON Schema validation for tool arguments

## Usage

```python
from beddel_protocol_mcp.stdio_client import StdioMCPClient

client = StdioMCPClient(command="my-mcp-server", args=["--flag"])
await client.connect("stdio://my-mcp-server")

tools = await client.list_tools()
result = await client.call_tool("tool-name", {"arg": "value"})

await client.disconnect()
```

### SSE Transport

```python
from beddel_protocol_mcp.sse_client import SSEMCPClient

client = SSEMCPClient(url="http://localhost:8080/mcp")
await client.connect("sse://localhost:8080/mcp")
```

### Schema Validation

```python
from beddel_protocol_mcp.schema_validator import validate_tool_arguments

validate_tool_arguments({"name": "Alice", "age": 30}, tool_schema)
```

## Testing

```bash
cd kits/protocol-mcp-kit
python -m pytest tests/ -x
```
