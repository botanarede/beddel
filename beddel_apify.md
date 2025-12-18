# Beddel + Apify: Agentes Declarativos na Plataforma

## Visão Geral

Integração do **Beddel** (protocolo declarativo de agentes YAML) com **Apify** (plataforma de automação web e scraping). Esta combinação permite criar actors Apify que interpretam agentes declarativos em YAML, expandindo o ecossistema Apify com agentes multi-linguagem e portáveis.

## Proposta de Valor

### Para o Ecossistema Apify
- **Agentes Declarativos**: Defina comportamentos de IA em YAML sem código imperativo
- **Segurança por Design**: Runtime isolado sem `eval()` ou execução dinâmica de código
- **Portabilidade**: Agentes YAML podem ser interpretados em qualquer linguagem (futuro: Python, Go, Java)
- **Extensibilidade**: Protocolo aberto para expansão pela comunidade Apify

### Diferencial Competitivo
- **Primeiro actor com protocolo declarativo de agentes**
- **Segurança enterprise-grade** (isolated-vm, validação Zod)
- **Integração nativa com Gemini** (texto, tradução, imagens)
- **Auditoria e compliance** (GDPR/LGPD ready)

## Arquitetura da Solução

```
Apify Actor (Node.js)
├── src/
│   ├── main.ts              # Entry point do actor
│   ├── agents/              # Agentes declarativos YAML
│   │   ├── hello-world.yaml
│   │   ├── web-scraper.yaml
│   │   └── data-enricher.yaml
│   └── config.ts
├── package.json
└── .actor/
    └── actor.json           # Configuração do actor
```

## Passo a Passo: Criando o Actor

### 1. Criar Projeto Apify

```bash
# Instalar Apify CLI
npm install -g apify-cli

# Criar novo actor
apify create beddel-declarative-actor

# Escolher template: "Empty project"
cd beddel-declarative-actor
```

### 2. Instalar Beddel

```bash
npm install beddel
npm install @apify/actor
```

### 3. Configurar package.json

```json
{
  "name": "beddel-declarative-actor",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "start": "node dist/main.js",
    "build": "tsc",
    "dev": "tsx src/main.ts"
  },
  "dependencies": {
    "beddel": "^0.1.0",
    "@apify/actor": "^3.0.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "tsx": "^4.0.0"
  }
}
```

### 4. Criar Agente Hello World

**src/agents/hello-world.yaml**

```yaml
agent:
  id: hello-world
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "Hello World Agent"
  description: "Retorna saudação personalizada via Gemini"
  category: "demo"

schema:
  input:
    type: "object"
    properties:
      nome:
        type: "string"
        description: "Nome do usuário"
    required: []

  output:
    type: "object"
    properties:
      mensagem:
        type: "string"
    required: ["mensagem"]

logic:
  workflow:
    - name: "gerar-saudacao"
      type: "genkit-joke"
      action:
        type: "joke"
        prompt: "Crie uma saudação criativa e amigável para uma pessoa. Se o nome for fornecido no contexto, use-o. Caso contrário, use 'amigo'. Seja breve e positivo."
        result: "saudacaoResult"

    - name: "entregar-resposta"
      type: "output-generator"
      action:
        type: "generate"
        output:
          mensagem: "$saudacaoResult.texto"

output:
  schema:
    mensagem: "$saudacaoResult.texto"
```

### 5. Implementar Main do Actor

**src/main.ts**

```typescript
import { Actor } from '@apify/actor';
import { DeclarativeAgentInterpreter } from 'beddel/dist/runtime/declarativeAgentRuntime.js';
import { ExecutionContext } from 'beddel/dist/types/executionContext.js';
import { readFileSync } from 'fs';
import { join } from 'path';

await Actor.init();

try {
  // Obter input do actor
  const input = await Actor.getInput() ?? {};
  const { agentName = 'hello-world', agentInput = {}, geminiApiKey } = input;

  // Validar API key
  if (!geminiApiKey) {
    throw new Error('GEMINI_API_KEY é obrigatória no input do actor');
  }

  // Carregar agente YAML
  const agentPath = join(process.cwd(), 'src', 'agents', `${agentName}.yaml`);
  const yamlContent = readFileSync(agentPath, 'utf-8');

  // Criar contexto de execução
  const context = new ExecutionContext();

  // Interpretar agente
  const interpreter = new DeclarativeAgentInterpreter();
  const result = await interpreter.interpret({
    yamlContent,
    input: agentInput,
    props: { gemini_api_key: geminiApiKey },
    context
  });

  // Salvar resultado no dataset
  await Actor.pushData({
    agentName,
    input: agentInput,
    output: result,
    executionTime: context.getExecutionTime(),
    logs: context.getLogs()
  });

  console.log('✅ Agente executado com sucesso:', result);

} catch (error) {
  console.error('❌ Erro na execução:', error);
  throw error;
}

await Actor.exit();
```

### 6. Configurar Actor

**.actor/actor.json**

```json
{
  "actorSpecification": 1,
  "name": "beddel-declarative-actor",
  "title": "Beddel Declarative Agent Runner",
  "description": "Execute agentes de IA declarativos definidos em YAML usando o protocolo Beddel",
  "version": "1.0.0",
  "dockerfile": "./Dockerfile",
  "input": "./input_schema.json",
  "storages": {
    "dataset": {
      "actorSpecification": 1,
      "title": "Agent Execution Results",
      "views": {
        "overview": {
          "title": "Overview",
          "transformation": {
            "fields": [
              "agentName",
              "output",
              "executionTime"
            ]
          }
        }
      }
    }
  }
}
```

**.actor/input_schema.json**

```json
{
  "title": "Beddel Agent Input",
  "type": "object",
  "schemaVersion": 1,
  "properties": {
    "agentName": {
      "title": "Agent Name",
      "type": "string",
      "description": "Nome do arquivo YAML do agente (sem extensão)",
      "default": "hello-world",
      "editor": "textfield"
    },
    "agentInput": {
      "title": "Agent Input",
      "type": "object",
      "description": "Dados de entrada para o agente",
      "editor": "json",
      "default": {}
    },
    "geminiApiKey": {
      "title": "Gemini API Key",
      "type": "string",
      "description": "Chave de API do Google Gemini",
      "editor": "textfield",
      "isSecret": true
    }
  },
  "required": ["geminiApiKey"]
}
```

### 7. Build e Deploy

```bash
# Build local
npm run build

# Testar localmente
apify run

# Deploy para Apify
apify login
apify push
```

## Estratégia de Expansão

### Fase 1: Demonstração (MVP)
- Actor básico com hello-world
- Documentação clara
- Exemplo de uso no README

### Fase 2: Casos de Uso Apify
Criar agentes YAML para cenários típicos:

**web-scraper-enricher.yaml** - Enriquece dados de scraping com IA
```yaml
# Recebe dados de scraping e adiciona análise de sentimento,
# categorização automática, tradução, etc.
```

**content-generator.yaml** - Gera conteúdo baseado em templates
```yaml
# Cria descrições de produtos, posts de blog, etc.
```

**data-validator.yaml** - Valida e limpa dados extraídos
```yaml
# Aplica regras de negócio e validações complexas
```

### Fase 3: Integração com Apify SDK
- **Input Mapping**: Conectar datasets Apify com inputs de agentes
- **Output Chaining**: Encadear múltiplos agentes
- **Storage Integration**: Salvar resultados em Key-Value Store

### Fase 4: Marketplace
- Publicar no Apify Store
- Criar agentes pré-configurados para venda
- Oferecer consultoria de implementação

## Compatibilidade Genkit

### Status Atual
O Beddel usa **AI SDK (Vercel)** com `@ai-sdk/google`, não Genkit diretamente.

### Opções de Integração

**Opção 1: Manter AI SDK (Recomendado)**
- ✅ Já funciona out-of-the-box
- ✅ Suporte nativo a Gemini
- ✅ Streaming e imagens
- ❌ Não usa Genkit

**Opção 2: Adicionar Genkit**
- Criar novo step type: `genkit-flow`
- Requer refatoração do runtime
- Benefício: Acesso a plugins Genkit

**Recomendação**: Manter AI SDK e documentar como "Genkit-compatible" (ambos usam Gemini).

## Diferencial de Segurança

### Por que Apify deveria se importar?

1. **Isolated VM**: Código do agente roda em sandbox isolado
2. **Sem eval()**: Zero execução dinâmica de código
3. **Validação Zod**: Schemas tipados e validados
4. **Auditoria**: Logs completos de execução
5. **Compliance**: GDPR/LGPD ready

### Pitch para Apify Staff

> "Beddel traz agentes declarativos seguros para Apify. Enquanto outros actors executam código arbitrário, Beddel interpreta YAML em runtime isolado. É o primeiro protocolo de agentes multi-linguagem no ecossistema Apify - hoje em TypeScript, amanhã em Python, Go, Java. Perfeito para empresas que precisam de IA com governança."

## Próximos Passos

1. ✅ Criar actor básico
2. ⬜ Testar com 3 agentes diferentes
3. ⬜ Documentar casos de uso Apify
4. ⬜ Submeter para Apify Store
5. ⬜ Escrever blog post técnico
6. ⬜ Apresentar em Apify Community Call

## Recursos

- [Apify SDK Docs](https://docs.apify.com/sdk/js)
- [Beddel GitHub](https://github.com/botanarede/beddel-alpha)
- [AI SDK Docs](https://sdk.vercel.ai/docs)
- [Gemini API](https://ai.google.dev/gemini-api/docs)
