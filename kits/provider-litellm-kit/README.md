# provider-litellm-kit

LiteLLM provider adapter for the Beddel SDK. Implements the `ILLMProvider` port to execute completions and streaming via LiteLLM's unified API across 100+ LLM providers.

## Dependencies

- `litellm>=1.40,<1.82.7`

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `src/` directory to your Python path:

```bash
export PYTHONPATH="kits/provider-litellm-kit/src:$PYTHONPATH"
```

Or install the Beddel SDK with the litellm extra (when available):

```bash
pip install beddel[litellm]
```

## Usage

```python
from beddel_provider_litellm.adapter import LiteLLMAdapter

adapter = LiteLLMAdapter(default_api_key="sk-...")

# Single-turn completion
result = await adapter.complete("openai/gpt-4o", [{"role": "user", "content": "Hello!"}])
print(result["content"])

# Streaming
async for chunk in adapter.stream("openai/gpt-4o", [{"role": "user", "content": "Hello!"}]):
    print(chunk, end="")
```

## Running Tests

```bash
cd kits/provider-litellm-kit
python -m pytest tests/ -x
```
