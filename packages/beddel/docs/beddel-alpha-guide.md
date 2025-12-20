# Beddel Alpha Guide

## Overview

Beddel Alpha is a complete demonstration of the **real Beddel runtime** executing declarative YAML agents. This guide covers how to use the runtime, execute agents, and create custom agents.

## Key Features

- **Real Agent Execution**: Agents declared in YAML execute through the Beddel runtime
- **GraphQL Integration**: Execute agents via `/api/graphql` endpoint
- **Custom Agents**: Create your own agents in the `/agents` directory
- **Built-in Agents**: Joker, Translator, and Image Generator ready to use
- **Genkit Integration**: Powered by Google Gemini Flash

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Beddel Alpha Application                       │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                     Agent Sources                             │  │
│   │                                                               │  │
│   │   /agents/                    packages/beddel/src/agents/    │  │
│   │   (Custom)                    (Built-in - Sharded)            │  │
│   │                                                               │  │
│   │   • your-agent.yaml          • joker/joker.yaml              │  │
│   │   • calculator.yaml          • translator/translator.yaml    │  │
│   │   • ...                      • image/image.yaml              │  │
│   │                              • mcp-tool/mcp-tool.yaml        │  │
│   │                              • chromadb/chromadb.yaml        │  │
│   │                              • rag/rag.yaml                  │  │
│   │                              • chat/chat.yaml                │  │
│   │                                                               │  │
│   │           Custom agents override built-in agents              │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                    Agent Registry                             │  │
│   │                                                               │  │
│   │   Automatically discovers and registers all agents           │  │
│   │   at application startup                                     │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                GraphQL API (/api/graphql)                     │  │
│   │                                                               │  │
│   │   mutation {                                                  │  │
│   │     executeMethod(                                            │  │
│   │       methodName: "joker.execute"                            │  │
│   │       params: {}                                              │  │
│   │       props: { gemini_api_key: "..." }                       │  │
│   │     )                                                         │  │
│   │   }                                                           │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
beddel-alpha/
├── agents/                          # Custom agents (auto-discovered)
│   └── example-agent.yaml           # Example custom agent
│
├── app/
│   ├── api/
│   │   └── graphql/
│   │       └── route.ts             # GraphQL endpoint
│   ├── layout.tsx
│   └── page.tsx
│
├── packages/beddel/
│   └── src/
│       ├── agents/                  # Sharded agent structure
│       │   ├── registry/
│       │   │   └── agentRegistry.ts # Agent management
│       │   ├── joker/
│       │   │   ├── joker.yaml       # Agent definition
│       │   │   ├── joker.handler.ts # Server-only handler
│       │   │   └── index.ts         # Public exports
│       │   ├── translator/
│       │   ├── image/
│       │   ├── mcp-tool/
│       │   ├── chromadb/
│       │   ├── gitmcp/
│       │   ├── rag/
│       │   └── chat/
│       ├── runtime/
│       │   ├── declarativeAgentRuntime.ts
│       │   └── workflowExecutor.ts
│       ├── shared/                  # Client-safe types
│       └── client/                  # Client-safe exports
│
├── docs/                            # Documentation
│   ├── architecture/
│   └── guides/
│
└── CUSTOM_AGENTS.md                 # Custom agents quick reference
```

---

## Built-in Agents

### 1. Joker Agent

Generates short, original jokes using Gemini Flash.

**Method**: `joker.execute`  
**Route**: `/agents/joker`

```graphql
mutation {
  executeMethod(
    methodName: "joker.execute"
    params: {}
    props: { gemini_api_key: "your-api-key" }
  ) {
    success
    data
    executionTime
  }
}
```

**Response**:
```json
{
  "response": "Why don't scientists trust atoms? Because they make up everything!"
}
```

---

### 2. Translator Agent

Translates text between languages using Gemini Flash.

**Method**: `translator.execute`  
**Route**: `/agents/translator`

```graphql
mutation {
  executeMethod(
    methodName: "translator.execute"
    params: {
      texto: "Hello, how are you?"
      idioma_origem: "en"
      idioma_destino: "pt"
    }
    props: { gemini_api_key: "your-api-key" }
  ) {
    success
    data
  }
}
```

**Response**:
```json
{
  "texto_traduzido": "Olá, como você está?",
  "metadados": {
    "modelo_utilizado": "gemini-flash",
    "tempo_processamento": 245,
    "confianca": 0.95
  }
}
```

---

### 3. Image Generator Agent

Creates images in various styles using Gemini Flash.

**Method**: `image.generate`  
**Route**: `/agents/image`

```graphql
mutation {
  executeMethod(
    methodName: "image.generate"
    params: {
      descricao: "A sunset over mountains"
      estilo: "watercolor"
      resolucao: "1024x1024"
    }
    props: { gemini_api_key: "your-api-key" }
  ) {
    success
    data
  }
}
```

**Supported Styles**: `watercolor`, `neon`, `sketch`

---

## Custom Agents

### Creating a Custom Agent

1. **Create a YAML file** in the `/agents` directory:

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
    required: ["name"]

  output:
    type: "object"
    properties:
      greeting:
        type: "string"
    required: ["greeting"]

logic:
  workflow:
    - name: "generate"
      type: "genkit-joke"
      action:
        type: "joke"
        prompt: "Create a warm greeting for {{name}}"
        result: "result"

output:
  schema:
    greeting: "$result.texto"
```

2. **Restart the application** - the agent is automatically discovered.

3. **Execute the agent**:

```graphql
mutation {
  executeMethod(
    methodName: "greeting.execute"
    params: { name: "Alice" }
    props: { gemini_api_key: "your-api-key" }
  ) {
    success
    data
  }
}
```

### Overriding Built-in Agents

Create a custom agent with the same route to override:

```yaml
# agents/joker-custom.yaml
agent:
  id: joker
  protocol: beddel-declarative-protocol/v2.0

metadata:
  route: "/agents/joker"  # Same route = override
  # ... your custom implementation
```

---

## GraphQL API

Beddel ships a native GraphQL endpoint powered by GraphQL Yoga.

### Endpoint

```
GET /api/graphql
POST /api/graphql
```

### Authentication

`executeMethod` requires an API key (or admin header). GraphiQL and schema
introspection are always enabled.

Include your API key in the Authorization header:

```http
Authorization: Bearer your-api-key
```

Admin mode (no API key):

```http
x-admin-tenant: true
```

### Schema

```graphql
type Query {
  ping: String!
}

type Mutation {
  executeMethod(
    methodName: String!
    params: JSON!
    props: JSON!
  ): ExecutionResult!
}

type ExecutionResult {
  success: Boolean!
  data: JSON
  error: String
  executionTime: Int!
}
```

### Example Request

Using variables (recommended):

```bash
curl -X POST http://localhost:3000/api/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "query": "mutation Execute($methodName: String!, $params: JSON!, $props: JSON!) { executeMethod(methodName: $methodName, params: $params, props: $props) { success data error executionTime } }",
    "variables": {
      "methodName": "joker.execute",
      "params": {},
      "props": { "gemini_api_key": "your-gemini-key" }
    }
  }'
```

Inline arguments:

```bash
curl -X POST http://localhost:3000/api/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "query": "mutation { executeMethod(methodName: \"joker.execute\", params: {}, props: { gemini_api_key: \"your-gemini-key\" }) { success data error executionTime } }"
  }'
```

---

## Development

### Prerequisites

- Node.js 18+
- pnpm
- Gemini API key

### Setup

```bash
# Install dependencies
pnpm install

# Create environment file
cp .env.example .env
# Add your GEMINI_API_KEY to .env

# Start development server
pnpm dev
```

### Running in Local Mode

```bash
# Use local beddel package
pnpm dev:local
```

---

## Agent Protocol Reference

### Required Sections

```yaml
agent:
  id: string          # Unique identifier
  version: string     # Semver version
  protocol: string    # "beddel-declarative-protocol/v2.0"

metadata:
  name: string
  description: string
  route: string       # e.g., "/agents/my-agent"

schema:
  input:              # Input validation schema
    type: "object"
    properties: {}
    required: []
  output:             # Output validation schema
    type: "object"
    properties: {}
    required: []

logic:
  workflow:           # Execution steps
    - name: string
      type: string    # genkit-joke | genkit-translation | genkit-image | output-generator
      action: {}
```

### Workflow Types

| Type | Description | Action Fields |
|------|-------------|---------------|
| `genkit-joke` | Text generation | `prompt`, `result` |
| `genkit-translation` | Translation | `result` |
| `genkit-image` | Image generation | `promptTemplate`, `result` |
| `output-generator` | Format output | `output` |

---

## Troubleshooting

### Agent Not Loading

1. Check the `/agents` directory exists
2. Verify YAML syntax is valid
3. Check console for error messages
4. Ensure `protocol` is `beddel-declarative-protocol/v2.0`

### Execution Errors

1. Verify `gemini_api_key` is provided in props
2. Check input matches `schema.input`
3. Review server logs for detailed errors

### Override Not Working

1. Ensure custom agent has same `route` as built-in
2. Restart the application
3. Check for YAML parsing errors

---

## Summary

| Feature | Status |
|---------|--------|
| Built-in Agents | ✅ Joker, Translator, Image |
| Custom Agents | ✅ Auto-discovered from `/agents` |
| GraphQL API | ✅ `/api/graphql` |
| Schema Validation | ✅ Zod-based |
| Genkit Integration | ✅ Gemini Flash |

---

> 🚀 Beddel Alpha demonstrates real agent execution through the Beddel runtime. Create custom agents by adding YAML files to `/agents` and they are automatically registered and available via GraphQL.
