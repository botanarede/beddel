# Custom Agents Guide

This guide explains how to create and use custom agents in Beddel.

## Overview

Beddel supports **custom agents** that you define in your application's `/agents` directory. Custom agents are automatically discovered and registered at startup, with priority over built-in agents.

---

## Directory Structure

Create an `agents` folder at the root of your Next.js/React application:

```
your-app/
├── agents/                          # Custom agents (auto-discovered)
│   ├── my-agent.yaml                # Simple agent
│   ├── calculator/
│   │   └── calculator.yaml          # Agent in subdirectory
│   └── custom-translator/
│       └── translator.yaml          # Override built-in
│
└── packages/beddel/src/agents/      # Built-in agents (package)
    ├── joker-agent.yaml
    ├── translator-agent.yaml
    └── image-agent.yaml
```

---

## Agent YAML Format

Each agent must be defined in a `.yaml` or `.yml` file following the `beddel-declarative-protocol/v2.0`.

### Minimal Structure

```yaml
agent:
  id: my-agent
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "My Agent"
  description: "What the agent does"
  category: "utility"
  route: "/agents/my-agent"

schema:
  input:
    type: "object"
    properties:
      message:
        type: "string"
    required: ["message"]

  output:
    type: "object"
    properties:
      response:
        type: "string"
    required: ["response"]

logic:
  workflow:
    - name: "process"
      type: "genkit-joke"
      action:
        type: "joke"
        prompt: "{{message}}"
        result: "result"

output:
  schema:
    response: "$result.texto"
```

---

## Field Reference

### `agent`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ | Unique identifier (kebab-case) |
| `version` | string | ✅ | Semver version |
| `protocol` | string | ✅ | Must be `beddel-declarative-protocol/v2.0` |

### `metadata`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Display name |
| `description` | string | ✅ | Agent description |
| `category` | string | ❌ | Category (utility, creative, public) |
| `route` | string | ✅ | HTTP route (e.g., `/agents/my-agent`) |

### `schema`

Defines input/output contracts using JSON Schema-like syntax.

```yaml
schema:
  input:
    type: "object"
    properties:
      name:
        type: "string"
        minLength: 1
        maxLength: 100
      age:
        type: "number"
    required: ["name"]

  output:
    type: "object"
    properties:
      greeting:
        type: "string"
    required: ["greeting"]
```

**Supported types**: `string`, `number`, `boolean`, `object`, `array`

### `logic.workflow`

Defines execution steps.

```yaml
logic:
  workflow:
    - name: "step-name"
      type: "workflow-type"
      action:
        type: "action-type"
        prompt: "Template with {{variables}}"
        result: "variableName"
```

**Workflow types**:

| Type | Description | Action Fields |
|------|-------------|---------------|
| `genkit-joke` | Text generation via Gemini | `prompt`, `result` |
| `genkit-translation` | Translation via Gemini | `result` |
| `genkit-image` | Image generation via Gemini | `promptTemplate`, `result` |
| `output-generator` | Format final output | `output` |

---

## Complete Example

```yaml
# agents/greeting.yaml
agent:
  id: greeting
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "Greeting Agent"
  description: "Generates personalized greetings"
  category: "utility"
  route: "/agents/greeting"

schema:
  input:
    type: "object"
    properties:
      name:
        type: "string"
        minLength: 1
        maxLength: 100
        description: "Person's name"
      language:
        type: "string"
        pattern: "^[a-z]{2}$"
        description: "Language code (en, pt, es)"
    required: ["name"]

  output:
    type: "object"
    properties:
      greeting:
        type: "string"
      metadata:
        type: "object"
        properties:
          model_used:
            type: "string"
          processing_time:
            type: "number"
    required: ["greeting"]

logic:
  workflow:
    - name: "generate-greeting"
      type: "genkit-joke"
      action:
        type: "joke"
        prompt: "Create a warm, friendly greeting for {{name}} in {{language}} language"
        result: "greetingResult"

    - name: "format-output"
      type: "output-generator"
      action:
        type: "generate"
        output:
          greeting: "$greetingResult.texto"
          metadata:
            model_used: "gemini-flash"
            processing_time: 0

output:
  schema:
    greeting: "$greetingResult.texto"
```

---

## Using Custom Agents

### Via GraphQL API

```graphql
mutation {
  executeMethod(
    methodName: "greeting.execute"
    params: { 
      name: "Alice",
      language: "en"
    }
    props: { gemini_api_key: "your-api-key" }
  ) {
    success
    data
    error
    executionTime
  }
}
```

### Via TypeScript

```typescript
import { agentRegistry } from "beddel";

const context = {
  logs: [],
  status: "running",
  output: null,
  log: console.log,
  setOutput: (output) => (context.output = output),
  setError: console.error,
};

const result = await agentRegistry.executeAgent(
  "greeting.execute",
  { name: "Alice", language: "en" },
  { gemini_api_key: process.env.GEMINI_API_KEY },
  context
);

console.log(result.greeting);
```

---

## Overriding Built-in Agents

Create a custom agent with the same route to override a built-in:

```yaml
# agents/joker-custom.yaml
agent:
  id: joker
  version: 2.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "Custom Joker Agent"
  description: "My custom joke generator"
  route: "/agents/joker"  # Same route = override built-in

# ... rest of your implementation
```

> ⚠️ **Warning**: When a custom agent has the same name as a built-in, the custom agent takes priority.

---

## Agent Loading Process

```
┌─────────────────────────────────────────────────────────────┐
│                  Agent Loading Sequence                      │
│                                                              │
│  1. Application starts                                       │
│     │                                                        │
│     ▼                                                        │
│  2. AgentRegistry constructor()                              │
│     │                                                        │
│     ├──▶ registerBuiltinAgents()                            │
│     │       ├── joker.execute                                │
│     │       ├── translator.execute                           │
│     │       └── image.generate                               │
│     │                                                        │
│     └──▶ loadCustomAgents()                                 │
│             │                                                │
│             └── Scans /agents/**/*.yaml recursively         │
│                 └── Registers each agent (overwrites OK)    │
│                                                              │
│  3. All agents ready for execution                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Console Logs

During startup, you'll see:

```
Agent registered: joker.execute (beddel-declarative-protocol/v2.0)
Agent registered: translator.execute (beddel-declarative-protocol/v2.0)
Agent registered: image.generate (beddel-declarative-protocol/v2.0)
🔍 Loading custom agents from: /path/to/your-app/agents
Agent registered: greeting.execute (beddel-declarative-protocol/v2.0)
✅ Successfully loaded 1/1 custom agents
```

---

## Troubleshooting

### Agent Not Loading

1. Verify `/agents` directory exists at project root
2. Check file has `.yaml` or `.yml` extension
3. Check console for error messages
4. Validate YAML syntax

### Validation Errors

Ensure your YAML includes all required sections:
- `agent` (with `id`, `version`, `protocol`)
- `metadata` (with `description`, `route`)
- `logic` (with `workflow`)

### Agent Not Executing

1. Verify method name is correct (e.g., `my-agent.execute`)
2. Check input matches `schema.input`
3. Ensure required props are provided (e.g., `gemini_api_key`)

### Override Not Working

1. Custom agent must have same `route` as built-in
2. Restart application after changes
3. Check for YAML parsing errors in console

---

## Best Practices

1. **Use descriptive IDs**: `user-greeter` not `agent1`
2. **Document your agent**: Fill in `description` completely
3. **Validate inputs**: Define strict `schema.input`
4. **Handle errors**: Check required fields
5. **Version your agents**: Use semver in `version` field
6. **Organize in subdirectories**: Group related agents

---

## API Reference

### AgentRegistry Methods

```typescript
// Load custom agents from directory
agentRegistry.loadCustomAgents(path?: string): void

// Get all registered agents
agentRegistry.getAllAgents(): AgentRegistration[]

// Get specific agent
agentRegistry.getAgent(name: string): AgentRegistration | undefined

// Execute an agent
agentRegistry.executeAgent(
  name: string,
  input: Record<string, any>,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<any>
```

### AgentRegistration Interface

```typescript
interface AgentRegistration {
  id: string;
  name: string;           // e.g., "greeting.execute"
  description: string;
  protocol: string;
  route: string;          // e.g., "/agents/greeting"
  requiredProps: string[];
  yamlContent: string;
}
```

---

## Summary

| Feature | Support |
|---------|---------|
| Auto-discovery | ✅ Scans `/agents/**/*.yaml` |
| Subdirectories | ✅ Recursive scanning |
| Override built-ins | ✅ Same route = override |
| Schema validation | ✅ Zod-based |
| Multiple formats | ✅ `.yaml` and `.yml` |

Create YAML files in `/agents` and they're automatically discovered and registered!
