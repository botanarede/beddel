# provider-gemini-kit

Google Gemini direct provider adapter for the Beddel SDK. Implements the `ILLMProvider` port to execute completions and streaming via the `google-genai` SDK, providing direct access to Gemini models without the LiteLLM intermediary.

## Dependencies

- `google-genai>=1.0.0`

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `src/` directory to your Python path:

```bash
export PYTHONPATH="kits/provider-gemini-kit/src:$PYTHONPATH"
```

Or install the Beddel SDK with the Gemini extra:

```bash
pip install beddel[provider-gemini]
```

## Usage

```python
from beddel_provider_gemini.adapter import GeminiLLMProvider

# Uses GOOGLE_API_KEY env var, or falls back to ADC
provider = GeminiLLMProvider()

# Single-turn completion
result = await provider.complete(
    "gemini-3.1-pro",
    [{"role": "user", "content": "Hello!"}],
)
print(result["content"])

# Streaming
async for chunk in provider.stream(
    "gemini-3-flash",
    [{"role": "user", "content": "Hello!"}],
):
    print(chunk, end="")
```

## Configuration

### Authentication

| Method | Description |
|--------|-------------|
| `GOOGLE_API_KEY` env var | Checked first; passed as `api_key` to the client |
| Application Default Credentials (ADC) | Fallback when no API key is set |

### Vertex AI ADC

When no `GOOGLE_API_KEY` is set, the adapter falls back to Vertex AI mode using Application Default Credentials:

```python
# Set GCP project (required for Vertex AI)
export GOOGLE_CLOUD_PROJECT=my-project-id
export GOOGLE_CLOUD_LOCATION=us-central1  # optional, defaults to us-central1

# Authenticate via gcloud
gcloud auth application-default login

provider = GeminiLLMProvider()  # Uses Vertex AI ADC automatically
```

| Env Var | Required | Default | Description |
|---------|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Yes (for Vertex AI) | — | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | No | `us-central1` | GCP region |

### Safety Settings

Pass Gemini safety settings via the `safety_settings` kwarg:

```python
result = await provider.complete(
    "gemini-3.1-pro",
    [{"role": "user", "content": "Summarize this article."}],
    safety_settings=[
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
    ],
)
```

## Supported Models

| Model ID | Description |
|----------|-------------|
| `gemini-3.1-pro` | Gemini 3.1 Pro — high capability |
| `gemini-3-flash` | Gemini 3 Flash — fast and efficient |
| `gemma-4` | Gemma 4 — open model |

Models are passed directly to the Gemini API (no prefix mapping needed).

## Running Tests

```bash
cd kits/provider-gemini-kit
python -m pytest tests/ -x
```
