# Templates de Prompts para BonarJS - Baseado em Pesquisa Científica

## Base Científica

Este documento é baseado na pesquisa **"Selection of Prompt Engineering Techniques for Code Generation through Predicting Code Complexity"** ([arXiv:2409.16416](https://arxiv.org/pdf/2409.16416)) que demonstra como selecionar automaticamente as melhores técnicas de engenharia de prompts baseado na complexidade do código.

### Insights Principais da Pesquisa

1. **PET-Select**: Modelo que seleciona automaticamente a melhor técnica de prompt baseado na complexidade do código
2. **Melhoria de 1.9%** na precisão pass@1 com **74.8% menos tokens** utilizados
3. **Classificação por Complexidade**: Problemas simples vs complexos requerem abordagens diferentes
4. **Técnicas Multi-Estágio**: Incorporação de respostas em múltiplas etapas

## Framework de Seleção de Prompts para BonarJS

### 1. Classificação por Complexidade

#### Problemas Simples (Vibe Factor < 2)
- Componentes básicos (Button, Input, Card)
- Hooks simples (useState, useEffect básicos)
- Validações Zod simples
- **Técnica Recomendada**: Few-shot prompting

#### Problemas Complexos (Vibe Factor > 3)
- Arquitetura de packages
- Integração Firebase complexa
- Hooks com múltiplas dependências
- **Técnica Recomendada**: Chain-of-Thought + Self-Refinement

### 2. Técnicas Específicas por Categoria

## Templates de Prompts Otimizados

### 2.1 Componentes UI (Complexidade Baixa)

#### Template: Few-Shot Prompting
```
Contexto: BonarJS UI Package - Sistema de componentes baseado em Radix UI + Tailwind
Papel: Desenvolvedor especialista em design systems
Tarefa: Criar componente [NOME] seguindo padrões BonarJS

Exemplos de componentes similares:
[Incluir 2-3 exemplos de componentes existentes]

Restrições:
- Usar class-variance-authority para variantes
- Implementar forwardRef
- Incluir TypeScript interfaces
- Seguir padrão de export do index.ts

Formato: TypeScript + Tailwind + Radix UI
```

**Exemplo Prático:**
```
Contexto: BonarJS UI Package - Sistema de componentes baseado em Radix UI + Tailwind
Papel: Desenvolvedor especialista em design systems
Tarefa: Criar componente Badge seguindo padrões BonarJS

Exemplos de componentes similares:
// Button.tsx
const buttonVariants = cva("base-classes", { variants: { variant: { primary: "..." } } })
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({ variant, ...props }, ref) => (
  <button ref={ref} className={buttonVariants({ variant })} {...props} />
))

Restrições:
- Usar class-variance-authority para variantes
- Implementar forwardRef
- Incluir TypeScript interfaces
- Seguir padrão de export do index.ts

Formato: TypeScript + Tailwind + Radix UI
```

### 2.2 Hooks SDK (Complexidade Média)

#### Template: Chain-of-Thought Prompting
```
Contexto: BonarJS SDK - Hook para [FUNCIONALIDADE]
Papel: Arquitetor de software especialista em React + Firebase
Tarefa: Implementar hook use[Nome] seguindo padrões BonarJS

Raciocínio passo a passo:
1. Analisar requisitos do hook
2. Definir interface TypeScript
3. Implementar lógica de estado
4. Adicionar error handling
5. Incluir loading states
6. Implementar cleanup

Restrições:
- Usar react-firebase-hooks
- Implementar error handling
- Incluir loading states
- Seguir padrão de retorno { data, loading, error }
- Usar TypeScript generics quando apropriado

Formato: TypeScript + Firebase + React Hooks
```

**Exemplo Prático:**
```
Contexto: BonarJS SDK - Hook para gerenciar tabelas dinâmicas
Papel: Arquitetor de software especialista em React + Firebase
Tarefa: Implementar hook useDynamicTable seguindo padrões BonarJS

Raciocínio passo a passo:
1. Analisar requisitos: CRUD operations, paginação, filtros
2. Definir interface: { data, loading, error, create, update, delete }
3. Implementar lógica: Firebase queries, state management
4. Adicionar error handling: try/catch, error states
5. Incluir loading states: loading indicators
6. Implementar cleanup: unsubscribe listeners

Restrições:
- Usar react-firebase-hooks
- Implementar error handling
- Incluir loading states
- Seguir padrão de retorno { data, loading, error }
- Usar TypeScript generics quando apropriado

Formato: TypeScript + Firebase + React Hooks
```

### 2.3 Arquitetura Complexa (Complexidade Alta)

#### Template: Self-Refinement + Chain-of-Thought
```
Contexto: BonarJS Boilerplate - Arquitetura de packages Next.js 15 + Firebase
Papel: Arquiteto de software sênior especialista em monorepos
Tarefa: [TAREFA COMPLEXA]

Raciocínio inicial:
1. Analisar requisitos arquiteturais
2. Identificar dependências entre packages
3. Definir interfaces e contratos
4. Implementar solução
5. Validar integração

Auto-refinamento:
- Revisar código gerado
- Identificar possíveis melhorias
- Otimizar performance
- Validar padrões BonarJS
- Verificar integração com Firebase

Restrições:
- Manter compatibilidade com Next.js 15
- Seguir padrões de monorepo
- Integrar com Firebase
- Manter TypeScript strict mode
- Implementar testes

Formato: TypeScript + Next.js 15 + Firebase + Monorepo
```

### 2.4 API Routes (Complexidade Média-Alta)

#### Template: Progressive-Hint Prompting
```
Contexto: Next.js 15 API Routes para BonarJS
Papel: Desenvolvedor backend especialista em Firebase + Next.js
Tarefa: Criar endpoint /api/[rota] seguindo padrões BonarJS

Dicas progressivas:
1. Estrutura básica: Handler, validação, response
2. Integração Firebase: Admin SDK, Firestore
3. Validação: Zod schemas, error handling
4. Segurança: Auth middleware, rate limiting
5. Performance: Caching, otimizações

Restrições:
- Usar Firebase Admin SDK
- Implementar validação com Zod
- Incluir error handling padronizado
- Seguir convenção de response { success, data, error }
- Implementar rate limiting se necessário

Formato: TypeScript + Next.js 15 + Firebase Admin
```

## 3. Técnicas Avançadas Baseadas na Pesquisa

### 3.1 Contrastive Learning para Seleção de Prompts

#### Implementação Prática:
```typescript
// Sistema de classificação de complexidade
interface PromptComplexity {
  simple: boolean;      // Vibe Factor < 2
  medium: boolean;      // Vibe Factor 2-3
  complex: boolean;     // Vibe Factor > 3
}

// Seleção automática de técnica
function selectPromptTechnique(complexity: PromptComplexity): string {
  if (complexity.simple) return "few-shot";
  if (complexity.medium) return "chain-of-thought";
  if (complexity.complex) return "self-refinement";
  return "chain-of-thought";
}
```

### 3.2 Multi-Stage Response Optimization

#### Template para Respostas em Etapas:
```
Etapa 1 - Análise:
Analise o requisito e identifique a complexidade do problema.

Etapa 2 - Planejamento:
Crie um plano detalhado para implementação.

Etapa 3 - Implementação:
Implemente a solução seguindo o plano.

Etapa 4 - Refinamento:
Revise e melhore a implementação.

Etapa 5 - Validação:
Valide contra padrões BonarJS e requisitos.
```

### 3.3 Automated Prompt Selection

#### Sistema de Seleção Inteligente:
```typescript
interface PromptSelection {
  technique: 'few-shot' | 'chain-of-thought' | 'self-refinement' | 'progressive-hint';
  complexity: 'simple' | 'medium' | 'complex';
  estimatedTokens: number;
  expectedAccuracy: number;
}

function selectOptimalPrompt(task: string, context: BonarJSContext): PromptSelection {
  // Implementar lógica baseada na pesquisa PET-Select
  const complexity = analyzeCodeComplexity(task);
  const technique = selectPromptTechnique(complexity);
  
  return {
    technique,
    complexity,
    estimatedTokens: estimateTokenUsage(technique),
    expectedAccuracy: estimateAccuracy(technique, complexity)
  };
}
```

## 4. Templates Específicos por Domínio

### 4.1 Firebase Integration

#### Template: Firebase-Specific Chain-of-Thought
```
Contexto: Integração Firebase no BonarJS
Papel: Especialista em Firebase + React
Tarefa: [TAREFA FIREBASE]

Raciocínio Firebase:
1. Identificar serviço Firebase necessário (Auth, Firestore, Storage)
2. Configurar SDK (Client vs Admin)
3. Implementar segurança (Rules, Validation)
4. Gerenciar estado (Hooks, Context)
5. Tratar erros (Offline, Permissions)

Restrições:
- Usar Firebase v10+
- Implementar error handling
- Seguir security rules
- Otimizar performance
- Manter offline support

Formato: TypeScript + Firebase + React
```

### 4.2 Next.js 15 Specific

#### Template: Next.js 15 App Router
```
Contexto: Next.js 15 App Router no BonarJS
Papel: Especialista em Next.js 15 + React 19
Tarefa: [TAREFA NEXT.JS]

Raciocínio Next.js 15:
1. Estrutura App Router (app/ directory)
2. Server vs Client Components
3. Streaming e Suspense
4. Middleware e Route Protection
5. Performance Optimization

Restrições:
- Usar App Router
- Server Components quando possível
- Implementar middleware
- Otimizar bundle size
- Manter SEO

Formato: TypeScript + Next.js 15 + React 19
```

### 4.3 Monorepo Management

#### Template: Monorepo Architecture
```
Contexto: Monorepo BonarJS com packages
Papel: Arquiteto de monorepo especialista em npm workspaces
Tarefa: [TAREFA MONOREPO]

Raciocínio Monorepo:
1. Estrutura de packages
2. Dependências internas
3. Build e deployment
4. Versionamento
5. CI/CD pipeline

Restrições:
- Manter workspaces
- Gerenciar dependências
- Build otimizado
- Versionamento semântico
- CI/CD eficiente

Formato: TypeScript + npm workspaces + Monorepo
```

## 5. Métricas de Eficácia

### 5.1 Acompanhamento de Performance

#### Métricas Baseadas na Pesquisa:
```typescript
interface PromptMetrics {
  accuracy: number;        // pass@1 accuracy
  tokenUsage: number;      // tokens utilizados
  timeToComplete: number;  // tempo para completar
  complexity: 'simple' | 'medium' | 'complex';
  technique: string;       // técnica utilizada
}

// Meta: 1.9% melhoria na precisão com 74.8% menos tokens
const targetMetrics: PromptMetrics = {
  accuracy: 0.85,          // 85% de precisão
  tokenUsage: 0.25,        // 75% redução de tokens
  timeToComplete: 300,     // 5 minutos
  complexity: 'medium',
  technique: 'chain-of-thought'
};
```

### 5.2 Dashboard de Métricas

#### Implementação:
```typescript
// Componente para acompanhar métricas
const PromptMetricsDashboard = () => {
  const [metrics, setMetrics] = useState<PromptMetrics[]>([]);
  
  return (
    <div className="metrics-dashboard">
      <h3>Métricas de Prompts BonarJS</h3>
      <div className="metrics-grid">
        <MetricCard title="Precisão" value={`${accuracy}%`} />
        <MetricCard title="Tokens Economizados" value={`${tokenSavings}%`} />
        <MetricCard title="Tempo Médio" value={`${avgTime}min`} />
      </div>
    </div>
  );
};
```

## 6. Implementação Prática

### 6.1 Setup do Sistema

#### Configuração Inicial:
```bash
# Instalar dependências para análise de complexidade
npm install --save-dev @typescript-eslint/parser @typescript-eslint/eslint-plugin

# Configurar métricas
npm install --save-dev @vercel/analytics
```

#### Script de Análise:
```typescript
// scripts/analyze-complexity.ts
import { analyzeCodeComplexity } from './complexity-analyzer';

export function analyzeBonarJSTask(task: string): PromptSelection {
  const complexity = analyzeCodeComplexity(task);
  return selectOptimalPrompt(task, complexity);
}
```

### 6.2 Integração com VS Code

#### Extension para Seleção Automática:
```json
// .vscode/settings.json
{
  "bonarjs.promptSelection": {
    "autoSelect": true,
    "complexityThreshold": 2,
    "preferredTechnique": "chain-of-thought"
  }
}
```

## 7. Conclusão

### Benefícios Esperados (Baseado na Pesquisa):

1. **1.9% melhoria na precisão** dos prompts
2. **74.8% redução no uso de tokens**
3. **Seleção automática** da melhor técnica
4. **Otimização de custos** com IA
5. **Melhoria na qualidade** do código gerado

### Próximos Passos:

1. **Implementar sistema de classificação** de complexidade
2. **Configurar métricas** de acompanhamento
3. **Treinar equipe** nas novas técnicas
4. **Validar resultados** com dados reais
5. **Iterar e melhorar** baseado nos resultados

---

**Referência Científica**: [Selection of Prompt Engineering Techniques for Code Generation through Predicting Code Complexity](https://arxiv.org/pdf/2409.16416) - Chung-Yu Wang, Alireza DaghighFarsoodeh, Hung Viet Pham (2024)

**Aplicação Prática**: Este documento adapta as descobertas científicas para o contexto específico do BonarJS Boilerplate, maximizando a eficácia da colaboração humano-IA no desenvolvimento de software.

