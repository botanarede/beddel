# provider-litellm-kit — TypeScript target (unavailable)

**Status:** unavailable
**Peer kit:** [`provider-vercelai-kit`](../../provider-vercelai-kit/)

## Why no TypeScript target

LiteLLM is a Python-only multi-provider LLM router. Its adapter resolution, retry
logic, and provider-specific quirk handling are implemented as a Python package
with no equivalent JavaScript/TypeScript port. Re-implementing LiteLLM's full
provider matrix in TS is out of scope.

## Use this instead

For TypeScript projects needing multi-provider LLM routing, use the peer kit
[`provider-vercelai-kit`](../../provider-vercelai-kit/), which is the JS/TS
ecosystem equivalent built on the Vercel AI SDK (`ai` + `@ai-sdk/openai`,
`@ai-sdk/anthropic`, `@ai-sdk/google`). It covers the same use case (one
configuration, many providers) via the Vercel AI SDK's `streamText` / `generateText`
abstractions.

## Status declaration

This stub directory documents the unavailability explicitly. The kit manifest
[`../kit.yaml`](../kit.yaml) declares `targets.typescript.status: unavailable`
with the same rationale.
