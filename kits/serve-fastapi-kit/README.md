# serve-fastapi-kit

FastAPI serving + SSE.

## Dependencies

- `fastapi>=0.100`
- `sse-starlette>=1.6`
- `uvicorn>=0.23`

## Integrations

| Name | Description |
|------|-------------|
| create_beddel_handler | One-line workflow-to-endpoint factory with SSE streaming |
| BeddelSSEAdapter | SSE adapter for Beddel workflow event streams |
| BeddelServer | Background Uvicorn server lifecycle handle |
| start_beddel_server | Start an ASGI app in a daemon-thread Uvicorn server |

## Usage

Install this kit and its declared dependencies with:

```
beddel kit install serve-fastapi-kit
```

The kit is auto-discovered by the Beddel engine when its dependencies are installed.
