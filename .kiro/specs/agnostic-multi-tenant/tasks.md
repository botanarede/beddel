# Implementation Plan: Agnostic Multi-Tenant

## Overview

Implementação incremental da refatoração multi-tenant agnóstico, começando pelas interfaces e providers, depois refatorando o TenantManager existente.

## Tasks

- [-] 1. Criar interfaces base do sistema multi-tenant
  - [-] 1.1 Criar arquivo `packages/beddel/src/tenant/interfaces.ts` com ITenantProvider, ITenantApp, ITenantDatabase, ITenantCollection, ITenantDocument
    - Definir tipos ProviderType, TenantConfig agnóstico, FirebaseProviderConfig, MemoryProviderConfig
    - Exportar todas as interfaces
    - _Requirements: 1.1, 1.2, 1.3, 1.13_

- [ ] 2. Implementar InMemoryTenantProvider
  - [ ] 2.1 Criar `packages/beddel/src/tenant/providers/InMemoryTenantProvider.ts`
    - Implementar ITenantProvider com Map em memória
    - Implementar ITenantApp, ITenantDatabase, ITenantCollection, ITenantDocument
    - _Requirements: 1.8_

- [ ] 3. Implementar FirebaseTenantProvider
  - [ ] 3.1 Criar `packages/beddel/src/tenant/providers/FirebaseTenantProvider.ts`
    - Extrair lógica Firebase do tenantManager.ts atual
    - Implementar ITenantProvider delegando para firebase-admin
    - Manter compatibilidade com comportamento existente
    - _Requirements: 1.7_

- [ ] 4. Criar ProviderFactory
  - [ ] 4.1 Criar `packages/beddel/src/tenant/providerFactory.ts`
    - Implementar createProvider(type: ProviderType): ITenantProvider
    - Validar configurações e lançar ValidationError para configs inválidas
    - _Requirements: 1.4, 1.14_

- [ ] 5. Refatorar TenantManager para usar interfaces
  - [ ] 5.1 Criar `packages/beddel/src/tenant/TenantManager.ts`
    - Copiar lógica de negócio do MultiTenantFirebaseManager
    - Substituir dependência direta de firebase-admin por ITenantProvider
    - Manter integração com AuditTrail, LGPDCompliance, GDPRCompliance
    - _Requirements: 1.5, 1.6, 1.10, 1.11_

- [ ] 6. Criar barrel export e deprecar arquivo antigo
  - [ ] 6.1 Criar `packages/beddel/src/tenant/index.ts`
    - Exportar TenantManager, interfaces, factory, providers
    - _Requirements: 1.1_
  - [ ] 6.2 Adicionar comentário @deprecated em `packages/beddel/src/firebase/tenantManager.ts`
    - Manter arquivo para retrocompatibilidade temporária
    - _Requirements: 1.7_

- [ ] 7. Checkpoint - Verificar implementação
  - Garantir que código compila sem erros
  - Verificar que imports estão corretos
  - Perguntar ao usuário se há dúvidas

- [ ]* 8. Testes e validações
  - [ ]* 8.1 Criar testes unitários para InMemoryTenantProvider
    - Testar CRUD básico
    - _Requirements: 1.3, 1.8_
  - [ ]* 8.2 Criar property test para Provider Factory
    - **Property 1: Provider Factory Correctness**
    - **Validates: Requirements 1.4**
  - [ ]* 8.3 Criar property test para Tenant Lifecycle
    - **Property 2: Tenant Lifecycle Round-Trip**
    - **Validates: Requirements 1.5, 1.9**
  - [ ]* 8.4 Criar property test para Database Operations
    - **Property 3: Database Operations Consistency**
    - **Validates: Requirements 1.3**
  - [ ]* 8.5 Criar property test para Error Handling
    - **Property 4: Invalid Config Error Handling**
    - **Property 5: Unsupported Operation Error**
    - **Validates: Requirements 1.12, 1.14**

- [ ] 9. Checkpoint final
  - Garantir que todos os testes passam
  - Perguntar ao usuário se há dúvidas

## Notes

- Tasks marcadas com `*` são opcionais e podem ser puladas para MVP mais rápido
- Implementação foca primeiro na funcionalidade core, testes ficam para o final
- FirebaseTenantProvider mantém compatibilidade total com comportamento atual
- InMemoryTenantProvider permite testes sem Firebase configurado
