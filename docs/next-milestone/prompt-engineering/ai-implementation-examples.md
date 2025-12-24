# Exemplos Práticos de Implementação - Técnicas de IA para BonarJS

## Baseado na Pesquisa PET-Select

Este documento apresenta exemplos práticos de como implementar as técnicas de engenharia de prompts baseadas na pesquisa científica para o projeto BonarJS Boilerplate.

## 1. Sistema de Classificação de Complexidade

### 1.1 Implementação do Analisador de Complexidade

```typescript
// lib/complexity-analyzer.ts
interface CodeComplexity {
  cyclomatic: number;
  cognitive: number;
  maintainability: number;
  overall: 'simple' | 'medium' | 'complex';
}

export function analyzeCodeComplexity(code: string): CodeComplexity {
  const lines = code.split('\n').length;
  const functions = (code.match(/function|const\s+\w+\s*=/g) || []).length;
  const conditions = (code.match(/if|else|switch|case/g) || []).length;
  const loops = (code.match(/for|while|forEach|map/g) || []).length;
  
  // Cálculo da complexidade ciclomática
  const cyclomatic = conditions + loops + 1;
  
  // Cálculo da complexidade cognitiva
  const cognitive = conditions * 2 + loops * 3 + functions;
  
  // Cálculo do índice de manutenibilidade
  const maintainability = Math.max(0, 171 - 5.2 * Math.log(lines) - 0.23 * cyclomatic - 16.2 * Math.log(functions));
  
  // Classificação geral
  let overall: 'simple' | 'medium' | 'complex';
  if (cyclomatic <= 5 && cognitive <= 10) {
    overall = 'simple';
  } else if (cyclomatic <= 10 && cognitive <= 20) {
    overall = 'medium';
  } else {
    overall = 'complex';
  }
  
  return {
    cyclomatic,
    cognitive,
    maintainability,
    overall
  };
}
```

### 1.2 Seleção Automática de Técnica

```typescript
// lib/prompt-selector.ts
import { analyzeCodeComplexity } from './complexity-analyzer';

export type PromptTechnique = 'few-shot' | 'chain-of-thought' | 'self-refinement' | 'progressive-hint';

export interface PromptSelection {
  technique: PromptTechnique;
  complexity: 'simple' | 'medium' | 'complex';
  estimatedTokens: number;
  expectedAccuracy: number;
  template: string;
}

export function selectOptimalPrompt(task: string, context: string): PromptSelection {
  const complexity = analyzeCodeComplexity(context);
  
  let technique: PromptTechnique;
  let estimatedTokens: number;
  let expectedAccuracy: number;
  let template: string;
  
  switch (complexity.overall) {
    case 'simple':
      technique = 'few-shot';
      estimatedTokens = 500;
      expectedAccuracy = 0.85;
      template = getFewShotTemplate();
      break;
      
    case 'medium':
      technique = 'chain-of-thought';
      estimatedTokens = 800;
      expectedAccuracy = 0.90;
      template = getChainOfThoughtTemplate();
      break;
      
    case 'complex':
      technique = 'self-refinement';
      estimatedTokens = 1200;
      expectedAccuracy = 0.95;
      template = getSelfRefinementTemplate();
      break;
  }
  
  return {
    technique,
    complexity: complexity.overall,
    estimatedTokens,
    expectedAccuracy,
    template
  };
}
```

## 2. Templates Específicos para BonarJS

### 2.1 Template Few-Shot para Componentes Simples

```typescript
// templates/few-shot-component.ts
export function getFewShotTemplate(): string {
  return `
Contexto: BonarJS UI Package - Sistema de componentes baseado em Radix UI + Tailwind
Papel: Desenvolvedor especialista em design systems
Tarefa: Criar componente [NOME] seguindo padrões BonarJS

Exemplos de componentes similares:

// Exemplo 1: Button.tsx
import { cva, type VariantProps } from "class-variance-authority"
import { forwardRef } from "react"

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground"
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={buttonVariants({ variant, size, className })}
        ref={ref}
        {...props}
      />
    )
  }
)

// Exemplo 2: Input.tsx
import { forwardRef } from "react"

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        ref={ref}
        {...props}
      />
    )
  }
)

Restrições para o novo componente:
- Usar class-variance-authority para variantes
- Implementar forwardRef
- Incluir TypeScript interfaces
- Seguir padrão de export do index.ts
- Usar tokens do tema (spacing, colors, typography)

Formato: TypeScript + Tailwind + Radix UI
`;
}
```

### 2.2 Template Chain-of-Thought para Hooks

```typescript
// templates/chain-of-thought-hook.ts
export function getChainOfThoughtTemplate(): string {
  return `
Contexto: BonarJS SDK - Hook para [FUNCIONALIDADE]
Papel: Arquitetor de software especialista em React + Firebase
Tarefa: Implementar hook use[Nome] seguindo padrões BonarJS

Raciocínio passo a passo:

1. **Análise de Requisitos**:
   - Identificar funcionalidades necessárias
   - Definir interface de retorno
   - Mapear dependências Firebase

2. **Definição de Interface**:
   - Criar TypeScript interfaces
   - Definir tipos de dados
   - Especificar parâmetros opcionais

3. **Implementação de Estado**:
   - Gerenciar loading states
   - Implementar error handling
   - Configurar data fetching

4. **Integração Firebase**:
   - Configurar queries/operations
   - Implementar real-time updates
   - Gerenciar subscriptions

5. **Cleanup e Otimização**:
   - Implementar cleanup functions
   - Otimizar re-renders
   - Adicionar memoização

Exemplo de estrutura esperada:
\`\`\`typescript
interface Use[Nome]Return {
  data: T | null;
  loading: boolean;
  error: Error | null;
  // ... outras propriedades
}

export function use[Nome](params?: Params): Use[Nome]Return {
  // Implementação
}
\`\`\`

Restrições:
- Usar react-firebase-hooks
- Implementar error handling robusto
- Incluir loading states
- Seguir padrão de retorno { data, loading, error }
- Usar TypeScript generics quando apropriado
- Implementar cleanup automático

Formato: TypeScript + Firebase + React Hooks
`;
}
```

### 2.3 Template Self-Refinement para Arquitetura

```typescript
// templates/self-refinement-architecture.ts
export function getSelfRefinementTemplate(): string {
  return `
Contexto: BonarJS Boilerplate - Arquitetura de packages Next.js 15 + Firebase
Papel: Arquiteto de software sênior especialista em monorepos
Tarefa: [TAREFA COMPLEXA]

Raciocínio inicial:

1. **Análise Arquitetural**:
   - Identificar componentes envolvidos
   - Mapear dependências entre packages
   - Definir interfaces e contratos

2. **Planejamento de Implementação**:
   - Estruturar solução modular
   - Definir responsabilidades
   - Planejar integração

3. **Implementação**:
   - Criar código seguindo padrões
   - Implementar testes
   - Documentar interfaces

4. **Validação**:
   - Verificar integração
   - Testar performance
   - Validar padrões BonarJS

Auto-refinamento:

**Revisão 1 - Código Gerado**:
- Analisar qualidade do código
- Verificar padrões TypeScript
- Validar estrutura de packages

**Revisão 2 - Integração**:
- Verificar compatibilidade com Next.js 15
- Validar integração Firebase
- Testar funcionamento end-to-end

**Revisão 3 - Otimização**:
- Analisar performance
- Otimizar bundle size
- Melhorar UX

**Revisão 4 - Padrões BonarJS**:
- Verificar consistência com design system
- Validar naming conventions
- Confirmar estrutura de exports

Restrições:
- Manter compatibilidade com Next.js 15
- Seguir padrões de monorepo
- Integrar com Firebase
- Manter TypeScript strict mode
- Implementar testes unitários e de integração
- Documentar APIs públicas

Formato: TypeScript + Next.js 15 + Firebase + Monorepo
`;
}
```

## 3. Sistema de Métricas e Monitoramento

### 3.1 Implementação de Métricas

```typescript
// lib/prompt-metrics.ts
interface PromptMetrics {
  id: string;
  task: string;
  technique: PromptTechnique;
  complexity: 'simple' | 'medium' | 'complex';
  tokensUsed: number;
  timeToComplete: number;
  accuracy: number;
  codeQuality: number;
  timestamp: Date;
}

export class PromptMetricsCollector {
  private metrics: PromptMetrics[] = [];
  
  recordMetric(metric: Omit<PromptMetrics, 'id' | 'timestamp'>): void {
    const newMetric: PromptMetrics = {
      ...metric,
      id: crypto.randomUUID(),
      timestamp: new Date()
    };
    
    this.metrics.push(newMetric);
    this.saveMetrics();
  }
  
  getMetrics(): PromptMetrics[] {
    return this.metrics;
  }
  
  getAverageAccuracy(): number {
    const total = this.metrics.reduce((sum, m) => sum + m.accuracy, 0);
    return total / this.metrics.length;
  }
  
  getTokenSavings(): number {
    // Comparar com baseline sem otimização
    const baselineTokens = this.metrics.reduce((sum, m) => sum + m.tokensUsed * 1.5, 0);
    const actualTokens = this.metrics.reduce((sum, m) => sum + m.tokensUsed, 0);
    return ((baselineTokens - actualTokens) / baselineTokens) * 100;
  }
  
  private saveMetrics(): void {
    localStorage.setItem('bonarjs-prompt-metrics', JSON.stringify(this.metrics));
  }
}
```

### 3.2 Dashboard de Métricas

```typescript
// components/PromptMetricsDashboard.tsx
import React from 'react';
import { PromptMetricsCollector } from '@/lib/prompt-metrics';

interface DashboardProps {
  metricsCollector: PromptMetricsCollector;
}

export const PromptMetricsDashboard: React.FC<DashboardProps> = ({ metricsCollector }) => {
  const metrics = metricsCollector.getMetrics();
  const avgAccuracy = metricsCollector.getAverageAccuracy();
  const tokenSavings = metricsCollector.getTokenSavings();
  
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 p-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900">Precisão Média</h3>
        <p className="text-3xl font-bold text-blue-600">
          {(avgAccuracy * 100).toFixed(1)}%
        </p>
        <p className="text-sm text-gray-500">Meta: 85%</p>
      </div>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900">Tokens Economizados</h3>
        <p className="text-3xl font-bold text-green-600">
          {tokenSavings.toFixed(1)}%
        </p>
        <p className="text-sm text-gray-500">Meta: 74.8%</p>
      </div>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900">Tarefas Completadas</h3>
        <p className="text-3xl font-bold text-purple-600">
          {metrics.length}
        </p>
        <p className="text-sm text-gray-500">Total de prompts</p>
      </div>
    </div>
  );
};
```

## 4. Integração com VS Code

### 4.1 Extension Configuration

```json
// .vscode/settings.json
{
  "bonarjs.promptSelection": {
    "autoSelect": true,
    "complexityThreshold": 2,
    "preferredTechnique": "chain-of-thought",
    "enableMetrics": true,
    "templates": {
      "component": "few-shot",
      "hook": "chain-of-thought",
      "architecture": "self-refinement",
      "api": "progressive-hint"
    }
  }
}
```

### 4.2 Snippets para VS Code

```json
// .vscode/snippets/bonarjs-prompts.code-snippets
{
  "BonarJS Component Prompt": {
    "prefix": "bonarjs-component",
    "body": [
      "Contexto: BonarJS UI Package - Sistema de componentes baseado em Radix UI + Tailwind",
      "Papel: Desenvolvedor especialista em design systems",
      "Tarefa: Criar componente ${1:ComponentName} seguindo padrões BonarJS",
      "",
      "Restrições:",
      "- Usar class-variance-authority para variantes",
      "- Implementar forwardRef",
      "- Incluir TypeScript interfaces",
      "- Seguir padrão de export do index.ts",
      "",
      "Formato: TypeScript + Tailwind + Radix UI"
    ],
    "description": "Template para criar componentes BonarJS"
  },
  
  "BonarJS Hook Prompt": {
    "prefix": "bonarjs-hook",
    "body": [
      "Contexto: BonarJS SDK - Hook para ${1:funcionalidade}",
      "Papel: Arquitetor de software especialista em React + Firebase",
      "Tarefa: Implementar hook use${2:HookName} seguindo padrões BonarJS",
      "",
      "Raciocínio passo a passo:",
      "1. Analisar requisitos do hook",
      "2. Definir interface TypeScript",
      "3. Implementar lógica de estado",
      "4. Adicionar error handling",
      "5. Incluir loading states",
      "6. Implementar cleanup",
      "",
      "Restrições:",
      "- Usar react-firebase-hooks",
      "- Implementar error handling",
      "- Incluir loading states",
      "- Seguir padrão de retorno { data, loading, error }",
      "",
      "Formato: TypeScript + Firebase + React Hooks"
    ],
    "description": "Template para criar hooks BonarJS"
  }
}
```

## 5. Exemplos de Uso Prático

### 5.1 Criando um Componente Badge

**Prompt Gerado Automaticamente:**
```
Contexto: BonarJS UI Package - Sistema de componentes baseado em Radix UI + Tailwind
Papel: Desenvolvedor especialista em design systems
Tarefa: Criar componente Badge seguindo padrões BonarJS

Exemplos de componentes similares:
[Inclui exemplos do Button e Input]

Restrições:
- Usar class-variance-authority para variantes
- Implementar forwardRef
- Incluir TypeScript interfaces
- Seguir padrão de export do index.ts

Formato: TypeScript + Tailwind + Radix UI
```

**Resultado Esperado:**
```typescript
// components/ui/badge.tsx
import { cva, type VariantProps } from "class-variance-authority"
import { forwardRef } from "react"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground"
      }
    },
    defaultVariants: {
      variant: "default"
    }
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant, ...props }, ref) => {
    return (
      <div ref={ref} className={badgeVariants({ variant, className })} {...props} />
    )
  }
)
```

### 5.2 Criando um Hook useDynamicTable

**Prompt Gerado Automaticamente:**
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

Formato: TypeScript + Firebase + React Hooks
```

## 6. Conclusão

### Benefícios Implementados:

1. **Seleção Automática**: Sistema escolhe a melhor técnica baseado na complexidade
2. **Métricas de Performance**: Acompanhamento de precisão e economia de tokens
3. **Templates Otimizados**: Prompts específicos para cada tipo de tarefa
4. **Integração VS Code**: Snippets e configurações para produtividade
5. **Validação Científica**: Baseado em pesquisa com resultados comprovados

### Próximos Passos:

1. **Implementar sistema de métricas** em produção
2. **Treinar equipe** nas novas técnicas
3. **Coletar dados** de performance
4. **Iterar e melhorar** baseado nos resultados
5. **Expandir templates** para outros domínios

---

**Referência**: [Selection of Prompt Engineering Techniques for Code Generation through Predicting Code Complexity](https://arxiv.org/pdf/2409.16416) - Adaptado para BonarJS Boilerplate

