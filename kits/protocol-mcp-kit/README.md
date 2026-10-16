# protocol-mcp-kit

MCP (Model Context Protocol) client adapters for the Beddel SDK. Provides stdio, SSE and Streamable HTTP transport clients that implement the `IMCPClient` port, plus a JSON Schema validator for tool arguments. The Streamable HTTP client reaches **remote** servers and performs MCP authorization (OAuth) through the official SDK.

Transports, OAuth and token storage live in this kit and never in the core (AD-21). The core depends on neither the SDK nor the specification revision named below.

## Dependencies and pins

| Item | Value |
| --- | --- |
| MCP SDK | `mcp==2.3.0` — an exact pin, so the upper bound is the pin itself; major line **2** |
| SDK Python requirement | `>=3.10` (compatible with the core's `>=3.12`) |
| MCP specification revision implemented | **2026-07-28** (Streamable HTTP transport and authorization). The SDK negotiates down to the earlier `initialize` handshake for servers that predate it. |
| JSON Schema | `jsonschema>=4.0` |

`httpx2`, `mcp-types`, `pydantic` and `anyio` are imported by the Streamable HTTP client and arrive with the SDK pin (`mcp-types` is pinned by `mcp` to its own version); they are not declared separately so the one SDK pin controls the line. The pin is recorded in `kit.yaml` and here. Bumping it is a deliberate kit change.

The 2026-07-28 authorization revision asks for credentials to be bound to the authorization server (`issuer`) and prefers Client ID Metadata Documents over Dynamic Client Registration. The kit satisfies this through the SDK: the SDK stamps and checks the `issuer` on the stored client registration and re-registers when the authorization server changes; the kit's store discards the tokens issued under a replaced registration in the same write (see *Credential binding*); the operator command accepts `--client-metadata-url` so the SDK uses a Client ID Metadata Document when the authorization server supports it, falling back to dynamic registration otherwise.

## Streamable HTTP client (`StreamableHTTPMCPClient`)

### Names (proposed here; confirmed by the owner at review)

| What | Value | Why |
| --- | --- | --- |
| Adapter `name` (the value a workflow writes as `transport`) | `mcp-streamable-http` | follows the kit's `mcp-<transport>` names (`mcp-stdio`, `mcp-sse`) and names the specification's transport, not the deprecated SSE one |
| Authorization method `none` | the server needs no authentication | explicit, never a default (decision D-11) |
| Authorization method `oauth` | OAuth through the SDK, with credentials the operator stored beforehand | the one interactive method |

A workflow entry looks like:

```yaml
mcp_servers:
  remote_tools:
    transport: mcp-streamable-http
    endpoint: https://mcp.example.com/mcp
    authorization: oauth
```

### Construction and lifecycle contract

This contract is written once here; the fake adapter of the integration stories follows the same one.

1. **Constructor from the entry's fields, no I/O.** `StreamableHTTPMCPClient(transport=..., endpoint=..., authorization=...)` takes the entry's three fields by name and validates them. It opens no socket, reads or writes no file, creates no directory and builds no SDK object. A `transport` other than `mcp-streamable-http`, an unknown `authorization` method, or a refused endpoint raises a Beddel `MCPError` (`BEDDEL-MCP-600`) with a fixed message that never contains the offending value.
2. **Connection on first call.** The first `list_tools` or `call_tool` connects. The core never calls `connect`; calling it is accepted only for the same endpoint (any other raises `BEDDEL-MCP-600`).
3. **Safe disconnect.** `disconnect` works whether or not a connection was made, repeatedly, and after a cancelled call (the step `timeout` is enforced by the core and cancels the call; the client stays usable and closable).

Keyword-only options (all with defaults; the step `timeout` is enforced by the core and bounds them): `connect_timeout=10.0`, `request_timeout=30.0`, `sse_read_timeout=300.0`, `max_connect_retries=2`, `retry_backoff=0.5`, `credentials_dir=None`, `allow_insecure_loopback=False`, `httpx_transport=None` (test seam).

### Authorization methods

* **`none`** — for a server that needs no authentication. It never bypasses authentication a server requires: if the server answers `401` or `403`, the call fails with `BEDDEL-MCP-605` (`MCP_AUTHORIZATION_REQUIRED`); no login is started, nothing is retried with other credentials, and exactly one request reaches the server.
* **`oauth`** — the SDK's `OAuthClientProvider`. A workflow run only **reads** credentials the operator stored. Missing, expired-and-not-refreshable or revoked credentials fail the call with `BEDDEL-MCP-605` before any request when nothing is stored, or when the server rejects the stored credentials. The message names the operator action and carries no SDK or transport text. The client never opens a browser, prompts, runs a login or registers a client during a run. An expired access token with a refresh token is refreshed by the SDK and the call proceeds; a failed refresh produces the same `BEDDEL-MCP-605` for that call only.
* Any other method name makes the constructor raise `BEDDEL-MCP-600` (no I/O).

### Operator authorization (outside any workflow run; not a `beddel` command)

```bash
python -m beddel_protocol_mcp.authorize --endpoint https://mcp.example.com/mcp
```

It runs the OAuth authorization-code flow with PKCE through the SDK, prints the authorization URL (and opens it in the browser unless `--no-browser`), receives the redirect on a callback server bound explicitly to `127.0.0.1`, and stores the credentials. It prints no token, code or secret. Options: `--authorization` (only `oauth` has a flow), `--port` (callback port on 127.0.0.1; set it when the authorization server only accepts the registered redirect URI), `--timeout`, `--client-metadata-url` (HTTPS Client ID Metadata Document URL), `--credentials-dir`, `--no-browser`.

### Settings and environment variables

| Name | Meaning | Default |
| --- | --- | --- |
| `BEDDEL_MCP_CREDENTIALS_DIR` | Directory holding the stored credentials (read by runs and by the operator command). Must be outside any repository, owned by the user, mode `0700`. | `~/.beddel/mcp-credentials` |

No other environment variable is read. The constructor options above are code arguments, not environment settings.

### Credential binding and storage

* Credentials are stored and looked up by the **canonical endpoint URL together with the authorization method name** — never by the workflow's server key. The canonical form lower-cases scheme and host, drops a default port and renders an empty path as `/`. A token stored for one endpoint is never presented to another, and the operator command names the endpoint it authorizes.
* One file per pair, named by a SHA-256 of the pair, created with `os.open(..., 0o600)` from the first byte (not tightened afterwards) and atomically replaced; the record repeats the endpoint and method and the reader checks them. The directory is created `0700`; a directory or file that is group/world accessible, not owned by the user, or inside the git work tree of the current directory or of this kit is refused. POSIX only. The directory is opened with `O_DIRECTORY | O_NOFOLLOW` and checked with `fstat`, files are created, read and replaced relative to that descriptor (`dir_fd`), and the directory is fsynced after the replace, so swapping a parent directory after the check cannot redirect a write and the rename survives a crash.
* The authorization server (`issuer`) is enforced **inside the record**, not in the file key: the key is endpoint + method (AC 5), and the issuer is stamped on the client registration the SDK stores. The SDK drops a registration whose issuer no longer matches the one the server advertises (and a run then fails with `BEDDEL-MCP-605` rather than registering); the store discards the tokens issued under a replaced registration in the same write. Credentials are therefore bound to endpoint **and** issuer without the issuer being part of the file name.
* The absolute expiry of the access token is persisted; the kit hands it to the SDK so an expired token is refreshed (when a refresh token is held) instead of being presented first. If the authorization server gives no `expires_in`, expiry is unknown and a rejected token ends in `BEDDEL-MCP-605`.

### Endpoint validation

The endpoint must be HTTPS. Plain `http` is accepted only for a loopback host and only when the code passes `allow_insecure_loopback=True` (the kit's tests do; a workflow cannot). Userinfo, any query string and any fragment are refused (the core's strictest rule, repeated here), before connecting.

### Errors and retries

| Situation | Error |
| --- | --- |
| Refused endpoint, unknown method, wrong transport name, connect() for another endpoint | `MCPError` `BEDDEL-MCP-600` |
| Authorization missing, expired, revoked, insufficient, or `none` against a protected server | `MCPError` `BEDDEL-MCP-605` (`MCP_AUTHORIZATION_REQUIRED`) |
| Unreachable server or lost connection | `MCPError` `BEDDEL-MCP-600` (`MCP_CONNECTION_FAILED`) |
| Silent server / request timeout | `MCPError` `BEDDEL-MCP-604` (`MCP_SERVER_TIMEOUT`) |
| Tool result with `isError`, or a JSON-RPC error | `MCPError` `BEDDEL-MCP-602` (`MCP_TOOL_INVOCATION_FAILED`) |

Only **connection establishment** is retried (default 2 extra attempts, doubling backoff); a tool call is never retried, and neither is an attempt that already sent a `grant_type=refresh_token` request (a rotating refresh token may have been consumed). Messages are fixed sentences plus the endpoint (which carries no userinfo or query) and the exception class name; no token, SDK text or server text is placed in a message or `details`, and no SDK or transport exception is left chained (`__context__`/`__cause__` are `None`) on the errors the kit raises.

`list_tools` descriptors carry `name`, `description` and `inputSchema` (the key the tool primitive reads).

## Other transports

```python
from beddel_protocol_mcp.stdio_client import StdioMCPClient

client = StdioMCPClient(command="my-mcp-server", args=["--flag"])
await client.connect("stdio://my-mcp-server")

tools = await client.list_tools()
result = await client.call_tool("tool-name", {"arg": "value"})

await client.disconnect()
```

```python
from beddel_protocol_mcp.sse_client import SSEMCPClient

client = SSEMCPClient(url="http://localhost:8080/mcp")
await client.connect("sse://localhost:8080/mcp")
```

On SDK line 2 the stdio and SSE clients needed one bounded change: `Tool.inputSchema` became `Tool.input_schema`, so both now read `input_schema` (without it they silently returned `{}`). Their other behaviour and tests are unchanged. They are not registered by the MVP composition root (AD-21: stdio is not declarable; SSE is not selected).

### Known asymmetry (AD-15)

The manifest declares the SSE adapter for Python but **not** for TypeScript, although a TypeScript SSE source exists (`typescript/src/mcp-sse-client.ts`). The TypeScript target also has no Streamable HTTP adapter. This is recorded, not fixed: no TypeScript adapter is added here.

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

`beddel` and the pinned `mcp` must be importable (`tests/conftest.py` adds the kit's `python/` directory to `sys.path`). The Streamable HTTP tests use an in-process fake MCP server and an OAuth stub served through an `httpx2` ASGI transport: no network, no real destination, no credential. Only the operator command's callback test touches the loopback interface.
