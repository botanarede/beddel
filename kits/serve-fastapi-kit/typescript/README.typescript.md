# serve-fastapi-kit — TypeScript target (unavailable)

**Status:** unavailable
**Peer kit:** [`serve-express-kit`](../../serve-express-kit/)

## Why no TypeScript target

FastAPI is a Python-only ASGI framework. The kit's value (`create_beddel_handler`
factory + SSE adapter) is tightly coupled to FastAPI's `Request`/`Response`/`StreamingResponse`
abstractions and Starlette's middleware pipeline. There is no direct one-to-one
translation in the JavaScript/TypeScript ecosystem.

## Use this instead

For TypeScript projects needing HTTP-serving of Beddel workflows, use the peer
kit [`serve-express-kit`](../../serve-express-kit/), which is the JS/TS
ecosystem equivalent built on Express.js. It provides the same conceptual surface
(workflow-to-endpoint factory + SSE streaming) using Express middleware patterns.

## Status declaration

This stub directory documents the unavailability explicitly. The kit manifest
[`../kit.yaml`](../kit.yaml) declares `targets.typescript.status: unavailable`
with the same rationale.
