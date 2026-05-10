# provider-vercelai-kit — Python target (unavailable)

**Status:** unavailable
**Peer kit:** [`provider-litellm-kit`](../../provider-litellm-kit/)

## Why no Python target

Vercel AI SDK is a JavaScript/TypeScript-only multi-provider router. There is no Python port of the Vercel AI SDK ecosystem (`ai`, `@ai-sdk/openai`, `@ai-sdk/anthropic`, `@ai-sdk/google`).

## Use this instead

For Python projects needing this capability, use the peer kit
[`provider-litellm-kit`](../../provider-litellm-kit/), which is the Python-ecosystem equivalent
and covers the same use case using PyPI packages and Python idioms.

## Status declaration

This stub directory documents the unavailability explicitly. The kit
manifest [`../kit.yaml`](../kit.yaml) declares `targets.python.status:
unavailable` with the same rationale.
