# Workflow Step Type Creation Guide

This document describes how to create new workflow step types for the Beddel Runtime. Following the Phase 3 refactoring, all agents are now sharded into individual modules with clear client/server separation.

## Architecture Overview

The Beddel Runtime uses a declarative architecture where:

1. **Agent YAML files** define the interface and execution flow
2. **Handler modules** implement the execution logic (server-only)
3. **Schema modules** define Zod validation schemas (shared)
4. **Type modules** define TypeScript interfaces (shared)
5. **Workflow Executor** delegates execution to individual handlers
6. **Agent Registry** manages registration and execution

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent YAML Definition                     │
│  (schema, metadata, workflow steps)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Registry                            │
│  (registerAgent, executeAgent, getAgent)                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Declarative Agent Interpreter                   │
│  (parseYaml, executeWorkflow, executeWorkflowStep)          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Workflow Executor                          │
│  (delegates to individual agent handlers)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Individual Agent Handlers                       │
│  joker.handler, translator.handler, chromadb.handler, etc.  │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

Each agent is sharded into its own folder with the following structure:

```
packages/beddel/src/
├── agents/
│   ├── index.ts                    # Public exports
│   ├── registry/
│   │   ├── index.ts
│   │   └── agentRegistry.ts        # Agent registration (server-only)
│   │
│   ├── joker/                      # Example agent structure
│   │   ├── index.ts                # Public exports (client-safe)
│   │   ├── joker.yaml              # Declarative definition
│   │   ├── joker.handler.ts        # Execution logic (server-only)
│   │   ├── joker.types.ts          # TypeScript interfaces (shared)
│   │   └── joker.schema.ts         # Zod schemas (shared)
│   │
│   └── [other-agents]/             # Same structure for each agent
│
├── runtime/
│   ├── index.ts
│   ├── declarativeAgentRuntime.ts  # YAML interpreter (server-only)
│   └── workflowExecutor.ts         # Step delegation (server-only)
│
├── shared/                          # Shared types and utilities
│   ├── types/
│   │   ├── agent.types.ts          # AgentMetadata, WorkflowStepType
│   │   ├── execution.types.ts      # ExecutionResult, ExecutionStatus
│   │   └── schema.types.ts         # Schema definitions
│   └── utils/
│       └── validation.ts           # Validation utilities
│
├── client/                          # Client-safe exports
│   ├── index.ts                    # Re-exports metadata and schemas
│   └── types.ts                    # Client-specific types
│
└── server/                          # Server-only code
    └── index.ts
```

## Available Workflow Step Types

| Type | Description | Handler |
|------|-------------|---------|
| `joke` | Generates jokes using Gemini | `joker.handler.ts` |
| `translation` | Translates text between languages | `translator.handler.ts` |
| `image` | Generates images using Gemini | `image.handler.ts` |
| `mcp-tool` | Connects to MCP servers via SSE | `mcp-tool.handler.ts` |
| `vectorize` | Generates text embeddings | `gemini-vectorize.handler.ts` |
| `chromadb` | Vector storage and retrieval | `chromadb.handler.ts` |
| `gitmcp` | Fetches GitHub documentation | `gitmcp.handler.ts` |
| `rag` | RAG-based answer generation | `rag.handler.ts` |
| `chat` | Orchestrates chat pipeline | `chat.handler.ts` |
| `output-generator` | Generates final output | Built-in |
| `builtin-agent` | Invokes another agent | Built-in |
| `custom-action` | Executes custom functions | Built-in |

### Legacy Step Types (Backward Compatibility)

| Legacy Type | Maps To |
|-------------|---------|
| `genkit-joke` | `joke` |
| `genkit-translation` | `translation` |
| `genkit-image` | `image` |
| `gemini-vectorize` | `vectorize` |


## Creating a New Workflow Step Type

### Step 1: Create the Agent Folder

```bash
mkdir -p packages/beddel/src/agents/my-agent
```

### Step 2: Create the Types File

Create `packages/beddel/src/agents/my-agent/my-agent.types.ts`:

```typescript
/**
 * My Agent Types - Shared between client and server
 */

export interface MyAgentHandlerParams {
  param1: string;
  param2?: number;
}

export interface MyAgentHandlerResult {
  success: boolean;
  data: string;
  metadata: {
    processing_time: number;
    model_used: string;
  };
}

export interface MyAgentMetadata {
  id: 'my-agent';
  name: string;
  description: string;
  category: string;
  route: '/agents/my-agent';
}
```

### Step 3: Create the Schema File

Create `packages/beddel/src/agents/my-agent/my-agent.schema.ts`:

```typescript
/**
 * My Agent Schema - Zod validation schemas
 * Safe for both client and server
 */

import { z } from 'zod';

export const MyAgentInputSchema = z.object({
  param1: z.string().min(1, 'param1 is required'),
  param2: z.number().optional(),
});

export const MyAgentOutputSchema = z.object({
  success: z.boolean(),
  data: z.string(),
  error: z.string().optional(),
});

export type MyAgentInput = z.infer<typeof MyAgentInputSchema>;
export type MyAgentOutput = z.infer<typeof MyAgentOutputSchema>;
```

### Step 4: Create the Handler File

Create `packages/beddel/src/agents/my-agent/my-agent.handler.ts`:

```typescript
import 'server-only'; // CRITICAL: Prevents client-side import

/**
 * My Agent Handler - Server-only execution logic
 */

import type { ExecutionContext } from '../../types/executionContext';
import type { MyAgentHandlerParams, MyAgentHandlerResult } from './my-agent.types';

/**
 * Execute my agent logic
 */
export async function executeMyAgentHandler(
  params: MyAgentHandlerParams,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<MyAgentHandlerResult> {
  // 1. Validate required props
  const apiKey = props?.gemini_api_key?.trim();
  if (!apiKey) {
    throw new Error('Missing required prop: gemini_api_key');
  }

  // 2. Extract and validate parameters
  const { param1, param2 = 10 } = params;
  if (!param1) {
    throw new Error('Missing required parameter: param1');
  }

  // 3. Log execution start
  const startTime = Date.now();
  context.log(`[MyAgent] Starting execution with param1=${param1}`);

  try {
    // 4. Execute your logic here
    const result = await yourLogicFunction(param1, param2, apiKey);

    // 5. Return structured result
    return {
      success: true,
      data: result,
      metadata: {
        processing_time: Date.now() - startTime,
        model_used: 'your-model',
      },
    };
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    context.log(`[MyAgent] Error: ${message}`);
    throw new Error(`MyAgent execution failed: ${message}`);
  }
}
```

### Step 5: Create the Index File

Create `packages/beddel/src/agents/my-agent/index.ts`:

```typescript
/**
 * My Agent - Public exports (client-safe)
 */

// Schema exports (client-safe)
export { MyAgentInputSchema, MyAgentOutputSchema } from './my-agent.schema';
export type { MyAgentInput, MyAgentOutput } from './my-agent.schema';

// Type exports (client-safe)
export type { MyAgentHandlerParams, MyAgentHandlerResult, MyAgentMetadata } from './my-agent.types';

// Metadata (client-safe)
export const myAgentMetadata = {
  id: 'my-agent',
  name: 'My Agent',
  description: 'Description of what my agent does',
  category: 'utility',
  route: '/agents/my-agent',
} as const;
```

### Step 6: Create the YAML Definition

Create `packages/beddel/src/agents/my-agent/my-agent.yaml`:

```yaml
agent:
  id: my-agent
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "My Agent"
  description: "Description of what my agent does"
  category: "utility"
  route: "/agents/my-agent"

schema:
  input:
    type: "object"
    properties:
      param1:
        type: "string"
        description: "First parameter"
      param2:
        type: "number"
        description: "Second parameter (optional)"
    required: ["param1"]

  output:
    type: "object"
    properties:
      success:
        type: "boolean"
      data:
        type: "string"
      error:
        type: "string"
    required: ["success"]

logic:
  workflow:
    - name: "execute-my-agent"
      type: "my-agent"
      action:
        param1: "$input.param1"
        param2: "$input.param2"
        result: "myResult"

    - name: "deliver-response"
      type: "output-generator"
      action:
        type: "generate"
        output:
          success: "$myResult.success"
          data: "$myResult.data"
          error: "$myResult.error"

output:
  schema:
    success: "$myResult.success"
    data: "$myResult.data"
```


### Step 7: Register the Handler in Workflow Executor

Update `packages/beddel/src/runtime/workflowExecutor.ts`:

```typescript
// Add import at the top
import { executeMyAgentHandler } from '../agents/my-agent/my-agent.handler';

// Add to handlerMap
const handlerMap: Record<string, HandlerFunction> = {
  // ... existing handlers ...
  'my-agent': executeMyAgentHandler,
};
```

### Step 8: Add Step Type to Declarative Runtime

Update `packages/beddel/src/runtime/declarativeAgentRuntime.ts`:

```typescript
// Add case in executeWorkflowStep switch
case 'my-agent':
  return this.executeMyAgent(step, variables, options);

// Add the execution method
private async executeMyAgent(
  step: any,
  variables: Map<string, any>,
  options: YamlAgentInterpreterOptions
): Promise<any> {
  const param1 = this.resolveInputValue(step.action?.param1, options.input, variables);
  const param2 = this.resolveInputValue(step.action?.param2, options.input, variables);
  const resultVar = step.action?.result || 'myResult';

  const result = await executeMyAgentHandler(
    { param1, param2 },
    options.props,
    options.context
  );

  variables.set(resultVar, result);
  return result;
}
```

### Step 9: Register the Agent in Registry

Update `packages/beddel/src/agents/registry/agentRegistry.ts`:

```typescript
// Add registration method
private registerMyAgent(): void {
  try {
    const yamlPath = this.resolveAgentPath("my-agent/my-agent.yaml");
    const yamlContent = readFileSync(yamlPath, "utf-8");
    const agent = this.parseAgentYaml(yamlContent);

    this.registerAgent({
      id: agent.agent.id,
      name: "my-agent.execute",
      description: agent.metadata.description,
      protocol: agent.agent.protocol,
      route: agent.metadata.route || "/agents/my-agent",
      requiredProps: ["gemini_api_key"], // or [] if no props needed
      yamlContent,
    });
  } catch (error) {
    console.error("Failed to register My Agent:", error);
    throw error;
  }
}

// Call in registerBuiltinAgents()
private registerBuiltinAgents(): void {
  try {
    // ... existing registrations ...
    this.registerMyAgent();
  } catch (error) {
    console.error("Failed to register built-in agents:", error);
  }
}
```

### Step 10: Update Exports

Update `packages/beddel/src/agents/index.ts`:

```typescript
// Add metadata export
export { myAgentMetadata } from './my-agent';

// Add schema exports
export { MyAgentInputSchema, MyAgentOutputSchema } from './my-agent';

// Add type exports
export type { MyAgentInput, MyAgentOutput, MyAgentHandlerParams, MyAgentHandlerResult } from './my-agent';

// Add to allAgentMetadata array
export const allAgentMetadata = [
  // ... existing entries ...
  { id: 'my-agent', name: 'My Agent', description: 'Description', category: 'utility', route: '/agents/my-agent' },
] as const;
```

Update `packages/beddel/src/client/index.ts` with the same exports (excluding handlers).

## Helper Methods

### resolveInputValue

Resolves values from input, variables, or direct references:

```typescript
const value = this.resolveInputValue(step.action?.field, options.input, variables);
```

Supports:
- Direct values: `"text"`, `123`, `true`
- Input references: `"$input.field"`
- Variable references: `"$myVariable.property"`

### context.log

Logs execution messages:

```typescript
options.context.log(`[MyAgent] Processing...`);
```

### context.setError

Sets error state:

```typescript
options.context.setError('Error message');
```

## Security Checklist

- [ ] Handler file starts with `import 'server-only'`
- [ ] API keys are never exposed in types or schemas
- [ ] No `process.env` access in client-safe files
- [ ] Schemas use Zod for validation
- [ ] Metadata contains no sensitive information
- [ ] Index file only exports client-safe items

## Environment Variables

| Variable | Description | Required For |
|----------|-------------|--------------|
| `GEMINI_API_KEY` | Google Gemini API key | AI agents |
| `CHROMADB_URL` | ChromaDB server URL | ChromaDB agent |
| `CHROMADB_API_KEY` | Chroma Cloud API key | Cloud deployment |
| `CHROMADB_TENANT` | Chroma Cloud tenant | Cloud deployment |
| `CHROMADB_DATABASE` | Chroma Cloud database | Cloud deployment |

## Reference Files

| File | Purpose |
|------|---------|
| `packages/beddel/src/runtime/workflowExecutor.ts` | Handler delegation |
| `packages/beddel/src/runtime/declarativeAgentRuntime.ts` | YAML interpretation |
| `packages/beddel/src/agents/registry/agentRegistry.ts` | Agent registration |
| `packages/beddel/src/agents/joker/` | Reference implementation |
| `packages/beddel/src/shared/types/agent.types.ts` | Shared type definitions |

## Custom Agents (User-Defined)

Users can create custom agents in the `/agents` directory at the project root. The registry automatically loads:

1. YAML files (`.yaml`, `.yml`) - Agent definitions
2. TypeScript files (`.ts`) - Custom function implementations

Custom agents can override built-in agents by using the same route.

### Custom Function Example

Create `/agents/my-custom/handler.ts`:

```typescript
export async function myCustomFunction(args: {
  input: Record<string, any>;
  variables: Record<string, any>;
  action: any;
  context: ExecutionContext;
}) {
  // Your custom logic
  return { success: true, data: 'result' };
}
```

Reference in YAML:

```yaml
logic:
  workflow:
    - name: "custom-step"
      type: "custom-action"
      action:
        function: "my-custom/myCustomFunction"
        result: "customResult"
```


---

## Legacy Artifacts Mapping

The following artifacts from the pre-refactoring codebase are no longer used and can be safely removed:

### Deprecated YAML Files (in node_modules only)

These files exist only in cached `node_modules` from older package versions:

| File | Status | Notes |
|------|--------|-------|
| `node_modules/beddel/src/agents/joker-agent.yaml` | Deprecated | Replaced by `agents/joker/joker.yaml` |
| `node_modules/beddel/src/agents/translator-agent.yaml` | Deprecated | Replaced by `agents/translator/translator.yaml` |
| `node_modules/beddel/src/agents/image-agent.yaml` | Deprecated | Replaced by `agents/image/image.yaml` |

These will be removed automatically when `node_modules` is cleaned and reinstalled.

### Test Files to Review

| File | Status | Recommendation |
|------|--------|----------------|
| `test-beddel-alpha.js` | Outdated | Update or remove - tests UI elements that may have changed |
| `test-beddel-admin.js` | Outdated | Update or remove - tests UI elements that may have changed |
| `test-custom-agents.ts` | Valid | Keep - tests custom agent loading functionality |

### Migration Notes

1. **Step type naming**: The refactoring introduced English step type names (`joke`, `translation`, `image`, `vectorize`) while maintaining backward compatibility with legacy names (`genkit-joke`, `genkit-translation`, `genkit-image`, `gemini-vectorize`).

2. **Handler extraction**: All handler logic was extracted from `declarativeAgentRuntime.ts` into individual `*.handler.ts` files. The runtime now delegates to these handlers via `workflowExecutor.ts`.

3. **Client/Server separation**: The `server-only` package is used to prevent accidental client-side imports of handler code. All handlers must include `import 'server-only'` at the top.

4. **Type safety**: Each agent now has dedicated `.types.ts` and `.schema.ts` files for better type safety and validation.
