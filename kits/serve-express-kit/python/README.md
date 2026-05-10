# serve-express-kit — Python target (unavailable)

**Status:** unavailable
**Peer kit:** [`serve-fastapi-kit`](../../serve-fastapi-kit/)

## Why no Python target

Express is a JavaScript/TypeScript-only HTTP framework. Its middleware pipeline and request/response abstractions are not portable to Python.

## Use this instead

For Python projects needing this capability, use the peer kit
[`serve-fastapi-kit`](../../serve-fastapi-kit/), which is the Python-ecosystem equivalent
and covers the same use case using PyPI packages and Python idioms.

## Status declaration

This stub directory documents the unavailability explicitly. The kit
manifest [`../kit.yaml`](../kit.yaml) declares `targets.python.status:
unavailable` with the same rationale.
