# Port Interface Contracts

Language-agnostic specifications for the Beddel hexagonal architecture port interfaces.

## Purpose

These JSON contract files define the method signatures, input/output types, and behavioral expectations for each port interface in the Beddel domain core. They serve as the canonical reference for implementing ports in any language SDK.

## Source of Truth

The Python Protocol classes in `src/beddel-py/src/beddel/domain/ports.py` are the reference implementation. These contract files are derived from those classes and kept in sync manually. When a port changes in `ports.py`, the corresponding contract JSON must be updated.

## Contract Format

Each JSON file follows this structure:

```json
{
  "name": "IPortName",
  "description": "What this port does",
  "methods": [
    {
      "name": "method_name",
      "params": [
        { "name": "param_name", "type": "string", "required": true }
      ],
      "return_type": "void",
      "async": true,
      "description": "What this method does"
    }
  ],
  "properties": [
    {
      "name": "prop_name",
      "type": "float",
      "readonly": true,
      "description": "What this property represents"
    }
  ],
  "behavioral_expectations": [
    "Invariant or constraint that all implementations must satisfy"
  ]
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Interface name (e.g. `IAgentAdapter`) |
| `description` | string | What the port does and when it is used |
| `methods` | array | Method signatures with params, return type, and async flag |
| `properties` | array | Read-only properties (optional, used by `IBudgetEnforcer`) |
| `generic_parameters` | array | Generic type parameters (optional, used by `ITracer`) |
| `behavioral_expectations` | array | Invariants and constraints for all implementations |

### Type System

Contracts use language-agnostic type names:

| Contract Type | Python | TypeScript |
|---------------|--------|------------|
| `string` | `str` | `string` |
| `integer` | `int` | `number` |
| `float` | `float` | `number` |
| `boolean` | `bool` | `boolean` |
| `dict` | `dict[str, Any]` | `Record<string, any>` |
| `list<T>` | `list[T]` | `T[]` |
| `any` | `Any` | `any` |
| `void` | `None` | `void` |
| `null` | `None` | `null` |
| `Optional<T>` | `T \| None` | `T \| null` |
| `AsyncGenerator<T, null>` | `AsyncGenerator[T, None]` | `AsyncGenerator<T>` |

### Subtyping Model

Each contract specifies its subtyping model in `behavioral_expectations`:

- **Structural (Protocol)**: `IAgentAdapter`, `IBudgetEnforcer`, `ICircuitBreaker`, `IEventStore`, `IMCPClient` — any object with matching method signatures satisfies the contract. In TypeScript, use `interface`.
- **Nominal (ABC)**: `ILLMProvider`, `ITracer` — implementations must explicitly subclass/extend the base. In TypeScript, use `abstract class`.

## Contracts

| File | Port | Subtyping | Methods |
|------|------|-----------|---------|
| `IAgentAdapter.json` | Agent backend adapter | Protocol | `execute`, `stream` |
| `IBudgetEnforcer.json` | Per-workflow budget | Protocol | `track_usage`, `check_budget`, `get_remaining` + 4 properties |
| `ICircuitBreaker.json` | Provider fault tolerance | Protocol | `record_failure`, `record_success`, `is_open`, `state` |
| `IContextReducer.json` | Context reduction strategy | Protocol | `reduce` |
| `IEventStore.json` | Durable event store | Protocol | `append`, `load`, `truncate` |
| `IExecutionStrategy.json` | Workflow execution strategy | Protocol | `execute` |
| `IHookManager.json` | Hook management (extends ILifecycleHook) | Class | `add_hook`, `remove_hook` + 10 lifecycle callbacks |
| `ILifecycleHook.json` | Workflow lifecycle hooks | Class | `on_workflow_start`, `on_workflow_end`, `on_step_start`, `on_step_end`, `on_error`, `on_retry`, `on_decision`, `on_budget_threshold`, `on_approval_requested`, `on_approval_received` |
| `ILLMProvider.json` | LLM provider adapter | ABC | `complete`, `stream` |
| `IMCPClient.json` | MCP server client | Protocol | `connect`, `list_tools`, `call_tool`, `disconnect` |
| `IPrimitive.json` | Workflow primitive | ABC | `execute` |
| `ITierRouter.json` | Model tier routing | Protocol | `route` |
| `ITracer.json` | Observability tracing | ABC + Generic | `start_span`, `end_span` |

## Implementing in Another Language

1. Read the contract JSON for the port you need to implement.
2. Create an interface/abstract class matching the `methods` and `properties`.
3. Map contract types to your language using the type table above.
4. Mark methods with `"async": true` as async/coroutine/promise-returning.
5. Implement all `behavioral_expectations` as invariants in your code.
6. For Protocol-based ports, structural typing is sufficient (no inheritance needed).
7. For ABC-based ports, explicit subclassing/extension is required.

## Example: TypeScript Implementation

Given `ICircuitBreaker.json`, a TypeScript implementation would be:

```typescript
interface ICircuitBreaker {
  recordFailure(provider: string): void;
  recordSuccess(provider: string): void;
  isOpen(provider: string): boolean;
  state(provider: string): string;
}
```

Given `ITracer.json` (ABC + Generic), a TypeScript implementation would be:

```typescript
abstract class ITracer<SpanT> {
  abstract startSpan(name: string, attributes?: Record<string, any>): SpanT | null;
  abstract endSpan(span: SpanT | null, attributes?: Record<string, any>): void;
}
```
