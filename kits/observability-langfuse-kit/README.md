# observability-langfuse-kit

Langfuse observability adapter for the Beddel SDK. Implements the `ITracer` port to send traces, spans, and cost data to a Langfuse instance.

## Dependencies

- `langfuse>=2.0`

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `src/` directory to your Python path:

```bash
export PYTHONPATH="kits/observability-langfuse-kit/src:$PYTHONPATH"
```

Or install the Beddel SDK with the langfuse extra (when available):

```bash
pip install beddel[langfuse]
```

## Usage

```python
from beddel_observability_langfuse.adapter import LangfuseTracerAdapter

tracer = LangfuseTracerAdapter(
    public_key="pk-lf-...",
    secret_key="sk-lf-...",
    host="http://localhost:3000",
)

# Start a trace span
span = tracer.start_span("beddel.workflow", attributes={"model": "gpt-4"})

# End the span with usage data
tracer.end_span(span, attributes={
    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
})

# Flush pending data
tracer.flush()

# Shutdown when done
tracer.shutdown()
```

## Running Tests

```bash
cd kits/observability-langfuse-kit
python -m pytest tests/ -x
```
