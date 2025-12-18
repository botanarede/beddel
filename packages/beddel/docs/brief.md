# Beddel - Protocolo de Agentes com Lógica Declarativa Avançada

## 🎯 Objetivo Revolucionário

Criar o Beddel como um **protocolo universal de agentes** onde **toda a lógica JavaScript server-side é armazenada em dados estruturados declarativos** usando um formato híbrido que vai além do JSON tradicional, permitindo expressividade próxima ao código real sem comprometer a segurança.

## 🧠 Problema: Limitações do JSON para Lógica Complexa

### ❌ JSON Puro é Limitado Para:
```json
{
  "type": "transform", // Simplista - não pode ter loops, condições complexas
  "conditions": ["a > b"], // Expressões como strings - difícil validar
  "operations": ["x = y + z"] // Sem tipagem, sem validação de sintaxe
}
```

### ✅ Solução Beddel: Formato Declarativo YAML Expandido
```yaml
# Agente de Análise de Dados
id: data-analyzer-agent
version: 1.0.0
protocol: beddel-declarative-protocol/v2.0

metadata:
  name: "Smart Data Analyzer"
  category: "data-processing"

schema:
  input:
    type: "object"
    properties:
      data: { type: "array", items: { type: "object" } }
      config: { type: "object" }

# Lógica declarativa completa em YAML
logic:
  # Variáveis com tipos
  variables:
    - name: "filteredData"
      type: "array"
      init: "@input.data where .status == 'active'"
    
    - name: "summary"
      type: "object"
      init: "{@compute}" 
  
  # Computação com sintaxe natural
  compute:
    transform: 
      type: "map-filter-reduce"
      sequence:
        - filter: "$$.status != 'deleted'"
          transform: "$$ | {id: .id, value: .value * 2, status: .status}"
        - groupBy: "$$category"
          aggregate: 
            sum: "$$value"
            count: "$$length"
            avg: "$$sum / $$count" 
  
  # Lógica de decisão
  decision:
    rules:
      - condition: "$count > 100"
        action: 
          type: "process"
          method: "batch-process"
          params:
            chunks: "Math.ceil($count / 50)"
      - condition: "$complexity > 0.8"
        action:
          type: "optimize"
          algorithm: "parallel-stream"
    
  # Fluxo de controle declarativo
  workflow:
    type: "state-machine"
    states:
      validate:
        onEnter: "$input.schema.validate(@input.data)"
      process:
        conditions:
          - "$validated && $dataLength > 0"
        actions:
          - "filteredData = logic.compute()"
          - "summary = logic.compute.transform.aggregate(filteredData)"
      complete:
        onExit: "$output = {result: summary, metrics: @computeMetrics(summary)}"

# Integração com behaviors nativos
behaviors:
  - name: "text-analyzer"
    version: "latest"
    inputs: ["@variables.summary.text"]
  - name: "pattern-matcher"
    version: "1.2"
    inputs: ["@variables.filteredData"]
  
# Saída tipada
output:
  schema:
    result: "$summary"
    metrics:
      processingTime: "number" 
      complexityScore: "number"
```

## 🏗️ Arquitetura Declarativa Avançada

### 1. Formato Híbrido: YAML + Expressões Declarativas

#### Formato Completo (YAML-Based Logic)
```yaml
agent:
  id: "universal-processor"
  
logic:
  # Variáveis com sintaxe natural
  variables:
    records: "@input.data.map(item => ({...item, computed: item.a + item.b}))"
    filtered: "@records.filter(r => r.status != 'deleted')"
    grouped: "@records.groupBy(r => r.category)"
  
  # Fluxo de dados funcional
  flow:
    - name: "validate-input"
      condition: "@input && @input.data"
      transform: "@input.data | map(validate-schema) | filter(not-empty)"
    
    - name: "enrich-data" 
      match: "$record.type"
      cases:
        customer: "enrichCustomer($record)"
        product: "enrichProduct($record)"
      default: "$record"
    
    - name: "aggregate-metrics"
      compute: |
        $metrics = {
          total: @records.length,
          avg: avg(@records.map(r => r.value)),
          categories: @records.groupBy(r => r.type).map(g => ({
            type: g.key,
            count: g.length,
            sum: sum(g.value)
          }))
        }
  
  # Decisões complexas
  decisions:
    priority: 
      rule: "case when $risk > 0.8 then 'critical'"
      cases:
        critical: { action: 'alert', routing: 'urgent' }
        high: { action: 'notify', routing: 'priority' }
        default: { action: 'process', routing: 'normal' }
    
  # Integrações externas
  integrations:
    - provider: "external-api"
      when: "$category == 'external'"
      action: "api.call('${endpoint}', ${params})"
      transform: "json => json.results.map(r => ({...r, source: 'external'}))"
```

#### Sintaxe da Linguagem Declarativa

O Beddel usa uma sintaxe expandida que transforma ações em descrições:

1. **Transformações Funcionais**
```yaml
transform:
  type: "map-filter-reduce"
  sequence:
    - map: "$${ item | {id: .id, data: .data * 2, timestamp: now()} }"
    - filter: "$${ .value > threshold && .status != 'disabled' }"
    - reduce: |
        $acc = {sum: 0, count: 0, latest: null}
        $records.forEach(r => {
          $acc.sum += r.value;
          $acc.count += 1;
          $acc.latest = r.timestamp;
        })
        return $acc
```

2. **Condições Avançadas**
```yaml
conditions:
  - type: "temporal"
    expr: "createdAt > lastWeek && expiresAt > now()"

  - type: "business-logic"
    expr: "customer.tier == 'premium' || (order.value > 1000 && payment.status == 'confirmed')"
```

3. **Looping Declarativo**
```yaml
iterations:
  loop-over: "customers"
  condition: "$customer.isActive && $customer.balance > 0"
  actions:
    - "process-payment($customer)"
    - "send-notification($customer, 'payment-due')"
  parallel: true
  max-concurrent: 10
  error-handling: "continue-on-failure"
```

### 2. Tipos de Lógica Suportados

```yaml
logic-types:
  functional-transform:
    map: "$${ items | map(x => transformed(x)) }"
    filter: "$${ array | filter(condition) }"
    reduce: "$${ array | reduce((acc, curr) => updated) }"
  
  state-machine:
    states: [idle, processing, completed, failed]
    transitions:
      - "idle → processing: @validate()"
      - "processing → completed: @process.complete()"
      - "processing → failed: @process.error()"
  
  rule-engine:
    facts: [input, context, history]
    rules:
      - condition: "context.user.plan == 'pro' and input.amount > 100"
        action: upgrade-plan()
      - condition: "history.last-month > 5000 or context.priority == 'high'"
        action: apply-discount()
```

### 3. Protocolo de Behaviors Declarativos

Cada behavior do registry declara sua lógica:

```yaml
behavior:
  id: "declarative-text-analyzer"
  type: "declarative"
  version: "2.0.0"

# Lógica interna do behavior
logic:
  # Estrutura funcional completa
  functional: |
    $input.text
      | split-sentences
      | map-sentiment
      | group-by-emotion
      | aggregate-metrics
  
  # Condições complexas
  conditions: |
    $text-length > 100 && 
    $language == 'portuguese' &&
    $sentiment.polarity != 'neutral'
  
  # Transformações pipeline
  pipeline:
    step-1:
      type: "tokenize"
      lang: "$input.language"
      remove-stopwords: true
      
    step-2:
      type: "analyze-sentiment"
      model: "vader-portuguese"
      confidence: required
      
    step-3:
      type: "extract-entities"
      entities: ["person", "organization", "location"]
      context-window: 3
      
    step-4:
      type: "compute-insights"
      features: ["emotion", "intent", "topic"]
      return: "summary"

# Saída estruturada
output:
  schema:
    sentiment-score: "number [-1.0, 1.0]"
    emotion-dominant: "angry|joy|sadness|surprise|fear|disgust"
    topics: "array of {topic: string, relevance: number}"
    entities: "array of {type: string, text: string, confidence: number}"
    summary: "string < 500 characters"
```

## 🔧 Runtime Seguro: Interpretação Declarativa

### Motor de Execução Declarativo
```typescript
class DeclarativeRuntime {
  private behaviors = new Map<string, DeclarativeBehavior>();
  
  async executeLogicAgent(agent: AgentManifest, input: any, props: any) {
    const context = this.createContext(input, props);
    const logic = agent.logic;
    
    // 1. Variáveis com resolução funcional
    const variables = await this.resolveVariables(logic, context);
    
    // 2. Fluxo de execução declarativo
    for (const step of logic.workflow) {
      await this.executeStep(step, context, variables);
    }
    
    // 3. Validação de saída via schema
    return this.validateOutput(agent.schema, context.output);
  }
  
  // Resolver variáveis com sintaxe natural
  private resolveVariables(logic: DeclarativeLogic, context: Context) {
    const result: Record<string, any> = {};
    
    for (const varDecl of logic.variables) {
      const resolver = this.createResolver(context);
      const value = resolver.evaluate(varDecl.init);
      const typedValue = this.ensureType(varDecl.type, value);
      result[varDecl.name] = typedValue;
    }
    
    return result;
  }
  
  // Interpretador de linguagem natural-funcional
  private createResolver(context: Context) {
    return {
      evaluate: (expression: string): any => {
        // Expressões como "@input.data.filter(...)"
        if (expression.startsWith('@')) {
          return this.executeFunctionalExpression(expression.slice(1), context);
        }
        
        // Computações complexas
        if (expression.includes('$')) {
          return this.executeComputedExpression(expression, context);
        }
        
        // Valores literais com formatação
        return this.parseLiteral(expression);
      }
    };
  }
}
```

### Exemplo de Execução Natural
```yaml
# Código declarativo
filtered: "@input.orders | filter(o => o.status != 'cancelled')"

# Execução runtime (pseudo)
const orders = input.orders;
const filtered = orders.filter(order => order.status !== 'cancelled');
// Resultado: array filtrado tipado e validado
```

## 🛡️ Segurança por Design Múltipla

### 1. Conteúdo Limitado e Verificado
```yaml
security:
  validation:
    - "expressão analisada e vazia de código executável"
    - "tempo de execução limitado a 30 segundos"
    - "uso de memória monitorado"
  sandbox:
    - "nenhuma capacidade de I/O arbitrário"
    - "recursos externos requerem explicitação"
```

### 2. Behaviors Declarativos Limitados
```yaml
behaviors:
  text-analysis:
    capabilities: ["tokenize", "sentiment", "entity-extract"]
    disallow: ["code-generation", "command-execution"]
    
  data-processing:
    operations: ["map", "filter", "reduce", "group"]
    max-recursion: 3
    timeout: 20000
```

### 3. Protocolo de Validação
```yaml
protocol:
  validation:
    schema-check: "toda saída validada contra schema"
    types-check: "todas as variáveis têm tipos especificados"
    logic-isolation: "comportamentos rodam em contêiner isolados"
    resource-limit: "CPU, memória e uso de API limitados"
```

## 🌐 Mercado e Patterns Alternativos

### Comparação com Patterns do Mercado

#### Beddel vs. HashiCorp Configuration Language (HCL)
- **HCL**: Focado em infraestrutura - terraform, configs de IaaC
- **Beddel**: Focado em lógica declarativa de negócios

#### Beddel vs. Ansible YAML Playbooks
- **Ansible**: Orientado a automação e I/Os
- **Beddel**: Orientado a lógica e transformação de dados

#### Beddel vs. JSONPath/XPath
- **XPath**: Seleção e navegação em dados
- **Beddel**: Computação funcional completa

## 📈 Protocolo Aberto Universal

O Beddel define um protocolo expansível para agentes:

```yaml
# Protocolo base - beddel-declarative-protocol/v2.0
protocol:
  version: "2.0.0"
  format: "yaml-declarative"
  
  spec:
    # Componentes mínimos requeridos
    required:
      - schema: { input: object, output: object }
      - logic: { workflow: array }
      - metadata: { id: string, category: string }
    
    # Extensões permitidas  
    extensions:
      behaviors: "array de referências a behaviors"
      runtime: "configurações de execução"
      security: "políticas de segurança"
      monitoring: "métricas e observabilidade"
      
    # Compatibilidade retroativa
    compatibility:
      "1.x": "converte automaticamente para 2.0"
      "2.x": "formato nativo da versão 2"
```

### Exemplo Real de Agente Universal

```yaml
# Agente de Processamento de Pedidos de E-commerce
id: order-processor-agent-universal
namespace: "beddel/commerce/order-processing"

logic:
  # 1. Lógica de validação declarativa
  validate:
    customer:
      - "$customer.active && $customer.balance >= 0"
      - "$customer.region in $allowed-regions"
      - "!$customer.blacklisted"
    items:
      - "$items.all(i => i.available >= i.quantity)"
      - "$items.some(i => i.promotion && i.promotion.active)"
    
  # 2. Computação de preços com regras de negócio
  pricing:
    rules:
      - condition: "$customer.type == 'premium'"
        effect: "$subtotal * 0.9" # 10% desconto premium
        
      - condition: "$order.total > 500 && $order.region == 'local'"
        effect: "max(0, $shipping - 15)" # Frete promocional
        
      - condition: "$items.has-promotion && $items.quantity > 5"
        effect: "$subtotal * 0.95" # Desconto por quantidade + promoção
        
    calculations:
      subtotal: "$items.sum(i => i.price * i.quantity)"
      discount: max(0, $subtotal * $customer.discount-rate)
      tax: "$subtotal * $region.tax-rate"
      shipping: "$shipping-base + ($order.weight * $shipping-rate)"
      
  # 3. Decisões inteligentes
  fulfillment:
    when: "$order.status == 'confirmed'"
    decision:
      fast: "$customer.region same-day-capable and $order.time till-cutoff > 1h"
      standard: "$order.priority normal"
      express: "$order.priority urgent or $customer.plan == enterprise"
      
  # 4. Integração declarativa com behaviors
  behaviors:
    - name: "inventory-checker"
      version: "2.1"
      inputs: ["@logic.validate.items"]
      options: { realtime: true, cache: 300000 }
      
    - name: "customer-credit"
      version: "1.8"
      inputs: ["@customer.id", "@order.total"]
      condition: "$order.payment-method == 'credit-account'"
      
    - name: "notification-sender"
      version: "3.0"
      inputs: ["@order", "@customer"]
      when: "$order.status-changed"
      channels: ["email", "sms", "push-notification"]
      
  output:
    result:
      order-id: "$order.id"
      status: "$order.status" 
      items: "$processed-items"
      pricing: "$pricing-totals"
      routing: "$fulfillment.decision"
      notifications-sent: "notifications.sent"
```

## 🚀 Transformação para JavaScript Seguro

### Runtime Interpretador Declarativo
```typescript
class DeclarativeInterpreter {
  interpretYamlLogic(yamlLogic: string, input: any, props: any): any {
    // Parse YAML
    const parsed = this.parseYamlLogic(yamlLogic);
    
    // Interpretar lógica passo-a-passo
    const context = this.createExecutionContext(input, props);
    const result: Record<string, any> = {};
    
    // Resolver variáveis
    for (const varDecl of parsed.variables) {
      result[varDecl.name] = this.interpret(varDecl.init, context);
    }
    
    // Executar workflow declarativo
    for (const step of parsed.workflow) {
      const stepResult = this.interpretWorkflowStep(step, context);
      context.set(`$${step.name}`, stepResult);
    }
    
    return context.output;
  }
  
  private interpret(expression: string, context: Context): any {
    // Exemplo de interpretação: "@input.orders | filter(o => o.status != 'cancelled')"
    if (expression.includes('@')) {
      return this.processDataPipeline(expression, context);
    }
    
    if (expression.includes('$')) {
      return this.processConditionLogic(expression, context);
    }
    
    // Valores literais / computed
    return this.evaluateExpression(expression, context);
  }
}
```

### Exemplo de Execução Real
```typescript
// YAML declarativo
const agentLogic = `
variables:
  expensive-orders: "@input.orders.filter(o => o.value > 1000)"
  regions: "$expensive-orders.groupBy(o => o.region)"
  metrics: "$regions.map(r => ({region: r.key, count: r.length, volume: sum(r.items, v => v.value)}))"

workflow:
  - name: "analyze-patterns"
    condition: "$expensive-orders.length > 5"
    action: "sendToAnalytics($metrics)"
`;

// Execução segura
const interpreter = new DeclarativeInterpreter();

const input = {
  orders: [
    { id: 1, value: 1200, region: "usa" },
    { id: 2, value: 800, region: "usa" },
    { id: 3, value: 1500, region: "europe" }
  ]
};

const result = interpreter.interpretYamlLogic(agentLogic, input, {});
// Resultado: { regions: [...], metrics: [{region: "usa", count: 1, volume: 1200}, ...] }
```

## 📊 Vantagens do Beddel Declarativo

### Segurança Máxima
- ❌ **Zero código JavaScript executado dinamicamente**
- ✅ **100% dados estruturados validados**
- 🛡️ **Comportamentos previamente auditados staff-only**

### Expressividade Completa  
- 🔄 **Loops, filtros, condições complexas via sintaxe YAML**
- 📊 **Agregações, transformações, decisões declarativas**
- 🎯 **Integração funcional com behaviors nativos**

### Abertura e Evolução
- 🌐 **Protocolo universal - agentes trocáveis entre plataformas**
- 📈 **Marketplace de behaviors certificados**
- 🔗 **Documentação auto-gerada pelo schema integrado**

O Beddel revoluciona ao transformar lógica JavaScript complexa em **dados estruturados seguros e universalmente trocáveis**, mantendo toda a capacidade computacional através de um runtime interpretador declarativo.
