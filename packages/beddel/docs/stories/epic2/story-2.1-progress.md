# Joker Agent Runtime Integration - Progress Report

## Status: ✅ Completed

**Date**: December 2025  
**Sprint**: Agent Infrastructure

---

## Overview

**Objective**: Integrate declarative YAML agents into the Beddel runtime system for execution via GraphQL.

**Agents Implemented**:
- `joker-agent.yaml` - Joke generation
- `translator-agent.yaml` - Text translation
- `image-agent.yaml` - Image generation

---

## Implementation Summary

### 1. Declarative Agent Runtime

**File**: `packages/beddel/src/runtime/declarativeAgentRuntime.ts`

- Interprets declarative YAML agents without dynamic code execution
- Supports workflow types: `genkit-joke`, `genkit-translation`, `genkit-image`, `output-generator`
- Integrates with Gemini Flash via Genkit helpers
- Validates schemas using Zod

### 2. Agent Registry Service

**File**: `packages/beddel/src/agents/registry/agentRegistry.ts`

**Features**:
- Automatic registration of built-in agents at startup
- **Custom agent discovery** from `/agents` directory
- Safe agent registration with validation
- Priority system: custom agents override built-ins
- Direct agent execution via declarative interpreter

**Key Methods**:
- `registerAgent(agent, allowOverwrite?)` - Register an agent
- `executeAgent(name, input, props, context)` - Execute an agent
- `loadCustomAgents(path?)` - Load custom agents from directory
- `getAllAgents()` - List all registered agents

### 3. GraphQL Integration

**File**: `packages/beddel/src/server/api/graphql.ts`

- Declarative agents checked before traditional endpoints
- Seamless integration with existing authentication
- Proper error handling and logging

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Agent Registration Flow                       │
│                                                                      │
│   AgentRegistry constructor()                                        │
│       │                                                              │
│       ├──▶ registerBuiltinAgents()                                  │
│       │       ├── joker.execute                                      │
│       │       ├── translator.execute                                 │
│       │       └── image.generate                                     │
│       │                                                              │
│       └──▶ loadCustomAgents()                                       │
│               └── Scans /agents/**/*.yaml                           │
│                   └── Registers with allowOverwrite=true            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        Agent Execution Flow                          │
│                                                                      │
│   GraphQL Request                                                    │
│       │                                                              │
│       ▼                                                              │
│   agentRegistry.getAgent(methodName)                                │
│       │                                                              │
│       ▼                                                              │
│   agentRegistry.executeAgent(...)                                   │
│       │                                                              │
│       ▼                                                              │
│   declarativeInterpreter.interpret({                                │
│       yamlContent,                                                  │
│       input,                                                        │
│       props,                                                        │
│       context                                                       │
│   })                                                                │
│       │                                                              │
│       ▼                                                              │
│   Response                                                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Built-in Agents

| Agent | Method | Description | Required Props |
|-------|--------|-------------|----------------|
| Joker | `joker.execute` | Generates jokes via Gemini | `gemini_api_key` |
| Translator | `translator.execute` | Translates text via Gemini | `gemini_api_key` |
| Image | `image.generate` | Creates images via Gemini | `gemini_api_key` |

---

## Custom Agents

Developers can create custom agents in the `/agents` directory:

```
/agents
├── my-agent.yaml
└── subdirectory/
    └── another-agent.yaml
```

Custom agents are automatically discovered and registered at startup. They can override built-in agents by using the same route.

See `docs/guides/custom-agents.md` for complete documentation.

---

## Testing

### Unit Tests
- Schema validation tests
- Workflow execution tests
- Agent registration tests

### Integration Tests
- GraphQL endpoint tests
- End-to-end agent execution
- Custom agent loading tests

---

## Files Changed

- `packages/beddel/src/runtime/declarativeAgentRuntime.ts` - Declarative interpreter
- `packages/beddel/src/runtime/workflowExecutor.ts` - Workflow step execution
- `packages/beddel/src/agents/registry/agentRegistry.ts` - Agent registry with custom loading
- `packages/beddel/src/agents/*/` - Sharded agent modules (handler, schema, types, yaml)
- `packages/beddel/src/server/api/graphql.ts` - GraphQL integration

---

## Completion Notes

✅ Declarative agent runtime implemented  
✅ Agent registry with auto-registration  
✅ Custom agent discovery from `/agents`  
✅ GraphQL integration complete  
✅ All three built-in agents functional  
✅ Schema validation with Zod  
✅ Genkit/Gemini Flash integration  

---

## Next Steps

1. Additional workflow types as needed
2. Hot-reload for custom agents (development mode)
3. Agent marketplace integration
4. Enhanced error reporting
