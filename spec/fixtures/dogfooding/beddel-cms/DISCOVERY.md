# Beddel CMS — Discovery Document

## What Is This

A plan to build "Beddel CMS" — a multi-tenant static site CMS platform that
appropriates the skeleton of the existing Bonar CMS microsaas (frontend monorepo +
backend API + SDK) and rewires it to be managed, deployed, and billed through
Beddel workflows.

## Source Systems Analyzed

| System | Path | Role |
|--------|------|------|
| **bonar-cms** (frontend) | `~/www/2025/bonar-cms/` | Next.js monorepo, SSG export, Firebase Hosting per tenant |
| **bonar-cms-api** (backend) | `~/www/2025/bonar-cms-api/` | Next.js API routes, Firebase Admin, Firestore multi-tenant |
| **bonarjs-sdk** | `~/www/2025/bonar-cms/packages/bonarjs-sdk/` | Client SDK — auth, dynamic tables, hooks, providers |
| **Beddel SDK** | `~/www/2026/beddel/src/beddel-py/` | Python workflow engine — primitives, adapters, kits |

---

## 1. Architecture of the Existing Bonar CMS

### 1.1 Multi-Tenant Data Model (Firestore)

```
customers/{customerToken}          → { name, contact, whatsapp }
tables/{customerToken}             → { slug }  (tenant root)
tables/{customerToken}/{tableName} → { ...dynamic docs }
users/{userId}                     → { email, uid, apps: [customerToken] }
verification_codes/{id}            → { email, code, customerUid, createdAt }
```

- **Tenant isolation** is by `customerToken` (Firestore doc ID in `customers/`).
- The SDK sends `Authorization: <customerToken>` on every API call.
- The API validates the token against `customers/{token}` before any DB operation.
- Users belong to tenants via `apps[]` array (multi-tenant capable).

### 1.2 Frontend Monorepo

```
bonar-cms/
├── packages/
│   ├── bonarjs-sdk/     → Clean Architecture SDK (core/infra/presentation)
│   └── bonarjs-ui/      → Shared UI components (MUI + Radix + Tailwind)
├── src/apps/
│   ├── tenant-a.example.com/   → Main tenant (most complete)
│   └── ensaiorua.botanarede.com.br/    → Second tenant
└── sites/                              → SSG output per tenant
```

- Each app in `src/apps/` is a Next.js app with `output: 'export'` (SSG).
- `distDir` outputs to `sites/{domain}/` which Firebase Hosting serves.
- Apps share the monorepo `node_modules` (yarn workspaces).
- Each app has its own `.env` with `NEXT_PUBLIC_BONARJS_API_KEY` (= customerToken).

### 1.3 Backend API (bonar-cms-api)

Next.js API routes at `/api/`:

| Route | Guard | Purpose |
|-------|-------|---------|
| `tables/getItems` | guardRead (AppCheck) | List items from a dynamic table |
| `tables/getItemById` | guardRead | Get single item |
| `tables/setItem` | guardSmartWrite | Create/update item + optional email dispatch |
| `tables/deleteItemById` | guardSmartWrite | Delete item |
| `auth` | token validation | Email OTP login (Postmark) + custom token generation |
| `auth/verifyAppCheck` | — | AppCheck token verification |
| `users/add` | — | User creation |
| `mail/dispatchEventTicket` | — | Email dispatch |

Security layers:
- **AppCheck** (reCAPTCHA) for all reads
- **AppCheck + Firebase ID Token** for protected writes
- **Public submit tables** (`emails`, `reservas`) only need AppCheck

### 1.4 SDK Architecture (bonarjs-sdk)

Clean Architecture with:
- **core/entities**: `DynamicTable`, `User`, `Evento` (Zod schemas)
- **core/interfaces**: `IDynamicTableRepository`, `IAuthRepository`, etc.
- **infrastructure**: Firebase implementations (`DynamicTableRepository`, `AuthRepository`)
- **presentation/providers**: React context providers (Firebase, Auth, AppCheck)
- **hooks**: `useDynamicTable`, `useBonarJsAuth`, `useFirebaseImage`, etc.
- **PublicDataCacheService**: Firebase Storage JSON cache for public tables (agenda, metadata)

### 1.5 Deploy Pipeline (Current — Manual)

```
1. Developer edits app in src/apps/{tenant}/
2. next build → SSG export to sites/{tenant}/
3. firebase deploy --only hosting:{firebase-site-name}
4. Firebase Hosting serves static files
```

---

## 2. Beddel CMS Vision

### 2.1 Core Idea

Transform the manual microsaas into an **AI-first, workflow-driven CMS platform** where:

1. **Tenant provisioning** is a Beddel workflow (create Firestore customer, scaffold app, configure DNS)
2. **Content management** uses Beddel primitives (LLM-assisted content, guardrails, approval gates)
3. **Deployment** is a Beddel workflow (build SSG, deploy to hosting, health check)
4. **Billing** is tracked via Beddel's budget enforcer + tier router

### 2.2 What Beddel Brings to the Table

| Beddel Primitive | CMS Use Case |
|------------------|-------------|
| `llm` | Content generation, SEO optimization, translation |
| `chat` | Interactive content editing assistant |
| `output-generator` | Template rendering (email templates, page scaffolds) |
| `call-agent` | Delegate to specialized agents (SEO agent, deploy agent) |
| `guardrail` | Content moderation, brand compliance, PII detection |
| `tool` | Firebase Admin operations, DNS management, build triggers |
| `decide` | Route content approval (auto-approve vs human review) |

| Beddel Adapter | CMS Use Case |
|----------------|-------------|
| `tier-router` | Free/Pro/Enterprise tenant tiers with different LLM models |
| `budget-enforcer` | Per-tenant token/cost limits |
| `approval-gate` | Human-in-the-loop for content publish |
| `state-store` | Persist tenant workflow state (draft → review → published) |
| `memory-provider` | Episodic memory for content history per tenant |
| `knowledge-provider` | Brand guidelines, style guides per tenant |
| `pii-tokenizer` | Sanitize user-submitted content |
| `hooks` | Lifecycle events (on-publish, on-deploy, on-billing-event) |

| Beddel Kit | CMS Use Case |
|------------|-------------|
| `tools-http-kit` | API calls to Firebase, Postmark, Stripe |
| `tools-shell-kit` | Run `next build`, `firebase deploy` |
| `tools-file-kit` | Read/write tenant config files, .env generation |
| `serve-fastapi-kit` | Expose CMS management API |
| `observability-otel-kit` | Trace tenant operations, deploy latency |

### 2.3 Proposed Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Beddel CMS Platform                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Tenant       │  │  Content      │  │  Deploy       │  │
│  │  Provisioning │  │  Management   │  │  Pipeline     │  │
│  │  Workflow     │  │  Workflows    │  │  Workflow     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │          │
│  ┌──────┴──────────────────┴──────────────────┴───────┐ │
│  │              Beddel Workflow Engine                  │ │
│  │  (primitives, adapters, kits, strategies)           │ │
│  └──────┬──────────────────┬──────────────────┬───────┘ │
│         │                  │                  │          │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐  │
│  │  bonarjs-sdk  │  │  bonar-cms   │  │  Firebase     │  │
│  │  (adapted)    │  │  -api        │  │  Hosting      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Billing Layer (Stripe via tools-http-kit)        │   │
│  │  tier-router → budget-enforcer → usage tracking   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Concrete Workflows

### 3.1 Tenant Provisioning Workflow

```yaml
id: tenant_provision
steps:
  - id: validate_input
    primitive: guardrail
    # Validate tenant name, domain, plan tier

  - id: create_customer
    primitive: tool
    # Firebase Admin: create customers/{token} doc

  - id: scaffold_app
    primitive: tool
    # Copy casasavana template, replace .env, branding

  - id: configure_dns
    primitive: tool
    # Cloudflare/Firebase custom domain setup

  - id: initial_build
    primitive: tool
    # next build + firebase deploy

  - id: notify_owner
    primitive: output-generator
    # Welcome email via Postmark
```

### 3.2 Content Management Workflow

```yaml
id: content_manage
steps:
  - id: draft_content
    primitive: llm
    # AI-assisted content creation with brand context

  - id: moderate
    primitive: guardrail
    # PII check, brand compliance, content policy

  - id: approve
    primitive: decide
    # Auto-approve or route to human (HOTL)

  - id: publish
    primitive: tool
    # setItem via bonar-cms-api + cache refresh

  - id: rebuild_site
    primitive: call-agent
    # Trigger deploy pipeline if SSG content changed
```

### 3.3 Deploy Pipeline Workflow

```yaml
id: deploy_pipeline
steps:
  - id: build_ssg
    primitive: tool
    # shell: next build (output: export)

  - id: deploy_hosting
    primitive: tool
    # shell: firebase deploy --only hosting:{site}

  - id: health_check
    primitive: tool
    # http: GET https://{domain}/ → expect 200

  - id: notify
    primitive: output-generator
    # Deploy report (build time, pages, status)
```

### 3.4 Billing Workflow

```yaml
id: billing_cycle
steps:
  - id: collect_usage
    primitive: tool
    # Query Firestore for tenant API calls, storage, builds

  - id: calculate_invoice
    primitive: llm
    # Generate invoice line items based on tier + usage

  - id: charge
    primitive: tool
    # Stripe: create invoice + charge

  - id: enforce_limits
    primitive: decide
    # Downgrade/suspend if payment fails
```

---

## 4. Migration Strategy

### Phase 1: Wrap (No Breaking Changes)
- Create Beddel `tool` primitives that call the existing bonar-cms-api endpoints
- Create a `tenant-provision` workflow that automates what you do manually today
- Create a `deploy` workflow that wraps `next build` + `firebase deploy`
- **Zero changes** to existing frontend or backend code

### Phase 2: Enhance (AI Layer)
- Add `llm` + `guardrail` steps to content workflows
- Add `knowledge-provider` for per-tenant brand guidelines
- Add `memory-provider` for content history
- Add `tier-router` for Free/Pro/Enterprise model routing

### Phase 3: Monetize (Billing)
- Integrate Stripe via `tools-http-kit`
- Add `budget-enforcer` per tenant
- Build self-service tenant onboarding (provision + billing in one workflow)

### Phase 4: Decouple (SDK Independence)
- Extract bonarjs-sdk into a standalone npm package
- Replace Firebase-specific infra with adapter pattern (support Supabase, etc.)
- The SDK becomes a "Beddel CMS Kit" installable in any Next.js project

---

## 5. Memory Strategy for the Discovery Assistant

### Recommended: File-Based Memory (Simplest)

For the discovery/planning assistant that helps iterate on this design:

| Option | Mechanism | Pros | Cons |
|--------|-----------|------|------|
| **File memory** (RECOMMENDED) | `memory.json` in this folder | Zero setup, survives restarts, git-trackable | Manual, no semantic search |
| Beddel state-store | `state_store` adapter | Structured, typed | Requires running Beddel |
| Beddel memory-provider | Episodic memory adapter | Semantic search, timestamps | Requires vector DB setup |
| Neon QMD | PostgreSQL via MCP | Rich queries, shared with architect | Requires Neon connection |

**Decision**: Use `memory.json` in this folder. It's a simple JSON file that the
assistant workflow reads at start and writes at end. Each entry has a timestamp,
topic, decisions made, and open questions. This is the lowest-friction option
that works immediately.

---

## 6. Open Questions

1. Should the CMS API stay as Next.js API routes or migrate to FastAPI (via Beddel's serve-fastapi-kit)?
2. Should tenant apps stay as separate Next.js apps or become a single app with dynamic routing?
3. Firebase Hosting vs Cloudflare Pages vs Vercel for static deploy?
4. Stripe billing model: per-tenant flat fee, usage-based, or hybrid?
5. Should the bonarjs-sdk be published to npm as `@beddel/cms-sdk`?
6. How to handle existing Casa Savana data during migration?
