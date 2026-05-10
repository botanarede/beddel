# bridge-adk-kit — TypeScript target (planned)

**Status:** planned
**Planned entry point:** `./typescript/src/bridge.ts`

## Expected ports / tools

This README is a placeholder. The remote standardization agent (or any contributor)
should fill in the expected port/tool surface based on the Python implementation
under `../python/` and the kit role.

## Dependencies under consideration

TBD. Pick npm packages that map closest to the Python implementation's behavior.
Prefer packages already adopted by other Beddel TS kits when possible.

## Status: Planned

This kit's TypeScript implementation has not been written yet. The manifest
`targets.typescript` block declares it as `planned`. When implementation begins,
update the status to `implemented` and add `package`, `dependencies`, `tools`,
and `adapters` fields under `targets.typescript`.

## Dev note

TS implementation may route through @google/genai or the ADK Node SDK rather than the Python google-adk package. Verify ecosystem before implementation.
