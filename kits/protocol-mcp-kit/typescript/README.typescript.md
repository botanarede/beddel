# protocol-mcp-kit

MCP (Model Context Protocol) client adapter for Beddel (AD-2: official SDK).

## Installation

```bash
pnpm add @beddel/protocol-mcp @modelcontextprotocol/sdk
```

## Usage — stdio transport

```typescript
import { MCPStdioClient } from "@beddel/protocol-mcp";

const client = new MCPStdioClient({ command: "npx", args: ["-y", "mcp-server-example"] });
await client.connect("stdio://mcp-server-example");
const tools = await client.listTools();
const result = await client.callTool("tool-name", { arg: "value" });
await client.disconnect();
```

## Usage — SSE/HTTP transport

```typescript
import { MCPSSEClient } from "@beddel/protocol-mcp/sse";

const client = new MCPSSEClient();
await client.connect("http://localhost:8080/mcp");
const tools = await client.listTools();
await client.disconnect();
```
