# Guia de Criação de Workflow Step Types Nativos

Este documento descreve como criar novos workflow step types nativos para o Beddel Runtime. Todos os novos workflows devem ser implementados nativamente, seguindo o padrão estabelecido pelos agentes builtin existentes.

## Arquitetura

O Beddel utiliza uma arquitetura declarativa onde:

1. **Agentes YAML** definem a interface e o fluxo de execução
2. **Workflow Step Types** são implementados nativamente no `DeclarativeAgentInterpreter`
3. **Agent Registry** gerencia o registro e execução dos agentes

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
│                Native Workflow Step Types                    │
│  genkit-joke, genkit-translation, mcp-tool, chromadb, etc.  │
└─────────────────────────────────────────────────────────────┘
```

## Workflow Step Types Disponíveis

### Tipos Básicos

| Tipo | Descrição | Arquivo |
|------|-----------|---------|
| `output-generator` | Gera output final do agente | Builtin |
| `genkit-joke` | Gera piadas usando Gemini | Builtin |
| `genkit-translation` | Traduz textos entre idiomas | Builtin |
| `genkit-image` | Gera imagens usando Gemini | Builtin |

### Tipos de Integração

| Tipo | Descrição | Dependências |
|------|-----------|--------------|
| `mcp-tool` | Conecta a servidores MCP via SSE | `@modelcontextprotocol/sdk`, `eventsource` |
| `gemini-vectorize` | Gera embeddings de texto | `ai`, `@ai-sdk/google` |
| `chromadb` | Armazenamento e busca vetorial | `chromadb` |
| `gitmcp` | Busca documentação via GitMCP | Usa `mcp-tool` internamente |
| `rag` | Geração de respostas com contexto | `ai`, `@ai-sdk/google` |
| `builtin-agent` | Invoca outro agente builtin | Nenhuma |

## Criando um Novo Workflow Step Type

### Passo 1: Definir o Tipo no Switch Case

Adicione o novo tipo no método `executeWorkflowStep` em `declarativeAgentRuntime.ts`:

```typescript
private async executeWorkflowStep(
  step: any,
  variables: Map<string, any>,
  options: YamlAgentInterpreterOptions
): Promise<any> {
  switch (step.type) {
    // ... tipos existentes ...
    case "meu-novo-tipo":
      return this.executeMeuNovoTipo(step, variables, options);
    default:
      throw new Error(`Unsupported workflow step type: ${step.type}`);
  }
}
```

### Passo 2: Implementar o Método de Execução

Crie o método que implementa a lógica do workflow step:

```typescript
/**
 * Execute meu novo tipo de workflow step
 */
private async executeMeuNovoTipo(
  step: any,
  variables: Map<string, any>,
  options: YamlAgentInterpreterOptions
): Promise<any> {
  // 1. Extrair parâmetros do step.action
  const param1 = this.resolveInputValue(step.action?.param1, options.input, variables);
  const param2 = this.resolveInputValue(step.action?.param2, options.input, variables);
  const resultVar = step.action?.result || "meuResultado";

  // 2. Validar parâmetros obrigatórios
  if (!param1) {
    throw new Error("Missing required input: param1");
  }

  // 3. Executar lógica
  options.context.log(`[MeuNovoTipo] Executando com param1=${param1}...`);

  try {
    // Sua lógica aqui
    const resultado = await minhaLogica(param1, param2);

    // 4. Salvar resultado na variável
    const result = { success: true, data: resultado };
    variables.set(resultVar, result);
    return result;

  } catch (error: any) {
    options.context.log(`[MeuNovoTipo] Error: ${error.message}`);
    const result = { success: false, error: error.message };
    variables.set(resultVar, result);
    return result;
  }
}
```

### Passo 3: Criar o Agente YAML

Crie o arquivo YAML em `packages/beddel/src/agents/`:

```yaml
# meu-novo-agent.yaml
agent:
  id: meu-novo
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "Meu Novo Agent"
  description: "Descrição do que o agente faz"
  category: "categoria"
  route: "/agents/meu-novo"

schema:
  input:
    type: "object"
    properties:
      param1:
        type: "string"
        description: "Descrição do parâmetro 1"
      param2:
        type: "string"
        description: "Descrição do parâmetro 2"
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
    - name: "executar-acao"
      type: "meu-novo-tipo"
      action:
        param1: "$input.param1"
        param2: "$input.param2"
        result: "meuResultado"

    - name: "deliver-response"
      type: "output-generator"
      action:
        type: "generate"
        output:
          success: "$meuResultado.success"
          data: "$meuResultado.data"
          error: "$meuResultado.error"

output:
  schema:
    success: "$meuResultado.success"
    data: "$meuResultado.data"
    error: "$meuResultado.error"
```

### Passo 4: Registrar o Agente

Adicione o método de registro em `agentRegistry.ts`:

```typescript
/**
 * Register Meu Novo Agent
 */
private registerMeuNovoAgent(): void {
  try {
    const yamlPath = this.resolveAgentPath("meu-novo-agent.yaml");
    const yamlContent = readFileSync(yamlPath, "utf-8");
    const agent = this.parseAgentYaml(yamlContent);

    this.registerAgent({
      id: agent.agent.id,
      name: "meu-novo.execute",
      description: agent.metadata.description,
      protocol: agent.agent.protocol,
      route: agent.metadata.route || "/agents/meu-novo",
      requiredProps: [], // ou ["gemini_api_key"] se necessário
      yamlContent,
    });
  } catch (error) {
    console.error("Failed to register Meu Novo Agent:", error);
    throw error;
  }
}
```

E chame-o no `registerBuiltinAgents()`:

```typescript
private registerBuiltinAgents(): void {
  try {
    // ... outros agentes ...
    this.registerMeuNovoAgent();
  } catch (error) {
    console.error("Failed to register built-in agents:", error);
  }
}
```

## Helpers Disponíveis

### resolveInputValue

Resolve valores de input, variáveis ou referências:

```typescript
const valor = this.resolveInputValue(step.action?.campo, options.input, variables);
```

Suporta:
- Valores diretos: `"texto"`, `123`, `true`
- Referências a input: `"$input.campo"`
- Referências a variáveis: `"$minhaVariavel.propriedade"`

### ensureGeminiApiKey

Valida e retorna a API key do Gemini:

```typescript
const apiKey = this.ensureGeminiApiKey(options.props);
```

### splitIntoChunks

Divide texto em chunks preservando parágrafos:

```typescript
const chunks = this.splitIntoChunks(texto, 800); // 800 chars por chunk
```

### context.log

Registra logs de execução:

```typescript
options.context.log(`[MeuAgente] Mensagem de log`);
```

## Padrões de Implementação

### Lazy Loading de Dependências

Para dependências opcionais, use lazy loading:

```typescript
let meuClient: any = null;

private async executeMeuTipo(...) {
  if (!meuClient) {
    const { MeuClient } = await import("minha-dependencia");
    meuClient = new MeuClient();
  }
  // usar meuClient
}
```

### Tratamento de Erros

Sempre retorne um objeto com `success` e `error`:

```typescript
try {
  const resultado = await operacao();
  return { success: true, data: resultado };
} catch (error: any) {
  options.context.log(`[MeuTipo] Error: ${error.message}`);
  return { success: false, error: error.message };
}
```

### Composição de Agentes

Use `builtin-agent` para compor funcionalidades:

```yaml
logic:
  workflow:
    - name: "vectorizar"
      type: "builtin-agent"
      action:
        agent: "gemini-vectorize.execute"
        input:
          action: "embedSingle"
          text: "$input.texto"
        result: "vectorResult"
```

## Variáveis de Ambiente

| Variável | Descrição | Obrigatória |
|----------|-----------|-------------|
| `GEMINI_API_KEY` | API key do Google Gemini | Para agentes AI |
| `CHROMADB_URL` | URL do ChromaDB local | Não (default: localhost:8000) |
| `CHROMADB_API_KEY` | API key do Chroma Cloud | Não |
| `CHROMADB_TENANT` | Tenant do Chroma Cloud | Não |
| `CHROMADB_DATABASE` | Database do Chroma Cloud | Não |

## Checklist de Implementação

- [ ] Definir tipo no switch case de `executeWorkflowStep`
- [ ] Implementar método de execução com tratamento de erros
- [ ] Criar arquivo YAML do agente com schema completo
- [ ] Adicionar método de registro no `AgentRegistry`
- [ ] Chamar método de registro em `registerBuiltinAgents`
- [ ] Adicionar dependências ao `package.json` se necessário
- [ ] Document required environment variables
- [ ] Test agent execution

## Reference Examples

Consult the following files as reference:

- `packages/beddel/src/runtime/declarativeAgentRuntime.ts` - Step type implementation
- `packages/beddel/src/runtime/workflowExecutor.ts` - Workflow step execution
- `packages/beddel/src/agents/registry/agentRegistry.ts` - Agent registry
- `packages/beddel/src/agents/*/` - Sharded agent modules (handler, schema, types, yaml)
