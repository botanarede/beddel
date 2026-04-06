# observability-otel-kit

OpenTelemetry tracing adapter for the Beddel SDK. Implements the `ITracer` port to emit spans via the OpenTelemetry API.

## Dependencies

- `opentelemetry-api>=1.0`

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `src/` directory to your Python path:

```bash
export PYTHONPATH="kits/observability-otel-kit/src:$PYTHONPATH"
```

## Usage

```python
from beddel_observability_otel.adapter import OpenTelemetryAdapter

adapter = OpenTelemetryAdapter(service_name="my-service")

# Start and end spans
span = adapter.start_span("beddel.workflow", attributes={"beddel.model": "gpt-4o"})
adapter.end_span(span, attributes={"gen_ai.usage.total_tokens": 150})
```

## Running Tests

```bash
cd kits/observability-otel-kit
python -m pytest tests/ -x
```
