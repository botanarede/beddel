# Prompt: Setup da API GraphQL para Beddel Chat

## Contexto

O frontend do chat (`/chat`) está implementado e funcional, mas retorna 404 na rota `/api/graphql`. Precisamos implementar a camada de API que conecta o frontend aos agentes builtin do Beddel.

## Arquitetura de Referência (beddel-chat)

O projeto `beddel-chat` usa uma arquitetura com **agentes externos** (arquivos `.ts` e `.yaml` na pasta `/agents`):

```
beddel-chat/
├── agents/
│   ├── chat-agent.ts          # Orquestrador principal
│   ├── chromadb-agent.ts      # Integração ChromaDB
│   ├── gemini-vectorize-agent.ts
│   ├── gitmcp-agent.ts
│   └── rag-agent.ts
├── app/api/graphql/route.ts   # Rota simplificada que chama qaHandler
└── types/chat.ts
```

## Arquitetura Alvo (alpha-example)

O projeto `alpha-example` usa **agentes builtin** do pacote `beddel`:

```
alpha-example/
├── packages/beddel/src/agents/
│   ├── chat/                  # Agente chat builtin
│   ├── chromadb/
│   ├── gemini-vectorize/
│   ├── gitmcp/
│   └── rag/
├── src/app/api/graphql/route.ts  # A CRIAR
└── src/lib/chat-api.ts           # Já existe (frontend)
```

## Diferenças Chave

| Aspecto | beddel-chat | alpha-example |
|---------|-------------|---------------|
| Agentes | Externos (`/agents/*.ts`) | Builtin (`beddel/src/agents/*`) |
| Handler | `qaHandler` customizado | `executeChatHandler` do pacote |
| GraphQL | Simplificado (sem auth) | Pode usar `handleGraphQLPost` do Beddel |
| Tipos | Locais (`types/chat.ts`) | Exportados do pacote `beddel` |

## Opções de Implementação

### Opção A: Usar `handleGraphQLPost` do Beddel (Recomendado)
- Usa a infraestrutura completa do Beddel
- Requer header `x-admin-tenant: true` ou API key
- Suporta rate limiting, logging, etc.

### Opção B: Rota Simplificada (como beddel-chat)
- Chama diretamente `executeChatHandler`
- Sem autenticação
- Mais simples para desenvolvimento

## Arquivos a Criar

### 1. `src/app/api/graphql/route.ts`

**Responsabilidades:**
- Receber requisições GraphQL POST
- Extrair `methodName`, `params`, `props` das variables
- Chamar o handler apropriado do Beddel
- Retornar resposta no formato GraphQL

**Dependências:**
```typescript
import { executeChatHandler } from "beddel/agents/chat/chat.handler";
// OU
import { handleGraphQLPost } from "beddel/server/api/graphql";
```

### 2. Variáveis de Ambiente Necessárias

```env
# Já existentes no .env
GEMINI_API_KEY=...
CHROMADB_URL=...  # ou QDRANT_URL

# Opcionais (se usar handleGraphQLPost completo)
KV_REST_API_URL=...
KV_REST_API_TOKEN=...
```

### 3. Configuração de Knowledge Sources

O chat agent precisa de `knowledge_sources` (URLs GitMCP). No beddel-chat isso é resolvido via YAML:

```yaml
# agents/chat-agent.yaml
metadata:
  knowledge_sources:
    - "gitmcp-agent"  # Referência a outro agente
```

No alpha-example, pode ser:
- Hardcoded na rota
- Configurado via env
- Lido de um arquivo YAML local

## Checklist de Implementação

- [ ] Criar `src/app/api/graphql/route.ts`
- [ ] Decidir entre Opção A ou B
- [ ] Configurar knowledge_sources
- [ ] Verificar variáveis de ambiente
- [ ] Testar endpoint com curl/Postman
- [ ] Validar integração com frontend

## Exemplo de Request/Response

**Request:**
```json
{
  "query": "mutation ExecuteChat($input: JSON!) { executeMethod(methodName: \"chat.execute\", params: $input, props: {}) { success data error executionTime } }",
  "variables": {
    "input": {
      "messages": [
        { "role": "user", "content": "O que é o Beddel?" }
      ]
    }
  }
}
```

**Response:**
```json
{
  "data": {
    "executeMethod": {
      "success": true,
      "data": {
        "response": "Beddel é...",
        "timestamp": "2025-12-20T...",
        "execution_steps": [...],
        "total_duration": 1234
      },
      "error": null,
      "executionTime": 1234
    }
  }
}
```

## Notas Técnicas

1. **Import Path**: O handler do chat está em `beddel/agents/chat/chat.handler.ts` mas é marcado como `server-only`. A rota API (server component) pode importá-lo.

2. **ExecutionContext**: O handler espera um `ExecutionContext` com métodos `log`, `setOutput`, `setError`.

3. **Props**: O handler recebe `props` com secrets (API keys). Estes devem vir do `process.env`.

4. **Tipos Exportados**: `ConversationMessage`, `ChatHandlerResult`, `ExecutionStep` já são exportados do pacote `beddel` (v0.2.3).
