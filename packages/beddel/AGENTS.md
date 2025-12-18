# AGENTS.md for the Beddel Package

Use this document as the operational guide for AI assistants and humans working on `packages/beddel`. It complements `README.md` with more implementation context, code navigation tips, and documentation duties.

## 1. Mission snapshot

- **Primary goal:** ship a security-hardened YAML execution toolkit (parser + runtimes + compliance) that matches what `docs/beddel` envisions, while keeping the npm package trustworthy and auditable.
- **Current scope:** the repository contains the hardened primitives (`src/parser`, `src/runtime`, `src/security`, etc.). Advanced declarative constructs mentioned in `docs/beddel/brief.md` are roadmap items—treat them as specs, not as implemented features.
- **Users:** backend teams embedding declarative YAML agents in Node.js services, plus internal tooling that relies on strict isolation/compliance guarantees.

## 2. Source tree essentials

| Directory | Purpose | Notes |
| --- | --- | --- |
| `src/parser` | `SecureYamlParser` & helpers | FAILSAFE schema, depth/size controls, async option. |
| `src/runtime` | `IsolatedRuntimeManager`, `SimpleIsolatedRuntimeManager`, declarative interpreter, audit service, monitoring hooks | Runtimes share `runtimeConfig` and `securityProfiles`. |
| `src/agents` | `AgentRegistry` + sample `joker-agent.yaml` | Registry auto-loads the sample agent at startup. |
| `src/security` | Scanner, scoring, hardening, threat detection | `SecurityScanner.scan` is used by `SecureYamlRuntime`. |
| `src/compliance` | GDPR/LGPD engines | Depend on `AuditTrail` for hash logging. |
| `src/audit` | `AuditTrail` (hash-based logging) | Consumed by Firebase manager and compliance engines. |
| `src/firebase` | `MultiTenantFirebaseManager` | Wraps `firebase-admin` for tenant isolation. |
| `src/performance` | Monitoring, autoscaling, benchmarking | Emits recommendations, threshold-based violations. |
| `src/integration` | `SecureYamlRuntime` glue | Parses + scans + executes YAML in a single flow. |

Everything is exported via `src/index.ts`. Before adding a new folder, decide whether it fits one of the existing concerns; if not, create a new directory and expose it through the index.

## 3. Implementation notes & guardrails

### Secure YAML parser

- Only use `js-yaml` with `FAILSAFE_SCHEMA`. Never enable custom tags.
- Respect `YAMLParserConfig` limits (depth, keys, string length, UTF-8 validation). Any relaxation must be justified and must include new tests inside `packages/beddel/tests`.
- `parseSecureAsync` simply defers to `parseSecure` on the next tick. If you need streaming parsing, create a new API instead of mutating the current one.

### Runtimes

- `IsolatedRuntimeManager` maintains an isolate pool and strips dangerous globals (`require`, `eval`, timers). If you add a feature that needs a module inside the isolate, extend `securityProfiles` and add explicit allowlists.
- `SimpleIsolatedRuntimeManager` is for lower-overhead environments. Keep it feature-light; deep changes belong to the main manager.
- `DeclarativeAgentInterpreter` currently supports literal/variable initialization plus the step types `output-generator`, `genkit-joke`, `genkit-translation` e `genkit-image`, sempre com validação em Zod via `DeclarativeSchemaCompiler`. Cada manifest precisa declarar `schema.input`/`schema.output` completos (objetos/arrays/primitivos com `type`). O interpreter valida input/output, devolve `DeclarativeSchemaValidationError` em caso de mismatch e expõe helpers `callGeminiFlashText|Translation|Image` que invocam `google("models/gemini-flash-latest")` usando Genkit. Todos os steps Genkit exigem `props.gemini_api_key` — sem ela a execução falha com erro amigável. Qualquer novo step precisa de validação + testes + updates no README/AGENTS.
- `DeclarativeSchemaCompiler` caches compiled schemas per manifest path. When you tweak schema translation rules, add regression tests under `tests/runtime` (covering caching/perf, invalid payloads, and output rejection) so automation agents can rely on deterministic validation.
- `AgentRegistry` eagerly registers `joker-agent.yaml`, `translator-agent.yaml` e `image-agent.yaml`. Quando adicionar novos agentes embutidos, coloque o manifest em `src/agents` e carregue-o seguindo o mesmo padrão.

#### Declarative agent catalog

Built-in manifests live in `src/agents/` and are auto-registered by `AgentRegistry`. Keep the table below in sync whenever inputs/outputs change:

| Agent | Method | Inputs | Outputs | Required props | Notes |
| --- | --- | --- | --- | --- | --- |
| `joker-agent.yaml` | `joker.execute` | — | `response` | `gemini_api_key` | Usa `genkit-joke` com prompt fixo para gerar uma piada curta. |
| `translator-agent.yaml` | `translator.execute` | `texto`, `idioma_origem`, `idioma_destino` | `texto_traduzido`, `metadados` | `gemini_api_key` | Passa pelos helpers `callGeminiFlashTranslation` e devolve metadados (`modelo_utilizado`, `tempo_processamento`, `idiomas_suportados`). |
| `image-agent.yaml` | `image.generate` | `descricao`, `estilo (watercolor|neon|sketch)`, `resolucao` | `image_url`, `image_base64`, `media_type`, `prompt_utilizado`, `metadados` | `gemini_api_key` | Usa `genkit-image` e retorna a imagem em data URL (base64) + metadata. |

> Todos os agentes acima compartilham a mesma credencial `gemini_api_key` transmitida via `props`. Sem ela os helpers Genkit abortam imediatamente.

### Security, compliance, performance

- `SecurityScanner` is synchronous and in-memory. Long-running or I/O heavy enhancements should expose async APIs to avoid blocking the main interpreter.
- Compliance engines (`GDPRCompliance`, `LGPDCompliance`) assume `AuditTrail` is available. Do not instantiate heavy dependencies inside hot paths—pass singletons when possible.
- `PerformanceMonitor` uses retention windows and console logging. Respect the thresholds defined in `performanceTargets`.

### Firebase multi-tenancy

- `MultiTenantFirebaseManager.initializeTenant` is responsible for validating configs, setting security rules, and logging operations. Keep all Firebase Admin calls tenant-scoped (`admin.initializeApp(..., tenantId)`).
- Never store raw secrets in audit logs; always pass objects through `sanitizeForAudit`.

## 4. Documentation & sync duties

1. **When code changes:** update both `README.md` and this `AGENTS.md`. The README is user-facing; this file is for maintainers/agents. Mention new exports, behavior differences, and testing steps in both where relevant.
2. **When specs change:** reflect them in `docs/beddel`. If a spec is not implemented yet, add it to the “Docs/beddel roadmap coverage” section in the README so expectations stay aligned.
3. **When adding declarative language features:** include a worked example under `docs/beddel` (brief or PRD) and document the interpreter changes here (supported syntax, limits, fallback behavior).
4. **Audits:** cross-check the package map in the README with `src/index.ts` before publishing to npm so consumers never import stale symbols.

## 5. Testing & verification

- Use the package-level scripts (`pnpm --filter beddel test`, `pnpm --filter beddel lint`). Keep CI-friendly tests under `packages/beddel/tests`.
- For runtime-level changes, add regression tests in `tests/` (e.g., `test-runtime.js`, `test-runtime-security.js`) or create new files mirroring the naming convention.
- When touching sandbox logic, run the security-focused scripts (`test-runtime-security.js`, `test-session*`) locally; they cover threat detection, isolation, and audit flows.
- For Firebase features, mock `firebase-admin` or guard the tests behind env checks—CI should not need real credentials.

## 6. Contribution checklist

1. Understand the modules you touch (skim the directory table above).
2. Add or update tests.
3. Update README + AGENTS (and `docs/beddel` if specs changed).
4. Run `pnpm --filter beddel build && pnpm --filter beddel lint`.
5. Document remaining gaps vs. the spec under the README “Docs/beddel roadmap coverage” section.

Stay disciplined about the README/AGENTS sync requirement so downstream consumers and automation agents always get an accurate picture of the package.
