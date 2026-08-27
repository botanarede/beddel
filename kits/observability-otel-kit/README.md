# observability-otel-kit

OpenTelemetry observability tracing adapter.

## Dependencies

- `opentelemetry-api>=1.0`

## Adapters

| Port | Implementation | Description |
|------|---------------|-------------|
| ITracer | OpenTelemetryAdapter | Observability tracing via OpenTelemetry |

## Usage

Install and initialize Beddel:

```
pip install beddel && beddel init
```

The kit is auto-discovered by the Beddel engine when its dependencies are installed.
