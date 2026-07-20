# provider-kimi-kit

Kimi K3 LLM provider adapter for Beddel SDK via OpenAI-compatible API.

## Overview

Implements `ILLMProvider` port using `AsyncOpenAI` client pointing at `https://api.moonshot.ai/v1`.

## Features

- `complete()` — single-turn completion with reasoning extraction
- `stream()` — streaming tokens (content only, reasoning filtered)
- K3 model-policy normalization (fixed params: temperature/top_p/n/penalties)
- Vision support (base64 only, URL rejection)
- Error mapping to BEDDEL-ADAPT-060..063

## Configuration

| Env Var | Required | Description |
|---------|----------|-------------|
| `MOONSHOT_API_KEY` | Yes | Moonshot API key for authentication |

## Usage

```python
from beddel_provider_kimi import KimiLLMProvider

provider = KimiLLMProvider()
result = await provider.complete(
    model="kimi-k3",
    messages=[{"role": "user", "content": "Hello!"}],
    max_completion_tokens=2000,
    reasoning_effort="max",
)
print(result["content"])    # Final response
print(result["reasoning"])  # Thinking content (K3/K2.7)
```

## Models

| Model | Notes |
|-------|-------|
| kimi-k3 | Frontier reasoning, fixed temp/top_p/n/penalties |
| kimi-k2.7 | Thinking always on, cannot disable |
| kimi-k2.6 | Thinking can be toggled via extra_body |

## K3 Constraints

- temperature, top_p, n, penalties: FIXED, do not send
- tool_choice: only "required" or "none" (not "auto")
- Vision: base64 content parts ONLY (no URLs)
