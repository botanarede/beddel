---
id: translator-agent-mapping
version: v2
created: 2025-11-04
updated: 2025-12-18
type: architecture
category: agent-design
tags: [translator, genkit, beddel, public-agent]
status: active
---

# Translator Agent Architecture

## Overview

The Translator Agent is one of three built-in agents in Beddel, using Genkit with Gemini Flash for text translation. This document details its architecture and implementation.

---

## Agent Definition

**Location**: `packages/beddel/src/agents/translator/translator.yaml`

```yaml
agent:
  id: translator
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "Translator Agent"
  description: "Translates text between languages using Gemini Flash via Genkit"
  category: "translation"
  route: "/agents/translator"

schema:
  input:
    type: "object"
    properties:
      text:
        type: "string"
        minLength: 1
        maxLength: 10000
      source_language:
        type: "string"
        pattern: "^[a-z]{2}$"
      target_language:
        type: "string"
        pattern: "^[a-z]{2}$"
    required: ["text", "source_language", "target_language"]

  output:
    type: "object"
    properties:
      texto_traduzido:
        type: "string"
      metadados:
        type: "object"
    required: ["texto_traduzido", "metadados"]

logic:
  workflow:
    - name: "translate"
      type: "genkit-translation"
      action:
        type: "translate"
        result: "translationResult"
```

---

## Execution Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Translator Agent Flow                             │
│                                                                      │
│   ┌──────────────┐                                                  │
│   │   Request    │  texto: "Hello"                                  │
│   │              │  idioma_origem: "en"                             │
│   │              │  idioma_destino: "pt"                            │
│   └──────┬───────┘                                                  │
│          │                                                          │
│          ▼                                                          │
│   ┌──────────────┐                                                  │
│   │    Input     │  Validate against schema.input                   │
│   │  Validation  │  (Zod schema)                                    │
│   └──────┬───────┘                                                  │
│          │                                                          │
│          ▼                                                          │
│   ┌──────────────┐                                                  │
│   │   Genkit     │  callGeminiFlashTranslation()                   │
│   │ Translation  │  → Gemini Flash API                              │
│   └──────┬───────┘                                                  │
│          │                                                          │
│          ▼                                                          │
│   ┌──────────────┐                                                  │
│   │   Output     │  Validate against schema.output                  │
│   │  Validation  │                                                  │
│   └──────┬───────┘                                                  │
│          │                                                          │
│          ▼                                                          │
│   ┌──────────────┐                                                  │
│   │   Response   │  texto_traduzido: "Olá"                         │
│   │              │  metadados: { ... }                              │
│   └──────────────┘                                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Genkit Integration

The Translator Agent uses the `callGeminiFlashTranslation` helper from the declarative runtime:

```typescript
// packages/beddel/src/runtime/declarativeAgentRuntime.ts

async function callGeminiFlashTranslation(
  texto: string,
  idiomaOrigem: string,
  idiomaDestino: string,
  apiKey: string
): Promise<TranslationResult> {
  const genkit = configureGemini(apiKey);
  
  const result = await genkit.generateText({
    model: "google/gemini-flash-latest",
    prompt: `Translate the following text from ${idiomaOrigem} to ${idiomaDestino}: ${texto}`,
    config: { temperature: 0.3 }
  });
  
  return {
    texto_traduzido: result.text,
    metadados: {
      modelo_utilizado: "gemini-flash",
      tempo_processamento: result.timing,
      confianca: 0.95,
      idiomas_suportados: ["en", "pt", "es", "fr", "de", ...],
      idiomas_solicitados: { origem: idiomaOrigem, destino: idiomaDestino }
    }
  };
}
```

---

## Usage

### Via GraphQL

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
    executionTime
  }
}
```

### Via TypeScript

```typescript
import { agentRegistry } from "beddel";

const result = await agentRegistry.executeAgent(
  "translator.execute",
  {
    texto: "Hello, how are you?",
    idioma_origem: "en",
    idioma_destino: "pt"
  },
  { gemini_api_key: process.env.GEMINI_API_KEY },
  context
);

console.log(result.texto_traduzido); // "Olá, como você está?"
```

---

## Custom Translator

To override the built-in translator, create a custom agent with the same route:

```yaml
# agents/custom-translator.yaml
agent:
  id: translator
  version: 2.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "Custom Translator"
  description: "My custom translation implementation"
  route: "/agents/translator"  # Same route = override

# ... your custom implementation
```

The custom agent will be automatically discovered and registered with priority over the built-in.

---

## Security

- **Input Validation**: Text length limits (1-10000 chars)
- **Language Validation**: ISO 639-1 pattern (`^[a-z]{2}$`)
- **Schema Enforcement**: Zod validation on input and output
- **API Key Required**: `gemini_api_key` prop mandatory

---

## Performance

| Metric | Target |
|--------|--------|
| Response Time | < 500ms (simple text) |
| P95 Latency | < 2s (up to 5K chars) |
| Max Input | 10,000 characters |

---

## Related Files

- `packages/beddel/src/agents/translator/translator.yaml` - Agent definition
- `packages/beddel/src/agents/translator/translator.handler.ts` - Server-only handler
- `packages/beddel/src/agents/translator/translator.schema.ts` - Zod validation
- `packages/beddel/src/agents/translator/translator.types.ts` - TypeScript types
- `packages/beddel/src/agents/registry/agentRegistry.ts` - Registration
- `packages/beddel/src/runtime/declarativeAgentRuntime.ts` - Execution
- `packages/beddel/src/runtime/workflowExecutor.ts` - Workflow step execution
- `docs/guides/custom-agents.md` - Custom agent documentation
