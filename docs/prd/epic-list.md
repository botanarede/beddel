# Epic List

## Epic 1: Foundation & Core

Establish project structure, secure YAML parsing, and the core `WorkflowExecutor` that drives all pipeline execution.

### Story 1.1: Clean Setup

As a developer, I want a properly configured TypeScript package, so that I can build with strict type safety.

**Acceptance Criteria:**
1. Package includes: `ai`, `@ai-sdk/google`, `zod`, `js-yaml`
2. `tsconfig.json` configured with strict mode
3. No GraphQL dependencies in the package

### Story 1.2: Secure Parser

As a security-conscious developer, I want YAML parsing that prevents code execution, so that user-defined configurations are safe.

**Acceptance Criteria:**
1. `loadYaml` function uses `FAILSAFE_SCHEMA` from js-yaml
2. Functions and class instances are rejected by the parser
3. Parser returns typed `ParsedYaml` object

### Story 1.3: Workflow Executor

As a workflow author, I want steps to execute sequentially, so that I can compose complex pipelines.

**Acceptance Criteria:**
1. `WorkflowExecutor` iterates over `yaml.workflow` steps
2. If a handler returns a `Response` instance, execution stops and returns immediately
3. Step results are stored in `context.variables` for use by subsequent steps

---

## Epic 2: Primitive Handlers

Implement the three core primitives that power the pipeline: `llm`, `output-generator`, and `call-agent`.

### Story 2.1: Handler & Tool Registries

As a package author, I want extensible registries for primitives and tools, so that the system supports the Expansion Pack Pattern.

**Acceptance Criteria:**
1. `primitiveRegistry: Record<string, PrimitiveHandler>` exists in `src/primitives/index.ts`
2. `toolRegistry: Record<string, ToolImplementation>` exists in `src/tools/index.ts`
3. MVP includes `calculator` and `getCurrentTime` sample tools

### Story 2.2: LLM Primitive

As a workflow author, I want to call LLMs from YAML steps, so that I can define AI behavior declaratively.

**Acceptance Criteria:**
1. `stream: true` uses `streamText` and returns `result.toUIMessageStreamResponse()`
2. `stream: false` uses `generateText` and returns JSON object
3. `config.tools` maps to Vercel AI SDK `tools` via `mapTools()` function
4. `stopWhen: stepCountIs(5)` is set when tools are present (enabling tool loops)
5. Uses `convertToModelMessages()` for `UIMessage[]` → `ModelMessage[]` conversion (AI SDK v6)

### Story 2.3: Output Primitive

As a workflow author, I want to transform variables into structured output, so that I can format responses without LLM calls.

**Acceptance Criteria:**
1. Variable resolution supports `$input.*` and `$stepResult.*` syntax
2. Template is a pure JSON transform (no LLM invocation)
3. Returns the transformed object for next step consumption

### Story 2.4: Lifecycle Hooks

As a workflow author, I want callbacks to execute after streaming completes, so that I can persist conversations and log usage.

**Acceptance Criteria:**
1. `onFinish` callback executes after stream completes with `{ text, usage, totalUsage, steps }` payload
2. `onError` callback executes when stream errors with `{ error }` payload
3. Callbacks are registered via `callbackRegistry: Record<string, CallbackFn>`
4. YAML references callback by name string (e.g., `onFinish: "persistConversation"`)

---

## Epic 3: API & Integration

Expose the workflow engine via a REST endpoint and provide a sample agent for testing.

### Story 3.1: API Route

As a frontend developer, I want a REST endpoint for chat, so that I can use `useChat` or standard fetch calls.

**Acceptance Criteria:**
1. `POST /api/beddel/chat` accepts `{ agentId, messages }`
2. Loads YAML from `src/agents/{agentId}.yaml`
3. Returns streaming `Response` or JSON based on workflow output

### Story 3.2: Sample Assistant

As a developer onboarding to Beddel, I want a working example agent, so that I can understand the YAML structure.

**Acceptance Criteria:**
1. `src/agents/assistant.yaml` is provided with streaming enabled
2. Includes at least one tool definition (`calculator`)
3. curl command successfully receives streamed response
