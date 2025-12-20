# System Architecture: Declarative Agent Runtime

## Overview

This document outlines the architecture for the Beddel declarative agent runtime - a Next.js-based system for parsing and executing YAML-defined agents with enterprise-grade security, extensibility, and multi-tenant isolation.

## Architectural Principles

1. **Security First**: Multiple isolation layers with `isolated-vm` sandboxing
2. **Declarative Design**: Agents defined in YAML, not imperative code
3. **Extensibility**: Custom agents alongside built-in agents
4. **Simplicity**: Battle-tested technologies prioritizing maintainability

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Application Layer                             │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                      Next.js Application                         │  │
│   │                                                                  │  │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │  │
│   │   │   GraphQL    │  │   REST API   │  │   UI Components      │  │  │
│   │   │  /api/graphql│  │   /api/*     │  │                      │  │  │
│   │   └──────┬───────┘  └──────┬───────┘  └──────────────────────┘  │  │
│   │          │                 │                                     │  │
│   │          └────────┬────────┘                                     │  │
│   │                   ▼                                              │  │
│   │   ┌───────────────────────────────────────────────────────────┐ │  │
│   │   │                   Beddel Runtime                          │ │  │
│   │   │                                                           │ │  │
│   │   │  ┌─────────────────────────────────────────────────────┐ │ │  │
│   │   │  │                 Agent Registry                       │ │ │  │
│   │   │  │                                                      │ │ │  │
│   │   │  │  ┌──────────────────┐  ┌──────────────────────────┐ │ │ │  │
│   │   │  │  │  Built-in Agents │  │    Custom Agents         │ │ │ │  │
│   │   │  │  │                  │  │    /agents/*.yaml        │ │ │ │  │
│   │   │  │  │  • joker         │  │                          │ │ │ │  │
│   │   │  │  │  • translator    │  │  Auto-discovered at      │ │ │ │  │
│   │   │  │  │  • image         │  │  application startup     │ │ │ │  │
│   │   │  │  └──────────────────┘  └──────────────────────────┘ │ │ │  │
│   │   │  │                                                      │ │ │  │
│   │   │  │          Priority: Custom > Built-in                 │ │ │  │
│   │   │  └─────────────────────────────────────────────────────┘ │ │  │
│   │   │                          │                                │ │  │
│   │   │                          ▼                                │ │  │
│   │   │  ┌─────────────────────────────────────────────────────┐ │ │  │
│   │   │  │           Declarative Interpreter                   │ │ │  │
│   │   │  │                                                     │ │ │  │
│   │   │  │  • YAML Parser (FAILSAFE)  • Schema Validation      │ │ │  │
│   │   │  │  • Workflow Executor       • Genkit Integration     │ │ │  │
│   │   │  └─────────────────────────────────────────────────────┘ │ │  │
│   │   │                          │                                │ │  │
│   │   │                          ▼                                │ │  │
│   │   │  ┌─────────────────────────────────────────────────────┐ │ │  │
│   │   │  │            Secure Runtime (isolated-vm)             │ │ │  │
│   │   │  │                                                     │ │ │  │
│   │   │  │  • V8 Isolate   • Memory Limits   • Timeouts        │ │ │  │
│   │   │  │  • Audit Trail  • Tenant Isolation                  │ │ │  │
│   │   │  └─────────────────────────────────────────────────────┘ │ │  │
│   │   └───────────────────────────────────────────────────────────┘ │  │
│   │                                                                  │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                        Infrastructure                            │  │
│   │                                                                  │  │
│   │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐ │  │
│   │  │ Firebase Auth  │  │ Cloud Firestore│  │ Firebase Hosting   │ │  │
│   │  └────────────────┘  └────────────────┘  └────────────────────┘ │  │
│   └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Agent System Architecture

### Agent Registry

The `AgentRegistry` is the central component for managing declarative agents. It handles both built-in agents (shipped with the package) and custom agents (defined in the application).

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AgentRegistry                                 │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Initialization Flow                         │  │
│  │                                                                │  │
│  │   constructor()                                                │  │
│  │       │                                                        │  │
│  │       ├──▶ registerBuiltinAgents()                            │  │
│  │       │       ├── packages/beddel/src/agents/joker/joker.yaml │  │
│  │       │       ├── packages/beddel/src/agents/translator/...   │  │
│  │       │       ├── packages/beddel/src/agents/image/...        │  │
│  │       │       ├── packages/beddel/src/agents/mcp-tool/...     │  │
│  │       │       ├── packages/beddel/src/agents/chromadb/...     │  │
│  │       │       ├── packages/beddel/src/agents/gitmcp/...       │  │
│  │       │       ├── packages/beddel/src/agents/rag/...          │  │
│  │       │       └── packages/beddel/src/agents/chat/...         │  │
│  │       │                                                        │  │
│  │       └──▶ loadCustomAgents()                                 │  │
│  │               │                                                │  │
│  │               └── Scans: {cwd}/agents/**/*.yaml               │  │
│  │                   └── Registers with allowOverwrite=true      │  │
│  │                                                                │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      Public Methods                            │  │
│  │                                                                │  │
│  │   registerAgent(agent, allowOverwrite?)   Register an agent   │  │
│  │   executeAgent(name, input, props, ctx)   Execute agent       │  │
│  │   getAgent(name)                          Get agent by name   │  │
│  │   getAllAgents()                          List all agents     │  │
│  │   loadCustomAgents(path?)                 Load from directory │  │
│  │                                                                │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
Application Root/
│
├── agents/                              # Custom Agents (Application Level)
│   ├── my-agent.yaml                    # Auto-discovered
│   ├── calculator/
│   │   └── calculator.yaml              # Nested discovery supported
│   └── custom-translator/
│       └── translator.yaml              # Can override built-in
│
└── packages/beddel/
    └── src/
        ├── agents/                      # Built-in Agents (Sharded Structure)
        │   ├── registry/
        │   │   ├── agentRegistry.ts     # Registry implementation
        │   │   └── index.ts
        │   ├── joker/
        │   │   ├── joker.yaml           # Agent definition
        │   │   ├── joker.handler.ts     # Server-only handler
        │   │   ├── joker.schema.ts      # Zod validation
        │   │   ├── joker.types.ts       # TypeScript types
        │   │   └── index.ts             # Public exports
        │   ├── translator/
        │   ├── image/
        │   ├── mcp-tool/
        │   ├── gemini-vectorize/
        │   ├── chromadb/
        │   ├── gitmcp/
        │   ├── rag/
        │   ├── chat/
        │   └── index.ts
        │
        ├── runtime/
        │   ├── declarativeAgentRuntime.ts
        │   ├── workflowExecutor.ts      # Workflow step execution
        │   ├── schemaCompiler.ts
        │   └── index.ts
        │
        ├── shared/                      # Client-safe types
        │   ├── types/
        │   └── utils/
        │
        └── client/                      # Client-safe exports
            ├── index.ts
            └── types.ts
```

### Agent Execution Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Agent Execution Pipeline                        │
│                                                                      │
│   ┌──────────────┐                                                  │
│   │   Request    │  methodName: "greeting.execute"                  │
│   │   GraphQL    │  params: { name: "Alice" }                       │
│   │              │  props: { gemini_api_key: "..." }                │
│   └──────┬───────┘                                                  │
│          │                                                          │
│          ▼                                                          │
│   ┌──────────────┐                                                  │
│   │ AgentRegistry│  agentRegistry.getAgent("greeting.execute")      │
│   │    Lookup    │                                                  │
│   └──────┬───────┘                                                  │
│          │                                                          │
│          ▼                                                          │
│   ┌──────────────┐                                                  │
│   │    Schema    │  Validate input against schema.input             │
│   │  Validation  │  Compile YAML schema → Zod schema                │
│   └──────┬───────┘                                                  │
│          │                                                          │
│          ▼                                                          │
│   ┌──────────────┐                                                  │
│   │   Workflow   │  Execute workflow steps sequentially             │
│   │  Execution   │  • genkit-joke → Gemini Flash                    │
│   │              │  • genkit-translation → Gemini Flash              │
│   │              │  • genkit-image → Gemini Flash                    │
│   │              │  • output-generator → Format response             │
│   └──────┬───────┘                                                  │
│          │                                                          │
│          ▼                                                          │
│   ┌──────────────┐                                                  │
│   │   Output     │  Validate output against schema.output           │
│   │  Validation  │                                                  │
│   └──────┬───────┘                                                  │
│          │                                                          │
│          ▼                                                          │
│   ┌──────────────┐                                                  │
│   │   Response   │  { success: true, data: { ... } }               │
│   └──────────────┘                                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Technologies

### Frontend Framework
- **Next.js** (Latest) - Full-stack React framework with App Router
- **React** (Latest) - Component-based UI library
- **TypeScript** - Type-safe JavaScript
- **Tailwind CSS** - Utility-first CSS framework

### Backend & Infrastructure
- **Firebase Hosting** - Global CDN with automatic deployment
- **Firebase Auth** - Authentication via Firebase Admin SDK
- **Cloud Firestore** - NoSQL database (server-side access only)
- **Next.js API Routes** - Backend logic (`/api/*`)

### Key Dependencies

| Package | Version | Security Score | Purpose |
|---------|---------|----------------|---------|
| `js-yaml` | 4.1.0+ | 9.1/10 | Secure YAML parsing with FAILSAFE schema |
| `isolated-vm` | 6.0.2 | 9.3/10 | Enterprise-grade V8 isolate sandboxing |
| `zod` | Latest | N/A | Runtime schema validation |

---

## Component Architecture

### 1. YAML Parser Engine

```typescript
class SecureYamlParser {
  constructor(options: {
    maxDepth?: number;
    maxSize?: number;
    filename?: string;
  });
  
  parseSecure<T>(yamlContent: string): T;
}
```

**Security Features**:
- FAILSAFE schema only (no custom types)
- Depth and size limits
- UTF-8 validation
- Prototype pollution prevention

### 2. Declarative Agent Interpreter

```typescript
class DeclarativeAgentInterpreter {
  async interpret(options: {
    yamlContent: string;
    input: Record<string, any>;
    props: Record<string, string>;
    context: ExecutionContext;
  }): Promise<any>;
}
```

**Supported Workflow Types**:
- `output-generator` - Format output response
- `genkit-joke` - Generate text via Gemini Flash
- `genkit-translation` - Translate text via Gemini Flash
- `genkit-image` - Generate images via Gemini Flash

### 3. Agent Registry

```typescript
class AgentRegistry {
  registerAgent(agent: AgentRegistration, allowOverwrite?: boolean): void;
  executeAgent(name: string, input: any, props: any, ctx: ExecutionContext): Promise<any>;
  getAgent(name: string): AgentRegistration | undefined;
  getAllAgents(): AgentRegistration[];
  loadCustomAgents(customAgentsPath?: string): void;
}

interface AgentRegistration {
  id: string;
  name: string;
  description: string;
  protocol: string;
  route: string;
  requiredProps: string[];
  yamlContent: string;
}
```

### 4. Secure Runtime

```typescript
class IsolatedRuntimeManager {
  async execute(options: {
    code: string;
    securityProfile: 'ultra-secure' | 'tenant-isolated';
    timeout?: number;
    memoryLimit?: number;
  }): Promise<ExecutionResult>;
}
```

**Security Features**:
- Complete V8 isolate with separate memory heap
- Configurable memory limits (default: 128MB)
- Execution timeouts (default: 5s)
- No Node.js API access
- Automatic garbage collection

---

## Security Architecture

### Multi-Layer Security Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Security Layers                               │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Layer 1: Application Security                                │  │
│  │  • Firebase Authentication                                    │  │
│  │  • Rate limiting                                              │  │
│  │  • API key validation                                         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Layer 2: Parser Security                                     │  │
│  │  • FAILSAFE schema only                                       │  │
│  │  • Depth/size limits                                          │  │
│  │  • UTF-8 validation                                           │  │
│  │  • No prototype pollution                                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Layer 3: Schema Validation                                   │  │
│  │  • Zod schema compilation                                     │  │
│  │  • Input validation before execution                          │  │
│  │  • Output validation before response                          │  │
│  │  • Payload size limits (1MB)                                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Layer 4: Runtime Security                                    │  │
│  │  • V8 isolate sandbox                                         │  │
│  │  • Memory limits                                              │  │
│  │  • Execution timeouts                                         │  │
│  │  • No filesystem/network access                               │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Layer 5: Tenant Isolation                                    │  │
│  │  • Per-tenant Firebase apps                                   │  │
│  │  • Server-side data access only                               │  │
│  │  • Audit logging                                              │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Security Configuration

```typescript
interface SecurityConfig {
  tenantIsolation: {
    authentication: 'firebase-admin-sdk-server-side';
    dataAccess: 'server-side-only';
    tenantSeparation: 'strict-user-id-filtering';
  };

  yamlParser: {
    strictMode: true;
    maxFileSize: '1MB';
    maxDepth: 200;
    schemaValidation: true;
  };
  
  runtimeEnvironment: {
    memoryLimit: '128MB';
    executionTimeout: 5000;
    maxConcurrentExecutions: 3;
  };
}
```

---

## Performance Considerations

### YAML Parser Performance
- **Benchmark**: ~1.5M operations/second
- **Memory**: Linear scaling with document size
- **Large Files**: Stream processing for 10MB+ files

### Runtime Performance
- **Isolate Creation**: ~100ms initial overhead
- **Script Execution**: Sub-millisecond for small scripts
- **Memory Overhead**: ~50MB per running isolate
- **Pool Management**: Reusable isolate pool

### Optimization Strategies
- LRU caching for parsed YAML documents
- Isolate pool for rapid context creation
- Schema caching per agent manifest

---

## Built-in Agents Reference

| Agent | Method | Inputs | Outputs |
|-------|--------|--------|---------|
| Joker | `joker.execute` | — | `response` |
| Translator | `translator.execute` | `texto`, `idioma_origem`, `idioma_destino` | `texto_traduzido`, `metadados` |
| Image | `image.generate` | `descricao`, `estilo`, `resolucao` | `image_url`, `image_base64`, `media_type`, `metadados` |

All built-in agents require `gemini_api_key` in props.

---

## References

1. **js-yaml**: [Security Score: 9.1/10](https://www.endorlabs.com/learn/48-most-popular-open-source-tools-for-npm-applications-scored#js-yaml)
2. **isolated-vm**: [Security Review: 9.3/10](https://github.com/laverdet/isolated-vm/security)
3. **Beddel Protocol**: `beddel-declarative-protocol/v2.0`

---

*Last Updated: December 2025*
