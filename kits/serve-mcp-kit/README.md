# serve-mcp-kit

Expose Beddel YAML workflows as MCP servers. Any MCP-compatible agent (Claude, Kiro, Cursor, OpenClaw) can discover and execute workflows via the standard Model Context Protocol.

## Dependencies

- `mcp>=1.0` — MCP Python SDK (FastMCP server)

## Usage

```python
from beddel_serve_mcp.server import BeddelMCPServer, create_mcp_server

# Option 1: Scan a directory of YAML workflows
server = create_mcp_server("./workflows/")
server.run()  # stdio transport (default)

# Option 2: Register workflows manually
from beddel.domain.parser import WorkflowParser

server = BeddelMCPServer("My Workflows")
workflow = WorkflowParser.parse(open("workflow.yaml").read())
server.register_workflow(workflow)
server.run(transport="streamable-http", port=8000)
```

### How it works

Each YAML workflow becomes one MCP tool:
- `workflow.id` → tool name
- `workflow.description` → tool description
- `workflow.input_schema` → MCP `inputSchema`
- `WorkflowExecutor.execute()` → tool handler

### Transports

| Transport | Usage |
|-----------|-------|
| `stdio` (default) | Standard I/O — for IDE agents (Kiro, Claude, Cursor) |
| `streamable-http` | HTTP — for remote agents and dashboards |

## Testing

```bash
cd kits/serve-mcp-kit
python -m pytest tests/ -x
```
