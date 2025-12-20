# Design Document: Agnostic Multi-Tenant

## Overview

Refatoração do sistema multi-tenant do Beddel para eliminar o acoplamento com Firebase Admin SDK. A solução usa o padrão Strategy para permitir trocar providers de backend sem alterar código de negócio.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      TenantManager                          │
│  (Singleton - orquestra operações usando interfaces)        │
├─────────────────────────────────────────────────────────────┤
│  - provider: ITenantProvider                                │
│  - auditTrail: AuditTrail                                   │
│  - lgpdCompliance: LGPDCompliance                           │
│  - gdprCompliance: GDPRCompliance                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    ITenantProvider                          │
│  (Interface - contrato para providers)                      │
├─────────────────────────────────────────────────────────────┤
│  + initialize(config): Promise<ITenantApp>                  │
│  + get(tenantId): ITenantApp                                │
│  + remove(tenantId): Promise<void>                          │
│  + list(): string[]                                         │
└─────────────────────────────────────────────────────────────┘
           ▲                    ▲                    ▲
           │                    │                    │
┌──────────┴───────┐ ┌─────────┴────────┐ ┌────────┴─────────┐
│ FirebaseProvider │ │ InMemoryProvider │ │ [FutureProvider] │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

## Components and Interfaces

### ITenantProvider

```typescript
interface ITenantProvider {
  initialize(config: TenantConfig): Promise<ITenantApp>;
  get(tenantId: string): ITenantApp;
  remove(tenantId: string): Promise<void>;
  list(): string[];
  readonly type: ProviderType;
}
```

### ITenantApp

```typescript
interface ITenantApp {
  readonly tenantId: string;
  getDatabase(): ITenantDatabase;
  destroy(): Promise<void>;
}
```

### ITenantDatabase

```typescript
interface ITenantDatabase {
  collection(name: string): ITenantCollection;
}

interface ITenantCollection {
  doc(id: string): ITenantDocument;
  add(data: Record<string, unknown>): Promise<string>;
  get(): Promise<Array<{ id: string; data: Record<string, unknown> }>>;
}

interface ITenantDocument {
  get(): Promise<Record<string, unknown> | null>;
  set(data: Record<string, unknown>): Promise<void>;
  update(data: Record<string, unknown>): Promise<void>;
  delete(): Promise<void>;
}
```

### TenantConfig (Agnóstico)

```typescript
type ProviderType = 'firebase' | 'memory';

interface TenantConfig {
  tenantId: string;
  securityProfile: 'ultra-secure' | 'tenant-isolated';
  dataRetentionDays: number;
  lgpdEnabled: boolean;
  gdprEnabled: boolean;
  provider: ProviderType;
  providerConfig: FirebaseProviderConfig | MemoryProviderConfig;
}

interface FirebaseProviderConfig {
  projectId: string;
  databaseURL: string;
  storageBucket: string;
}

interface MemoryProviderConfig {
  persistToDisk?: boolean;
}
```

### ProviderFactory

```typescript
function createProvider(type: ProviderType): ITenantProvider {
  switch (type) {
    case 'firebase':
      return new FirebaseTenantProvider();
    case 'memory':
      return new InMemoryTenantProvider();
    default:
      throw new ValidationError(`Unknown provider type: ${type}`);
  }
}
```

## Data Models

### Estrutura de Diretórios

```
packages/beddel/src/
├── tenant/
│   ├── interfaces.ts          # ITenantProvider, ITenantApp, ITenantDatabase
│   ├── TenantManager.ts       # Manager agnóstico (refatorado)
│   ├── providerFactory.ts     # Factory function
│   └── providers/
│       ├── FirebaseTenantProvider.ts
│       └── InMemoryTenantProvider.ts
└── firebase/
    └── tenantManager.ts       # DEPRECATED (manter para migração)
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Provider Factory Correctness

*For any* valid ProviderType, the createProvider function SHALL return an object that implements ITenantProvider with all required methods.

**Validates: Requirements 1.4**

### Property 2: Tenant Lifecycle Round-Trip

*For any* TenantConfig, initializing a tenant and then removing it SHALL result in the tenant no longer being accessible via get().

**Validates: Requirements 1.5, 1.9**

### Property 3: Database Operations Consistency

*For any* data written to a tenant's database via set(), a subsequent get() SHALL return equivalent data.

**Validates: Requirements 1.3**

### Property 4: Invalid Config Error Handling

*For any* invalid provider configuration, the factory or provider SHALL throw ValidationError before any tenant initialization occurs.

**Validates: Requirements 1.14**

### Property 5: Unsupported Operation Error

*For any* operation not supported by a provider, calling that operation SHALL throw NotSupportedError with a descriptive message.

**Validates: Requirements 1.12**

## Error Handling

| Erro | Quando | Ação |
|------|--------|------|
| `ValidationError` | Config inválida | Lançar antes de inicializar |
| `NotFoundError` | Tenant não existe | Lançar em get() |
| `NotSupportedError` | Operação não suportada | Lançar com mensagem descritiva |
| `TenantAlreadyExistsError` | Tenant duplicado | Lançar em initialize() |

## Testing Strategy

### Unit Tests

- Testar cada provider isoladamente
- Testar factory com configs válidas e inválidas
- Testar integração TenantManager → Provider

### Property-Based Tests

- Usar fast-check para gerar TenantConfigs aleatórios
- Verificar propriedades de round-trip e consistência
- Mínimo 100 iterações por propriedade

### Configuração de Testes

```typescript
// Tag format para property tests
// Feature: agnostic-multi-tenant, Property 1: Provider Factory Correctness
```
