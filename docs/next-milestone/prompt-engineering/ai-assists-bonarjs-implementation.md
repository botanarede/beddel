# Aplicação Prática do Guia de IA - BonarJS Boilerplate

## Visão Geral

Este documento mostra como aplicar as práticas do **Vibe Factor** especificamente no desenvolvimento do BonarJS Boilerplate, um projeto Next.js 15 + React 19 + Firebase com arquitetura de packages.

## 1. Diagramas de Arquitetura com Diagrams.net

### 1.1 Arquitetura Geral do Sistema

**Diagrama: Visão de Alto Nível**
```
[User] → [Next.js App] → [Firebase Auth] → [Firestore]
    ↓           ↓              ↓
[BonarJS UI] → [BonarJS SDK] → [API Routes]
    ↓           ↓              ↓
[Components] → [Hooks] → [Use Cases]
```

**Como criar no Diagrams.net:**
1. Acesse [diagrams.net](https://diagrams.net)
2. Use os shapes: Rectangle (componentes), Cylinder (banco), Cloud (Firebase)
3. Conecte com arrows direcionais
4. Adicione labels com tecnologias específicas

### 1.2 Fluxo de Autenticação

**Diagrama: Auth Flow**
```
[Login Page] → [Firebase Auth] → [Middleware] → [Protected Route]
     ↓              ↓               ↓              ↓
[useBonarJsAuth] → [Token] → [Validation] → [Dashboard]
```

### 1.3 Estrutura de Packages

**Diagrama: Package Dependencies**
```
bonarjs-boilerplate/
├── packages/
│   ├── bonarjs-ui/ (Componentes + Theme)
│   └── bonarjs-sdk/ (Lógica + Firebase)
├── app/ (Next.js 15)
└── components/ (Específicos do boilerplate)
```

## 2. Aplicação Prática do Vibe Factor

### 2.1 Maximizando o Contexto (c) - Domínio BonarJS

#### Documentação de Contexto Específico

**Criar arquivo: `docs/domain-context.md`**
```markdown
# Contexto de Domínio - BonarJS

## Entidades Principais
- User: Usuários do sistema
- DynamicTable: Tabelas dinâmicas configuráveis
- Evento: Eventos do sistema

## Padrões Arquiteturais
- Repository Pattern: Separação de dados
- Provider Pattern: Contexto React
- Hook Pattern: Lógica reutilizável

## Regras de Negócio
- Autenticação obrigatória para rotas protegidas
- Tabelas dinâmicas com validação Zod
- Temas configuráveis por tenant
```

#### ADRs (Architecture Decision Records)

**Criar: `docs/adr/001-firebase-auth.md`**
```markdown
# ADR-001: Firebase Authentication

## Status
Aceito

## Contexto
Necessidade de autenticação robusta e escalável

## Decisão
Usar Firebase Auth com custom tokens

## Consequências
- Integração nativa com Firestore
- Suporte a múltiplos provedores
- Middleware de proteção automático
```

### 2.2 Engenharia de Prompts Específica

#### Templates para BonarJS

**Prompt para Componentes UI:**
```
Contexto: BonarJS UI Package - Sistema de componentes baseado em Radix UI + Tailwind
Papel: Desenvolvedor sênior especialista em design systems
Tarefa: Criar componente [NOME] seguindo padrões BonarJS
Restrições: 
- Usar class-variance-authority para variantes
- Implementar forwardRef
- Incluir TypeScript interfaces
- Seguir padrão de export do index.ts
- Usar tokens do tema (spacing, colors, typography)
Formato: TypeScript + Tailwind + Radix UI
Exemplo: Similar ao button.tsx existente
```

**Prompt para Hooks:**
```
Contexto: BonarJS SDK - Hook para [FUNCIONALIDADE]
Papel: Arquitetor de software especialista em React + Firebase
Tarefa: Implementar hook use[Nome] seguindo padrões BonarJS
Restrições:
- Usar react-firebase-hooks
- Implementar error handling
- Incluir loading states
- Seguir padrão de retorno { data, loading, error }
- Usar TypeScript generics quando apropriado
Formato: TypeScript + Firebase + React Hooks
Exemplo: Similar ao useBonarJsAuth.ts
```

**Prompt para API Routes:**
```
Contexto: Next.js 15 API Routes para BonarJS
Papel: Desenvolvedor backend especialista em Firebase + Next.js
Tarefa: Criar endpoint /api/[rota] seguindo padrões BonarJS
Restrições:
- Usar Firebase Admin SDK
- Implementar validação com Zod
- Incluir error handling padronizado
- Seguir convenção de response { success, data, error }
- Implementar rate limiting se necessário
Formato: TypeScript + Next.js 15 + Firebase Admin
Exemplo: Similar às rotas existentes em app/api/
```

### 2.3 Estratégias de Confiabilidade (r)

#### Testes Específicos para BonarJS

**Setup de Testes:**
```bash
# Instalar dependências de teste
npm install --save-dev @testing-library/react @testing-library/jest-dom jest jest-environment-jsdom
```

**Template de Teste para Componentes:**
```typescript
// __tests__/components/Button.test.tsx
import { render, screen } from '@testing-library/react'
import { Button } from '@/packages/bonarjs-ui/components/ui/button'

describe('Button Component', () => {
  it('renders with correct variant', () => {
    render(<Button variant="primary">Test</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-primary')
  })
})
```

**Template de Teste para Hooks:**
```typescript
// __tests__/hooks/useBonarJsAuth.test.ts
import { renderHook } from '@testing-library/react'
import { useBonarJsAuth } from '@/packages/bonarjs-sdk/hooks/useBonarJsAuth'

describe('useBonarJsAuth', () => {
  it('returns loading state initially', () => {
    const { result } = renderHook(() => useBonarJsAuth())
    expect(result.current.loading).toBe(true)
  })
})
```

#### Validação de Segurança

**Setup Semgrep para BonarJS:**
```yaml
# .semgrep.yml
rules:
  - id: firebase-security
    patterns:
      - pattern: firebase.auth().signInWithEmailAndPassword(...)
    message: "Use BonarJS auth hooks instead of direct Firebase calls"
    languages: [typescript]
    severity: WARNING
```

### 2.4 Experiência (e) - Padrões BonarJS

#### Biblioteca de Padrões

**Criar: `docs/patterns/component-patterns.md`**
```markdown
# Padrões de Componentes BonarJS

## Estrutura Padrão
```typescript
// 1. Interface
interface ComponentProps {
  variant?: 'primary' | 'secondary'
  size?: 'sm' | 'md' | 'lg'
  children: React.ReactNode
}

// 2. Variantes com CVA
const componentVariants = cva(
  "base-classes",
  {
    variants: {
      variant: {
        primary: "primary-classes",
        secondary: "secondary-classes"
      }
    }
  }
)

// 3. Componente com forwardRef
export const Component = forwardRef<HTMLDivElement, ComponentProps>(
  ({ variant, size, children, ...props }, ref) => {
    return (
      <div ref={ref} className={componentVariants({ variant, size })} {...props}>
        {children}
      </div>
    )
  }
)
```

#### Debugging Patterns

**Criar: `docs/debugging/firebase-debugging.md`**
```markdown
# Debugging Firebase no BonarJS

## Problemas Comuns
1. **Auth não funciona**: Verificar Firebase config
2. **Firestore rules**: Testar no console
3. **Middleware**: Verificar token validation

## Ferramentas
- Firebase Emulator Suite
- React DevTools
- Network tab para API calls
```

## 3. Fluxo de Trabalho Prático

### 3.1 Setup Inicial com IA

**Script de Setup:**
```bash
#!/bin/bash
# setup-bonarjs-ai.sh

echo "🚀 Setup BonarJS com IA Assist"

# 1. Instalar dependências
npm install

# 2. Configurar Firebase
cp .env.local.example .env.local
echo "⚠️  Configure suas credenciais Firebase no .env.local"

# 3. Setup de desenvolvimento
npm run dev

echo "✅ Setup completo! Acesse http://localhost:3000"
```

### 3.2 Processo de Desenvolvimento

#### Fase 1: Planejamento com IA
```markdown
1. **Definir Requisitos**
   - Usar prompt: "Como implementar [feature] no BonarJS seguindo padrões existentes?"

2. **Criar Diagrama**
   - Usar Diagrams.net para mapear fluxo
   - Documentar em docs/architecture/

3. **Preparar Prompts**
   - Criar templates específicos para BonarJS
   - Definir restrições e padrões
```

#### Fase 2: Implementação
```markdown
1. **Componente UI**
   - Prompt: Template de componente BonarJS
   - Validação: Testes + Storybook
   - Review: Seguir padrões existentes

2. **Hook SDK**
   - Prompt: Template de hook BonarJS
   - Validação: Testes + Firebase rules
   - Review: Error handling + TypeScript

3. **API Route**
   - Prompt: Template de API BonarJS
   - Validação: Testes + Security scan
   - Review: Performance + Error handling
```

#### Fase 3: Validação
```markdown
1. **Testes Automatizados**
   - Unit tests para componentes
   - Integration tests para hooks
   - E2E tests para fluxos críticos

2. **Análise de Qualidade**
   - Semgrep para segurança
   - SonarQube para qualidade
   - Bundle analyzer para performance

3. **Documentação**
   - Atualizar README
   - Documentar novos padrões
   - Criar exemplos de uso
```

## 4. Ferramentas Específicas para BonarJS

### 4.1 Desenvolvimento

**VS Code Extensions:**
```json
{
  "recommendations": [
    "bradlc.vscode-tailwindcss",
    "ms-vscode.vscode-typescript-next",
    "firebase.vscode-firebase-explorer",
    "esbenp.prettier-vscode"
  ]
}
```

**Scripts de Desenvolvimento:**
```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "test": "jest",
    "test:watch": "jest --watch",
    "lint": "eslint . --ext .ts,.tsx",
    "typecheck": "tsc --noEmit",
    "firebase:emulators": "firebase emulators:start",
    "storybook": "storybook dev -p 6006"
  }
}
```

### 4.2 Monitoramento

**Métricas BonarJS:**
```typescript
// lib/analytics.ts
export const trackBonarJSEvent = (event: string, properties?: any) => {
  // Firebase Analytics
  analytics().logEvent(event, {
    package: 'bonarjs',
    ...properties
  })
}

// Métricas específicas
export const trackComponentUsage = (componentName: string) => {
  trackBonarJSEvent('component_used', { component: componentName })
}
```

## 5. Exemplos Práticos

### 5.1 Criando um Novo Componente

**Prompt para IA:**
```
Crie um componente Card para BonarJS UI seguindo estes padrões:

Contexto: Sistema de design BonarJS baseado em Radix UI + Tailwind
Estrutura: 
- Interface TypeScript com variants (default, elevated, outlined)
- Usar class-variance-authority para styling
- Implementar forwardRef
- Exportar do index.ts

Exemplo base: button.tsx
Restrições: Acessibilidade, responsividade, tema consistente
```

**Resultado esperado:**
```typescript
// components/ui/card.tsx
import { cva, type VariantProps } from "class-variance-authority"
import { forwardRef } from "react"

const cardVariants = cva(
  "rounded-lg border bg-card text-card-foreground shadow-sm",
  {
    variants: {
      variant: {
        default: "border-border",
        elevated: "border-border shadow-lg",
        outlined: "border-2 border-border"
      }
    },
    defaultVariants: {
      variant: "default"
    }
  }
)

export interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant, ...props }, ref) => (
    <div
      ref={ref}
      className={cardVariants({ variant, className })}
      {...props}
    />
  )
)
```

### 5.2 Criando um Hook

**Prompt para IA:**
```
Crie um hook useDynamicTable para BonarJS SDK:

Contexto: Hook para gerenciar tabelas dinâmicas no Firestore
Funcionalidades:
- Listar itens com paginação
- Criar/editar/deletar itens
- Loading states e error handling
- TypeScript generics para tipagem

Padrão: Similar ao useBonarJsAuth.ts
Restrições: Firebase security rules, performance, cache
```

## 6. Métricas de Sucesso

### 6.1 Vibe Factor para BonarJS

**Cálculo Específico:**
```typescript
// e (Experiência): Conhecimento de Next.js 15 + Firebase + BonarJS
// r (Confiabilidade): Testes + Security + Performance
// c (Contexto): Domínio BonarJS + Padrões arquiteturais
// n (Tentativas): Prompts específicos vs genéricos
// AI(k): Tempo economizado vs qualidade

const bonarJSVibeFactor = (experience, reliability, context, attempts, aiEfficiency) => {
  return (experience * reliability * context) / (attempts * (1 - aiEfficiency))
}
```

**Métricas de Acompanhamento:**
- Tempo médio para criar componente: < 30 min
- Taxa de bugs em produção: < 1%
- Cobertura de testes: > 80%
- Performance score: > 90

## 7. Conclusão

Aplicar o Vibe Factor no BonarJS Boilerplate significa:

1. **Contexto Específico**: Documentar padrões BonarJS
2. **Prompts Otimizados**: Templates para cada tipo de arquivo
3. **Validação Rigorosa**: Testes + Security + Performance
4. **Experiência Acumulada**: Biblioteca de padrões e soluções

**Próximos Passos:**
1. Implementar templates de prompts
2. Configurar ferramentas de validação
3. Criar documentação de padrões
4. Estabelecer métricas de acompanhamento

---

**Lembre-se**: O sucesso do BonarJS depende da qualidade da colaboração humano-IA, não da substituição do desenvolvedor. Seja intencional sobre como você usa IA para amplificar sua expertise em Next.js, Firebase e design systems.

