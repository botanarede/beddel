# Prompt de Refatoração: Sharding de Agentes Beddel com Separação Client/Server

## Contexto

Este prompt utiliza a técnica **Chain-of-Thought (CoT) com Decomposição de Tarefas** para guiar a refatoração dos agentes builtin do Beddel. A técnica foi escolhida porque:

1. O problema envolve múltiplas decisões arquiteturais interdependentes
2. Requer análise de segurança em cada etapa
3. Precisa manter compatibilidade com código existente
4. Envolve reorganização de estrutura de arquivos complexa

---

## Objetivo Principal

Refatorar os agentes builtin do Beddel para:
1. **Shardar** cada agente em sua própria pasta com arquivos YAML e TypeScript separados
2. **Separar** código client-only, server-only e shared
3. **Prevenir** vazamento de dados sensíveis entre client e server
4. **Manter** funcionalidade existente

---

## Análise da Situação Atual

### Estrutura Atual
```
packages/beddel/src/
├── agents/
│   ├── agentRegistry.ts          # Registro centralizado
│   ├── chat-agent.yaml
│   ├── chromadb-agent.yaml
│   ├── gemini-vectorize-agent.yaml
│   ├── gitmcp-agent.yaml
│   ├── image-agent.yaml
│   ├── joker-agent.yaml
│   ├── mcp-tool-agent.yaml
│   ├── rag-agent.yaml
│   └── translator-agent.yaml
├── runtime/
│   └── declarativeAgentRuntime.ts  # Contém TODA a lógica de execução
├── server/                         # Código server-side
└── types/                          # Tipos compartilhados
```

### Problemas Identificados

1. **Monolito de Runtime**: `declarativeAgentRuntime.ts` contém toda a lógica de todos os agentes (~1000 linhas)
2. **Sem Separação Client/Server**: Código que deveria ser server-only pode vazar para o client
3. **Agentes Acoplados**: Lógica de cada agente está embutida no runtime
4. **Tipos Misturados**: Não há distinção clara entre tipos client-safe e server-only

### Artefatos a Mapear

| Artefato | Classificação | Justificativa |
|----------|---------------|---------------|
| API Keys (Gemini, ChromaDB) | **SERVER-ONLY** | Credenciais sensíveis |
| MCP Client/Transport | **SERVER-ONLY** | Conexões de rede privilegiadas |
| ChromaDB Client | **SERVER-ONLY** | Acesso a banco de dados |
| Embeddings/Vectors | **SERVER-ONLY** | Dados de processamento interno |
| Agent YAML Definitions | **SERVER-ONLY** | Configuração de runtime |
| Input/Output Schemas | **SHARED** | Validação em ambos os lados |
| Agent Metadata (name, description) | **SHARED** | Exibição em UI |
| ExecutionContext | **SERVER-ONLY** | Contexto de execução privilegiado |
| Agent Response Types | **SHARED** | Tipagem de respostas |

---

## Estrutura Proposta

```
packages/beddel/src/
├── agents/
│   ├── index.ts                    # Re-exports públicos
│   ├── registry/
│   │   ├── index.ts
│   │   └── agentRegistry.ts        # Registro centralizado (server-only)
│   │
│   ├── joker/
│   │   ├── index.ts                # Re-export público
│   │   ├── joker.yaml              # Definição declarativa
│   │   ├── joker.handler.ts        # Lógica de execução (server-only)
│   │   ├── joker.types.ts          # Tipos compartilhados
│   │   └── joker.schema.ts         # Schemas Zod (shared)
│   │
│   ├── translator/
│   │   ├── index.ts
│   │   ├── translator.yaml
│   │   ├── translator.handler.ts
│   │   ├── translator.types.ts
│   │   └── translator.schema.ts
│   │
│   ├── image/
│   │   ├── index.ts
│   │   ├── image.yaml
│   │   ├── image.handler.ts
│   │   ├── image.types.ts
│   │   └── image.schema.ts
│   │
│   ├── mcp-tool/
│   │   ├── index.ts
│   │   ├── mcp-tool.yaml
│   │   ├── mcp-tool.handler.ts     # Contém lógica MCP (server-only)
│   │   ├── mcp-tool.types.ts
│   │   └── mcp-tool.schema.ts
│   │
│   ├── gemini-vectorize/
│   │   ├── index.ts
│   │   ├── gemini-vectorize.yaml
│   │   ├── gemini-vectorize.handler.ts
│   │   ├── gemini-vectorize.types.ts
│   │   └── gemini-vectorize.schema.ts
│   │
│   ├── chromadb/
│   │   ├── index.ts
│   │   ├── chromadb.yaml
│   │   ├── chromadb.handler.ts     # Contém cliente ChromaDB (server-only)
│   │   ├── chromadb.types.ts
│   │   └── chromadb.schema.ts
│   │
│   ├── gitmcp/
│   │   ├── index.ts
│   │   ├── gitmcp.yaml
│   │   ├── gitmcp.handler.ts
│   │   ├── gitmcp.types.ts
│   │   └── gitmcp.schema.ts
│   │
│   ├── rag/
│   │   ├── index.ts
│   │   ├── rag.yaml
│   │   ├── rag.handler.ts
│   │   ├── rag.types.ts
│   │   └── rag.schema.ts
│   │
│   └── chat/
│       ├── index.ts
│       ├── chat.yaml
│       ├── chat.handler.ts         # Orquestrador (server-only)
│       ├── chat.types.ts
│       └── chat.schema.ts
│
├── runtime/
│   ├── index.ts
│   ├── declarativeAgentRuntime.ts  # Runtime simplificado
│   └── workflowExecutor.ts         # Executor de workflows (server-only)
│
├── shared/                          # Tipos e utilitários compartilhados
│   ├── index.ts
│   ├── types/
│   │   ├── agent.types.ts          # AgentMetadata, AgentResponse
│   │   ├── execution.types.ts      # ExecutionStep, ExecutionResult
│   │   └── schema.types.ts         # SchemaDefinition
│   └── utils/
│       └── validation.ts           # Utilitários de validação
│
├── server/                          # Código exclusivamente server-side
│   ├── index.ts
│   └── ...
│
└── client/                          # Código client-safe (novo)
    ├── index.ts
    └── types.ts                     # Re-exports de tipos seguros
```

---

## Tarefas de Implementação

### Fase 1: Preparação e Estrutura Base

#### Tarefa 1.1: Criar estrutura de diretórios
```bash
# Criar pastas para cada agente
mkdir -p packages/beddel/src/agents/{joker,translator,image,mcp-tool,gemini-vectorize,chromadb,gitmcp,rag,chat,registry}
mkdir -p packages/beddel/src/shared/{types,utils}
mkdir -p packages/beddel/src/client
```

#### Tarefa 1.2: Instalar pacote `server-only`
```bash
cd packages/beddel && pnpm add server-only
```

#### Tarefa 1.3: Criar arquivo de tipos compartilhados
Criar `packages/beddel/src/shared/types/agent.types.ts`:
```typescript
// Tipos seguros para client e server

export interface AgentMetadata {
  id: string;
  name: string;
  description: string;
  category: string;
  route: string;
  tags?: string[];
}

export interface AgentResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp?: string;
}

export interface ExecutionStep {
  agent: string;
  action: string;
  status: 'running' | 'success' | 'error';
  startTime: number;
  endTime?: number;
  duration?: number;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  error?: string;
  description?: string;
  phase?: 'orchestration' | 'vectorization' | 'storage' | 'retrieval' | 'ingestion' | 'generation';
}
```

---

### Fase 2: Extrair Handlers dos Agentes

#### Tarefa 2.1: Criar handler do Joker Agent
Criar `packages/beddel/src/agents/joker/joker.handler.ts`:
```typescript
import 'server-only'; // Garante que não será importado no client

import { generateText } from 'ai';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import type { ExecutionContext } from '../../types/executionContext';

const GEMINI_MODEL = 'models/gemini-2.5-flash';

export interface JokeHandlerParams {
  prompt?: string;
  temperature?: number;
  maxTokens?: number;
}

export interface JokeHandlerResult {
  texto: string;
  metadados: {
    modelo_utilizado: string;
    tempo_processamento: number;
    temperature: number;
    max_tokens: number | null;
    prompt_utilizado: string;
  };
}

export async function executeJokeHandler(
  params: JokeHandlerParams,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<JokeHandlerResult> {
  const apiKey = props?.gemini_api_key?.trim();
  if (!apiKey) {
    throw new Error('Missing required prop: gemini_api_key');
  }

  const prompt = params.prompt?.trim() || 'Conte uma piada curta e original em português.';
  const temperature = params.temperature ?? 0.8;
  const maxTokens = params.maxTokens;

  const google = createGoogleGenerativeAI({ apiKey });
  const model = google(GEMINI_MODEL);
  const startTime = Date.now();

  context.log(`[Joker] Generating joke with temperature=${temperature}`);

  const { text } = await generateText({
    model,
    prompt,
    temperature,
    ...(maxTokens && { maxOutputTokens: maxTokens }),
  });

  const finalText = text?.trim() || '';
  if (!finalText) {
    throw new Error('Gemini returned empty response');
  }

  return {
    texto: finalText,
    metadados: {
      modelo_utilizado: GEMINI_MODEL,
      tempo_processamento: Date.now() - startTime,
      temperature,
      max_tokens: maxTokens ?? null,
      prompt_utilizado: prompt,
    },
  };
}
```

#### Tarefa 2.2: Criar schema do Joker Agent
Criar `packages/beddel/src/agents/joker/joker.schema.ts`:
```typescript
import { z } from 'zod';

export const JokerInputSchema = z.object({}).optional();

export const JokerOutputSchema = z.object({
  response: z.string(),
});

export type JokerInput = z.infer<typeof JokerInputSchema>;
export type JokerOutput = z.infer<typeof JokerOutputSchema>;
```

#### Tarefa 2.3: Criar index do Joker Agent
Criar `packages/beddel/src/agents/joker/index.ts`:
```typescript
// Re-exports públicos (client-safe)
export { JokerInputSchema, JokerOutputSchema } from './joker.schema';
export type { JokerInput, JokerOutput } from './joker.schema';

// Metadata (client-safe)
export const jokerMetadata = {
  id: 'joker',
  name: 'Joker Agent',
  description: 'Conta piadas usando Gemini Flash',
  category: 'utility',
  route: '/agents/joker',
} as const;
```

**Repetir padrão para todos os outros agentes (translator, image, mcp-tool, gemini-vectorize, chromadb, gitmcp, rag, chat)**

---

### Fase 3: Refatorar o Runtime

#### Tarefa 3.1: Criar WorkflowExecutor
Criar `packages/beddel/src/runtime/workflowExecutor.ts`:
```typescript
import 'server-only';

import type { ExecutionContext } from '../types/executionContext';

// Import handlers de cada agente
import { executeJokeHandler } from '../agents/joker/joker.handler';
import { executeTranslationHandler } from '../agents/translator/translator.handler';
import { executeImageHandler } from '../agents/image/image.handler';
import { executeMcpToolHandler } from '../agents/mcp-tool/mcp-tool.handler';
import { executeVectorizeHandler } from '../agents/gemini-vectorize/gemini-vectorize.handler';
import { executeChromaDBHandler } from '../agents/chromadb/chromadb.handler';
import { executeGitMcpHandler } from '../agents/gitmcp/gitmcp.handler';
import { executeRagHandler } from '../agents/rag/rag.handler';

export type WorkflowStepType = 
  | 'genkit-joke'
  | 'genkit-translation'
  | 'genkit-image'
  | 'mcp-tool'
  | 'gemini-vectorize'
  | 'chromadb'
  | 'gitmcp'
  | 'rag'
  | 'output-generator'
  | 'builtin-agent';

const handlerMap: Record<string, Function> = {
  'genkit-joke': executeJokeHandler,
  'genkit-translation': executeTranslationHandler,
  'genkit-image': executeImageHandler,
  'mcp-tool': executeMcpToolHandler,
  'gemini-vectorize': executeVectorizeHandler,
  'chromadb': executeChromaDBHandler,
  'gitmcp': executeGitMcpHandler,
  'rag': executeRagHandler,
};

export async function executeWorkflowStep(
  stepType: WorkflowStepType,
  params: Record<string, unknown>,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<unknown> {
  const handler = handlerMap[stepType];
  if (!handler) {
    throw new Error(`Unknown workflow step type: ${stepType}`);
  }
  return handler(params, props, context);
}
```

#### Tarefa 3.2: Simplificar DeclarativeAgentRuntime
Refatorar `packages/beddel/src/runtime/declarativeAgentRuntime.ts` para usar o `WorkflowExecutor` em vez de ter toda a lógica inline.

---

### Fase 4: Configurar Exports do Package

#### Tarefa 4.1: Atualizar package.json exports
```json
{
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "default": "./dist/index.js"
    },
    "./server": {
      "types": "./dist/server/index.d.ts",
      "default": "./dist/server/index.js"
    },
    "./client": {
      "types": "./dist/client/index.d.ts",
      "default": "./dist/client/index.js"
    },
    "./shared": {
      "types": "./dist/shared/index.d.ts",
      "default": "./dist/shared/index.js"
    },
    "./agents/*": {
      "types": "./dist/agents/*/index.d.ts",
      "default": "./dist/agents/*/index.js"
    }
  }
}
```

#### Tarefa 4.2: Criar client/index.ts
```typescript
// Apenas tipos e metadados seguros para o client
export * from '../shared';

// Re-export metadados dos agentes (sem handlers)
export { jokerMetadata } from '../agents/joker';
export { translatorMetadata } from '../agents/translator';
export { imageMetadata } from '../agents/image';
// ... outros agentes
```

---

### Fase 5: Validação e Testes

#### Tarefa 5.1: Criar teste de isolamento
```typescript
// packages/beddel/tests/security/client-server-isolation.test.ts
import 'server-only';

describe('Client/Server Isolation', () => {
  it('should not expose server-only modules in client exports', async () => {
    // Importar apenas do client
    const clientExports = await import('beddel/client');
    
    // Verificar que não há funções de handler
    expect(clientExports).not.toHaveProperty('executeJokeHandler');
    expect(clientExports).not.toHaveProperty('executeMcpToolHandler');
    
    // Verificar que metadados estão disponíveis
    expect(clientExports).toHaveProperty('jokerMetadata');
  });
});
```

#### Tarefa 5.2: Verificar build
```bash
cd packages/beddel && npm run build
```

---

## Checklist de Segurança

- [ ] Todos os handlers usam `import 'server-only'` no topo
- [ ] API keys nunca são expostas em tipos compartilhados
- [ ] ChromaDB client está isolado em server-only
- [ ] MCP SDK está isolado em server-only
- [ ] Schemas Zod são compartilhados (validação em ambos os lados)
- [ ] Metadados de agentes são client-safe
- [ ] ExecutionContext é server-only
- [ ] Nenhum `process.env` em código client

---

## Ordem de Execução Recomendada

1. **Fase 1**: Criar estrutura de diretórios e tipos base
2. **Fase 2**: Extrair handlers um por um (começar pelo mais simples: joker)
3. **Fase 3**: Refatorar runtime para usar handlers extraídos
4. **Fase 4**: Configurar exports do package
5. **Fase 5**: Validar com testes e build

---

## Referências

- [Next.js Server/Client Components](https://nextjs.org/docs/app/building-your-application/rendering/composition-patterns)
- [Turborepo Internal Packages](https://turborepo.com/docs/crafting-your-repository/creating-an-internal-package)
- [server-only package](https://www.npmjs.com/package/server-only)
- [React Taint API](https://react.dev/reference/react/experimental_taintUniqueValue)

---

## Notas Importantes

1. **Não usar barrel files (index.ts) para re-exportar handlers** - isso pode causar tree-shaking incorreto
2. **Cada handler deve ser importado diretamente** quando necessário no server
3. **Schemas Zod podem ser compartilhados** pois são apenas definições de tipos
4. **Metadados são seguros** pois não contêm lógica executável
5. **Testar isolamento** antes de fazer deploy para produção
