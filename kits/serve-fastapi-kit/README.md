# serve-fastapi-kit

FastAPI serving kit for the Beddel SDK. Provides the HTTP handler, SSE streaming, and dashboard integration (auth middleware, agent pipeline router, inspector, history).

## Dependencies

- `fastapi>=0.100`
- `sse-starlette>=1.6`

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `src/` directory to your Python path:

```bash
export PYTHONPATH="kits/serve-fastapi-kit/src:$PYTHONPATH"
```

Or install the kit dependencies directly:

```bash
pip install fastapi sse-starlette
```

## Usage

```python
from beddel_serve_fastapi.handler import create_beddel_handler

app = create_beddel_handler()
```

## Running Tests

```bash
cd kits/serve-fastapi-kit
python -m pytest tests/ -x
```
