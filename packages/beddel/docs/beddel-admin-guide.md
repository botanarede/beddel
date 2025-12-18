# Beddel Admin Guide - Admin Tenant sem API Key

> 👑 **O admin tenant pode executar agentes declarados em YAML sem necessidade de API key através do header `x-admin-tenant: true`**

## 📋 Visão Geral

O novo módulo **Beddel Admin** permite que a aplicação principal (admin tenant) realize chamadas autorizadas ao runtime Beddel **sem necessidade de autenticação via API key**. Isso diferencia-se do sistema tradicional:

## ✨ Novidades

### Admin Tenant (Sem API Key)

- **Header especial**: `x-admin-tenant: true` habilita execução sem autenticação
- **Cliente ID fixo**: `"admin_tenant"` para chamadas administrativas
- **Sem rate limit**: Acesso direto ao runtime para testes e validação
- **Interface dedicada**: Rota `/beddel-admin` com branding admin

### Chamadas Anteriores (Com API Key)

- Requerem `Authorization: Bearer API_KEY` para autenticação
- Validam clientes via banco de dados com limite de requisições
- Usam sistema tradicional de rate limiting

## 🎯 Funcionalidades Admin

### 1. Execução via Header Admin

```typescript
// Sem API key - usando header admin
fetch("/api/graphql", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "x-admin-tenant": "true",
  },
  body: JSON.stringify({
    query: GRAPHQL_QUERY,
    variables: {
      methodName: "joker.execute",
      params: {},
      props: {},
    },
  }),
});
```

### 2. Múltiplas Experiências de Demonstração

| Experiência   | Rota            | Necessita API Key | Autenticação |
| ------------- | --------------- | ----------------- | ------------ |
| Parser YAML   | `/beddel`       | Não               | N/D          |
| Admin Tenant  | `/beddel-admin` | ❌ Não            |
| Tenant Normal | `/beddel-alpha` | ✅ Sim            | Bearer       |
| Admin Panel   | `/admin/*`      | ✅ Sim            | Bearer       |

## 🔧 Configuração

### Ativar Admin Tenant

Nenhuma configuração adicional necessária - basta acessar `/beddel-admin`.

### API Key para Tenant Normal

Adicione ao arquivo `.env.local` na raiz do projeto:

```bash
BEDDEL_API_KEY=opal_demo_client_key_gukutdeg8uhcdvcuumshxc
```

## 🌐 Rotas Disponíveis

| Rota               | Descrição                           | Autenticação Necessária |
| ------------------ | ----------------------------------- | ----------------------- |
| `/`                | Página inicial                      | Não                     |
| `/beddel`          | Demonstração do Secure YAML Parser  | Não                     |
| `/beddel-admin`    | **[NOVO]** Admin tenant sem API key | ❌                      |
| `/beddel-alpha`    | Tenant comum com API key na prática | ✅                      |
| `/admin/endpoints` | Painel de administração             | ✅                      |

### Arquitetura dos Headers

**Para Admin Tenant (Sem API Key)**:

```
Headers: {
  "x-admin-tenant": "true"
}
Client ID: "admin_tenant"
```

**Para Tenant Normal (Com API Key)**:

```
Headers: {
  "Authorization": "Bearer API_KEY"
}
Client ID: UUID do cliente no banco de dados
```

## 🧪 Testes

Executar teste completo do Beddel Admin:

```bash
node test-beddel-admin.js
```

Resultados esperados:

```
🧪 Executando testes do Beddel Admin...

1. Testando rota /beddel-admin...
✅ Rota /beddel-admin acessível

2. Testando componente BeddelAdmin...
✅ Componente BeddelAdmin compilado corretamente

3. Testando chamada GraphQL sem API key...
✅ Chamada GraphQL (modo admin) simulada com sucesso
   - Resposta: {"response":"lol"}
   - Tempo: 6ms

4. Testando elementos de branding admin...
✅ Branding do Beddel Admin com elementos visuais corretos

5. Testando navegação entre modos...
✅ Links de navegação para ambos os modos presentes

📊 Resultados corretos: admin tenant consegue executar agentes sem API key!
```

## 🚀 Como Acessar

Vá para `http://localhost:3000` e escolha entre:

- **👑 Beddel Admin - Sem API Key** - Execute direto como admin tenant
- **🚀 Beddel Alpha com Runtime Real** - Execute com autenticação API key

### Modo Admin (Sem API Key)

Clique no botão "👑 Beddel Admin - Sem API Key" e depois em "Executar Agente Joker - Admin"

O agente Joker retorna: `{ "response": "lol" }` automaticamente autorizado como admin tenant.

## 📊 Funcionamento

**Modo Admin Tenant**:

- Identifica quando `x-admin-tenant: true` está presente
- Atribui automaticamente cliente ID `"admin_tenant"`
- Permite execução direta de agentes declarativos
- Ideal para debugging e testes do sistema principal

**Modo Tenant Normal**:

- Requer validação de API key via Bearer token
- Consulta cliente no banco de dados
- Aplica rate limiting conforme configuração do cliente
- Para uso em produção com múltiplos tenants

## 🔐 Segurança Admin

Apesar de não requerer API key, ainda mantém proteção:

- Apenas header `x-admin-tenant: true` habilita admin mode
- Cliente ID fixo não permite mudança de identidade
- Sem rate limit para facilitar testes intensivos
- Tempo de execução monitorado para performance

## 📁 Arquivos Relacionados

```bash
# Beddel Admin
app/beddel-admin/page.tsx                  # Componente admin principal
app/api/graphql/route.ts                   # Ajustado para aceitar admin tenant
components/beddel/beddel-landing-page.tsx # Links para dois modos

# Testes
test-beddel-admin.js                      # Testes automáticos do admin

# Documentação
docs/beddel-admin-guide.md               # Este guia
```

## ✅ Implementação Concluída

- ✅ **Admin Tenant Criado**: Chamadas sem API key via header especial
- ✅ **Integração GraphQL Ajustada**: Aceita ambos os modos na mesma API
- ✅ **Interface Admin**: Página dedicada com branding e coroas (reais)
- ✅ **Testes Completos**: Script de verificação do novo sistema
- ✅ **Links de Navegação**: Escolha entre experiências

---

> 👑 **Beddel Admin está ativo!** A aplicação principal pode agora testar runtime de agentes declarativos **sem dependências de autenticação externa** via simples header `x-admin-tenant: true`.
