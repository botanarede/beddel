# Beddel

**Secure, Declarative, and Extensible Agent Runtime**

[![NPM Version](https://img.shields.io/npm/v/beddel.svg)](https://www.npmjs.com/package/beddel)
[![License](https://img.shields.io/npm/l/beddel.svg)](https://github.com/botanarede/beddel-alpha/blob/main/LICENSE)

Beddel is a security-first toolkit for building and running declarative YAML agents with enterprise-grade isolation, automatic schema validation, and extensible architecture.

## Quick Start

```yaml
# agents/my-agent.yaml
agent:
  id: my-agent
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "My Custom Agent"
  description: "A simple custom agent"
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

```typescript
import { agentRegistry } from "beddel";

// Execute the agent
const result = await agentRegistry.executeAgent(
  "my-agent.execute",
  { message: "Hello world" },
  { gemini_api_key: process.env.GEMINI_API_KEY },
  context
);
```

## Installation

```bash
npm install beddel
```

Requires Node.js 18+.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Beddel Runtime                              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Agent Registry                             │  │
│  │                                                               │  │
│  │  ┌─────────────────┐    ┌────────────────────────────────┐   │  │
│  │  │  Built-in       │    │  Custom Agents                 │   │  │
│  │  │  Agents         │    │  /agents/*.yaml                │   │  │
│  │  │                 │    │                                │   │  │
│  │  │ • joker         │    │  Automatically discovered      │   │  │
│  │  │ • translator    │    │  and registered at startup     │   │  │
│  │  │ • image         │    │                                │   │  │
│  │  └─────────────────┘    └────────────────────────────────┘   │  │
│  │                                                               │  │
│  │         Priority: Custom Agents > Built-in Agents            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                │                                    │
│                                ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              Declarative Agent Interpreter                    │  │
│  │                                                               │  │
│  │   • YAML Parsing (FAILSAFE schema)                           │  │
│  │   • Schema Validation (Zod)                                  │  │
│  │   • Workflow Execution                                       │  │
│  │   • Genkit Integration (Gemini Flash)                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                │                                    │
│                                ▼                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │               Secure Runtime (isolated-vm)                    │  │
│  │                                                               │  │
│  │   • Memory limits         • V8 isolate                       │  │
│  │   • Execution timeouts    • No Node.js access                │  │
│  │   • Audit logging         • Multi-tenant isolation           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Custom Agents

Beddel supports custom agents that you define in your application's `/agents` directory. Custom agents are automatically discovered and registered at startup.

### Directory Structure

```
your-app/
├── agents/                          # Custom agents directory
│   ├── my-agent.yaml                # Simple agent
│   ├── calculator/
│   │   └── calculator.yaml          # Agent in subdirectory
│   └── translator-custom/
│       └── translator-custom.yaml   # Override built-in
│
└── packages/beddel/src/agents/      # Built-in agents (package)
    ├── joker-agent.yaml
    ├── translator-agent.yaml
    └── image-agent.yaml
```

### Agent Loading Flow

```
┌─────────────────────────────────────────────────────────────┐
│                  Agent Loading Sequence                      │
│                                                              │
│  1. AgentRegistry constructor()                              │
│     │                                                        │
│     ├──▶ 2. registerBuiltinAgents()                         │
│     │       ├── joker.execute                                │
│     │       ├── translator.execute                           │
│     │       └── image.generate                               │
│     │                                                        │
│     └──▶ 3. loadCustomAgents()                              │
│             │                                                │
│             └── Recursively scans /agents/**/*.yaml         │
│                 └── Registers each agent                     │
│                     └── Custom agents override built-ins     │
│                                                              │
│  Priority: Custom Agents > Built-in Agents                   │
└─────────────────────────────────────────────────────────────┘
```

### Creating a Custom Agent

1. **Create the YAML file** in `/agents`:

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
    required: ["name"]

  output:
    type: "object"
    properties:
      greeting:
        type: "string"
    required: ["greeting"]

logic:
  workflow:
    - name: "generate-greeting"
      type: "genkit-joke"
      action:
        type: "joke"
        prompt: "Create a warm, friendly greeting for {{name}}"
        result: "greetingResult"

output:
  schema:
    greeting: "$greetingResult.texto"
```

2. **The agent is automatically registered** when your application starts.

3. **Execute via GraphQL or directly**:

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

Create a custom agent with the same route to override a built-in:

```yaml
# agents/joker-custom.yaml
agent:
  id: joker
  protocol: beddel-declarative-protocol/v2.0

metadata:
  route: "/agents/joker"  # Same route overrides built-in
  # ... your custom implementation
```

---

## Built-in Agents

| Agent | Method | Description | Required Props |
|-------|--------|-------------|----------------|
| **Joker** | `joker.execute` | Generates short, original jokes | `gemini_api_key` |
| **Translator** | `translator.execute` | Translates text between languages | `gemini_api_key` |
| **Image Generator** | `image.generate` | Creates images (watercolor, neon, sketch) | `gemini_api_key` |

### Joker Agent

```typescript
const result = await agentRegistry.executeAgent(
  "joker.execute",
  {},
  { gemini_api_key: "..." },
  context
);
// Returns: { response: "Why did the..." }
```

### Translator Agent

```typescript
const result = await agentRegistry.executeAgent(
  "translator.execute",
  {
    texto: "Hello, world!",
    idioma_origem: "en",
    idioma_destino: "pt"
  },
  { gemini_api_key: "..." },
  context
);
// Returns: { texto_traduzido: "Olá, mundo!", metadados: {...} }
```

### Image Generator Agent

```typescript
const result = await agentRegistry.executeAgent(
  "image.generate",
  {
    descricao: "A sunset over mountains",
    estilo: "watercolor",
    resolucao: "1024x1024"
  },
  { gemini_api_key: "..." },
  context
);
// Returns: { image_url, image_base64, media_type, ... }
```

---

## Core Components

### Package Map

| Capability | Module | Description |
|------------|--------|-------------|
| **YAML Parsing** | `SecureYamlParser` | FAILSAFE schema, depth/size limits, UTF-8 validation |
| **Sandboxed Execution** | `IsolatedRuntimeManager` | `isolated-vm` with security profiles |
| **Agent Interpretation** | `DeclarativeAgentInterpreter` | Executes YAML agents with Genkit |
| **Agent Registry** | `AgentRegistry` | Manages built-in and custom agents |
| **Security** | `SecurityScanner`, `ThreatDetectionEngine` | Static scanning, scoring |
| **Compliance** | `GDPRCompliance`, `LGPDCompliance` | Audit, anonymization |
| **Performance** | `PerformanceMonitor`, `AutoScaler` | Metrics, scaling |
| **Multi-tenancy** | `MultiTenantFirebaseManager` | Firebase tenant isolation |

### Secure YAML Parsing

```typescript
import { SecureYamlParser } from "beddel";

const parser = new SecureYamlParser({
  maxDepth: 200,
  filename: "agent-manifest",
});

const manifest = parser.parseSecure(yamlContent);
```

### Sandboxed Execution

```typescript
import { IsolatedRuntimeManager } from "beddel";

const runtime = new IsolatedRuntimeManager();

const result = await runtime.execute({
  code: `({ value: 42 })`,
  securityProfile: "ultra-secure",
  timeout: 2000,
});
```

### Agent Registry API

```typescript
import { agentRegistry } from "beddel";

// Get all registered agents
const agents = agentRegistry.getAllAgents();

// Get a specific agent
const agent = agentRegistry.getAgent("joker.execute");

// Execute an agent
const result = await agentRegistry.executeAgent(
  "joker.execute",
  input,
  props,
  context
);

// Load custom agents from a specific path
agentRegistry.loadCustomAgents("/path/to/custom/agents");
```

---

## Schema Validation

All agents must declare `schema.input` and `schema.output` blocks. The runtime compiles these into Zod schemas and validates:

- **Before execution**: Input must match `schema.input`
- **After execution**: Output must match `schema.output`

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

Supported types: `string`, `number`, `boolean`, `object`, `array`

---

## Security

### Multi-Layer Security Model

1. **Parser Layer**: FAILSAFE schema, size limits, sanitization
2. **Runtime Layer**: V8 isolate, memory limits, timeouts
3. **Application Layer**: Authentication, rate limiting, tenant isolation

### Security Profiles

```typescript
const result = await runtime.execute({
  code: userCode,
  securityProfile: "tenant-isolated", // ultra-secure | tenant-isolated
  timeout: 5000,
  memoryLimit: 128,
});
```

---

## Project Structure

```
src/
├── agents/                  # Agent registry and built-in agents
│   ├── agentRegistry.ts     # Agent management
│   ├── joker-agent.yaml     # Built-in: Joker
│   ├── translator-agent.yaml
│   └── image-agent.yaml
├── parser/                  # Secure YAML parsing
├── runtime/                 # Execution environments
│   ├── isolatedRuntime.ts
│   ├── declarativeAgentRuntime.ts
│   └── schemaCompiler.ts
├── security/                # Scanning and threat detection
├── compliance/              # GDPR/LGPD utilities
├── performance/             # Monitoring and autoscaling
├── firebase/                # Multi-tenant management
└── index.ts                 # Public exports
```

---

## Development

```bash
# Build
pnpm --filter beddel build

# Test
pnpm --filter beddel test

# Lint
pnpm --filter beddel lint
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
