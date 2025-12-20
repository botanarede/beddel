# AGENTS.md — Beddel Protocol

> **Language Policy**: The native language of the Beddel protocol is **English**. All code, comments, commit messages, documentation, and agent manifests **must be written in English**. This ensures consistency, broader accessibility, and seamless integration with AI agents.

This document provides essential context for AI agents and developers working on the `packages/beddel` codebase. It complements `README.md` with implementation details, navigation guides, and operational instructions.

---

## 1. Project Overview

**Beddel** is a security-hardened YAML execution toolkit for building declarative AI agents. It provides:

- **Secure YAML parsing** with strict schema validation
- **Isolated runtime environments** with sandboxed execution
- **Declarative agent definitions** via YAML manifests
- **Built-in compliance** (GDPR/LGPD) and audit trails
- **Multi-tenant Firebase support** with tenant isolation

**Target Users**: Backend teams embedding declarative YAML agents in Node.js services.

---

## 2. Source Tree Structure

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| `src/parser` | Secure YAML parsing with FAILSAFE schema | `SecureYamlParser` |
| `src/runtime` | Isolated execution, declarative interpreter, workflow executor | `DeclarativeAgentInterpreter`, `workflowExecutor` |
| `src/agents` | Agent registry and sharded agent modules | `AgentRegistry`, `*/index.ts`, `*/*.handler.ts` |
| `src/shared` | Client-safe types and utilities | `types/`, `utils/` |
| `src/client` | Client-safe exports | `index.ts`, `types.ts` |
| `src/security` | Threat detection, scoring, hardening | `SecurityScanner` |
| `src/compliance` | GDPR/LGPD compliance engines | `GDPRCompliance`, `LGPDCompliance` |
| `src/audit` | Hash-based audit trail logging | `AuditTrail` |
| `src/firebase` | Multi-tenant Firebase management | `MultiTenantFirebaseManager` |
| `src/performance` | Monitoring, autoscaling, benchmarking | `PerformanceMonitor` |
| `src/integration` | High-level runtime glue | `SecureYamlRuntime` |

All exports are centralized in `src/index.ts`.

---

## 3. Setup Commands

```bash
# Install dependencies
pnpm install

# Build the package
pnpm --filter beddel build

# Run tests
pnpm --filter beddel test

# Run linting
pnpm --filter beddel lint
```

---

## 4. Code Style Guidelines

### General Rules

- **Language**: All code, comments, and documentation must be in English
- **TypeScript**: Use strict typing; avoid `any` unless absolutely necessary
- **Naming**: Use camelCase for variables/functions, PascalCase for classes/interfaces
- **Imports**: Prefer named exports; group imports by external/internal

### YAML Parsing Rules

- Always use `js-yaml` with `FAILSAFE_SCHEMA` — never enable custom tags
- Respect `YAMLParserConfig` limits (depth, keys, string length, UTF-8 validation)
- Any relaxation of limits requires justification and new tests

### Runtime Rules

- `IsolatedRuntimeManager` maintains an isolate pool; dangerous globals (`require`, `eval`, timers) are stripped
- New module allowlists must be added to `securityProfiles` with explicit justification
- `SimpleIsolatedRuntimeManager` is for low-overhead scenarios; keep it minimal

### Security Rules

- `SecurityScanner` is synchronous — avoid I/O heavy operations in hot paths
- Compliance engines assume `AuditTrail` is available; pass singletons when possible
- Never store raw secrets in audit logs; use `sanitizeForAudit`

---

## 5. Agent Development

### Declarative Agent Structure

Agent manifests live in `src/agents/{agent-name}/` with a sharded structure:

```
src/agents/joker/
├── joker.yaml           # Agent definition
├── joker.handler.ts     # Server-only execution logic
├── joker.schema.ts      # Zod validation schemas
├── joker.types.ts       # TypeScript type definitions
└── index.ts             # Public exports (client-safe)
```

### Supported Workflow Step Types

| Step Type | Description | Required Props |
|-----------|-------------|----------------|
| `output-generator` | Returns literal or computed values | — |
| `genkit-joke` | Generates jokes via Gemini | `gemini_api_key` |
| `genkit-translation` | Translates text via Gemini | `gemini_api_key` |
| `genkit-image` | Generates images via Gemini | `gemini_api_key` |
| `mcp-tool` | Invokes MCP server tools | — |
| `gemini-vectorize` | Generates text embeddings | `gemini_api_key` |
| `chromadb` | Vector storage and retrieval | — |
| `gitmcp` | Fetches GitHub documentation | — |
| `rag` | RAG answer generation | `gemini_api_key` |
| `custom-action` | Executes custom TypeScript functions | Varies |

### Built-in Agents

| Agent | Method | Required Props | Description |
|-------|--------|----------------|-------------|
| `joker/joker.yaml` | `joker.execute` | `gemini_api_key` | Generates short jokes |
| `translator/translator.yaml` | `translator.execute` | `gemini_api_key` | Text translation with metadata |
| `image/image.yaml` | `image.generate` | `gemini_api_key` | Image generation with base64 output |
| `mcp-tool/mcp-tool.yaml` | `mcp-tool.execute` | — | MCP server tool invocation |
| `gemini-vectorize/gemini-vectorize.yaml` | `gemini-vectorize.execute` | `gemini_api_key` | Text embeddings |
| `chromadb/chromadb.yaml` | `chromadb.execute` | — | Vector storage/retrieval |
| `gitmcp/gitmcp.yaml` | `gitmcp.execute` | — | GitHub documentation fetching |
| `rag/rag.yaml` | `rag.execute` | `gemini_api_key` | RAG answer generation |
| `chat/chat.yaml` | `chat.execute` | `gemini_api_key` | RAG pipeline orchestrator |

### Custom Agents

Custom agents can be created in the application's `/agents` directory:

1. Create a YAML manifest defining the agent schema and workflow
2. Create a corresponding TypeScript file for custom logic
3. The `AgentRegistry` automatically loads agents from `/agents` with higher priority than built-in agents

---

## 6. Testing Instructions

### Test Commands

```bash
# Run all tests
pnpm --filter beddel test

# Run specific test files
node packages/beddel/tests/test-runtime.js
node packages/beddel/tests/test-runtime-security.js
```

### Test Requirements

- Add regression tests for any runtime changes in `tests/`
- Mock `firebase-admin` or guard tests behind environment checks
- Security-focused tests (`test-runtime-security.js`, `test-session*`) cover threat detection and isolation
- Schema validation changes require tests for caching, invalid payloads, and output rejection

---

## 7. Boundaries and Guardrails

### What Agents SHOULD Do

- ✅ Use existing utilities from `src/` before creating new ones
- ✅ Follow the YAML FAILSAFE schema strictly
- ✅ Add tests for any new functionality
- ✅ Update documentation when modifying APIs

### What Agents SHOULD NOT Do

- ❌ Modify security profiles without explicit approval
- ❌ Enable custom YAML tags or relax parsing limits without justification
- ❌ Store secrets or sensitive data in logs
- ❌ Create new directories without checking if functionality fits existing concerns
- ❌ Write code or documentation in languages other than English

### Files Requiring Caution

- `src/security/*` — Core security logic; changes require thorough review
- `src/parser/SecureYamlParser.ts` — Parsing security; modifications need justification
- `src/runtime/IsolatedRuntimeManager.ts` — Sandbox isolation; high-risk changes

---

## 8. Documentation Sync Duties

When making changes, ensure documentation stays synchronized:

| Change Type | Update Required |
|-------------|-----------------|
| Code changes | Update `README.md` and `AGENTS.md` |
| API changes | Update `docs/` and export list in `src/index.ts` |
| New agents | Add to agent catalog in this file |
| Spec changes | Reflect in `docs/beddel` |
| Schema changes | Document in interpreter section |

---

## 9. Contribution Checklist

Before submitting changes:

- [ ] Code and comments are in English
- [ ] Understand the modules being modified (see source tree)
- [ ] Tests added or updated for changes
- [ ] `README.md` and `AGENTS.md` updated
- [ ] `pnpm --filter beddel build` passes
- [ ] `pnpm --filter beddel lint` passes
- [ ] Roadmap gaps documented in README

---

## 10. Handling Uncertainty

When encountering ambiguous requirements or edge cases:

1. **Ask clarifying questions** before implementing
2. **Propose a plan** and wait for approval on significant changes
3. **Document assumptions** in code comments and commit messages
4. **Create draft PRs** with implementation notes for review

---

## 11. Git Workflow

### Commit Message Format

```
<type>: <short description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

### Branch Naming

- Features: `feat/<description>`
- Fixes: `fix/<description>`
- Documentation: `docs/<description>`

---

*This document is living documentation. Update it as the codebase evolves.*
