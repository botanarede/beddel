# provider-litellm-kit

LiteLLM multi-provider LLM adapter.

## Dependencies

- `litellm>=1.40`

## Adapters

| Port | Implementation | Description |
|------|---------------|-------------|
| ILLMProvider | LiteLLMAdapter | Multi-provider LLM access via LiteLLM |

## Usage

Install and initialize Beddel:

```
pip install beddel && beddel init
```

The kit is auto-discovered by the Beddel engine when its dependencies are installed.
