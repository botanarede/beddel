# @beddel/observability-budget

Budget enforcement adapters with Langfuse integration for the Beddel TypeScript SDK.

## Overview

Provides two `IBudgetEnforcer` implementations that extend the core
`InMemoryBudgetEnforcer` with external integrations:

- **LangfuseBudgetEnforcer** — enriches cost tracking with Langfuse trace data.
- **PersistentBudgetEnforcer** — persists budget state across workflow runs.

## Install

```bash
pnpm add @beddel/observability-budget
```

## Usage

```typescript
import { LangfuseBudgetEnforcer } from '@beddel/observability-budget';

const enforcer = new LangfuseBudgetEnforcer({
  maxCostUsd: 10.0,
  degradationThreshold: 0.8,
  degradationModel: 'gpt-4o-mini',
});

enforcer.trackUsage('step-1', { totalCost: 0.05 });
const { status, remaining } = enforcer.checkBudget();
```

## kit.yaml

```yaml
name: observability-budget-kit
version: "0.1.0"
adapters:
  - port: IBudgetEnforcer
    implementation: LangfuseBudgetEnforcer
  - port: IBudgetEnforcer
    implementation: PersistentBudgetEnforcer
```
