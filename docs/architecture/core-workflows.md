# Core Workflows

## Consumer Setup Flow

Setting up Beddel in a Next.js application:

### 1. Install Package

```bash
npm install beddel
# or
pnpm add beddel
```

### 2. Create API Route

```typescript
// app/api/beddel/chat/route.ts
import { createBeddelHandler } from 'beddel/server';

export const POST = createBeddelHandler({
  agentsPath: 'src/agents'  // Optional, default: 'src/agents'
});
```

### 3. Create YAML Agent

```yaml
# src/agents/assistant.yaml
metadata:
  name: "Streaming Assistant"
  version: "1.0.0"

workflow:
  - id: "chat-interaction"
    type: "llm"
    config:
      provider: "google"          # Optional: 'google' (default) or 'bedrock'
      model: "gemini-2.0-flash-exp"
      stream: true
      system: "You are a helpful and concise assistant."
      messages: "$input.messages"
```

**Using Amazon Bedrock:**

```yaml
# src/agents/bedrock-assistant.yaml
metadata:
  name: "Bedrock Assistant"
  version: "1.0.0"

workflow:
  - id: "chat-interaction"
    type: "llm"
    config:
      provider: "bedrock"
      model: "anthropic.claude-3-haiku-20240307-v1:0"
      stream: true
      system: "You are a helpful assistant."
      messages: "$input.messages"
```

### 4. (Optional) Register Custom Extensions

```typescript
// app/api/beddel/chat/route.ts
import { createBeddelHandler } from 'beddel/server';
import { registerTool, registerCallback, registerProvider } from 'beddel';
import { z } from 'zod';
import { createOpenAI } from '@ai-sdk/openai';

// Register custom LLM provider
registerProvider('openai', {
  createModel: (config) => {
    const openai = createOpenAI({ apiKey: process.env.OPENAI_API_KEY });
    return openai(config.model || 'gpt-4');
  },
});

// Register custom tool
registerTool('myTool', {
  description: 'My custom tool',
  parameters: z.object({ input: z.string() }),
  execute: async ({ input }) => ({ result: input.toUpperCase() }),
});

// Register lifecycle callback
registerCallback('saveConversation', async ({ text, usage }) => {
  await db.saveMessage(text, usage);
});

export const POST = createBeddelHandler();
```

---

## YAML Structure

YAML files define a **Pipeline** of sequential steps:

```yaml
metadata:
  name: "Agent Name"
  version: "1.0.0"

workflow:
  - id: "step-1"
    type: "llm"           # Primitive type
    config:
      provider: "google"  # Optional: 'google' (default) or 'bedrock' or custom
      model: "gemini-2.0-flash-exp"
      stream: true        # true = streaming, false = blocking
      system: "System prompt"
      messages: "$input.messages"
      tools:              # Optional: tools for function calling
        - name: "calculator"
      onFinish: "callbackName"   # Optional: lifecycle hook
    result: "stepOutput"  # Optional: variable name for result

  - id: "step-2"
    type: "output-generator"
    config:
      template:
        status: "completed"
        tokens: "$stepOutput.usage"
```

### Variable Resolution Patterns

| Pattern | Description | Example |
|---------|-------------|---------|
| `$input.*` | Access request input data | `$input.messages` |
| `$stepResult.varName.*` | Access step result by result name | `$stepResult.llmOutput.text` |
| `$varName.*` | Legacy: direct variable access | `$llmOutput.usage` |

---

## Streaming Chat Flow

```mermaid
sequenceDiagram
    participant Client as Client (useChat)
    participant API as POST /api/beddel/chat
    participant Loader as YAML Loader
    participant Executor as WorkflowExecutor
    participant LLM as llmPrimitive
    participant SDK as Vercel AI SDK

    Client->>API: { agentId, messages: UIMessage[] }
    API->>Loader: loadYaml(src/agents/{agentId}.yaml)
    Loader-->>API: ParsedYaml
    API->>Executor: new WorkflowExecutor(yaml)
    API->>Executor: execute({ messages })
    
    loop For each step in workflow
        Executor->>Executor: Get handler from registry
        Executor->>LLM: handler(config, context)
        
        alt stream: true
            LLM->>LLM: convertToModelMessages(UIMessage[])
            LLM->>SDK: streamText({ messages: ModelMessage[] })
            SDK-->>LLM: StreamResult
            LLM->>LLM: result.toUIMessageStreamResponse()
            LLM-->>Executor: Response (stream)
            Note over Executor: Break loop immediately
            Executor-->>API: Response
            API-->>Client: UI Message Stream
        else stream: false
            LLM->>LLM: convertToModelMessages(UIMessage[])
            LLM->>SDK: generateText({ messages: ModelMessage[] })
            SDK-->>LLM: TextResult
            LLM-->>Executor: { text, usage }
            Executor->>Executor: Store in context.variables
        end
    end
```

### AI SDK v6 Message Format

The LLM primitive handles message format conversion automatically:

| Source | Format | Example |
|--------|--------|---------|
| Frontend (`useChat`) | `UIMessage[]` | `{ role: "user", parts: [{ type: "text", text: "Hello" }] }` |
| Backend (`streamText`) | `ModelMessage[]` | `{ role: "user", content: "Hello" }` |

- `convertToModelMessages()` converts `UIMessage[]` → `ModelMessage[]`
- `toUIMessageStreamResponse()` returns the correct stream format for `useChat`

## Tool Loop Flow

When tools are defined, the LLM may invoke them in a multi-step loop:

```mermaid
sequenceDiagram
    participant LLM as llmPrimitive
    participant SDK as streamText
    participant Tools as Tool Registry
    participant Calc as calculator

    LLM->>SDK: streamText({ stopWhen: stepCountIs(5), tools })
    
    loop Until stopWhen condition met
        SDK->>SDK: LLM generates response
        
        alt Tool call requested
            SDK->>Tools: Lookup tool by name
            Tools->>Calc: execute({ expression })
            Calc-->>SDK: { result }
            SDK->>SDK: Continue with tool result
        else No tool call
            Note over SDK: Break loop
        end
    end
    
    SDK-->>LLM: Final StreamResult
```

## Variable Resolution Flow

How variables like `$input.messages` are resolved:

```mermaid
sequenceDiagram
    participant Config as Step Config
    participant Resolver as Variable Resolver
    participant Context as ExecutionContext

    Config->>Resolver: "$input.messages"
    Resolver->>Context: context.input.messages
    Context-->>Resolver: Message[]
    Resolver-->>Config: Resolved value
    
    Config->>Resolver: "$llmOutput.text"
    Resolver->>Context: context.variables.get("llmOutput").text
    Context-->>Resolver: "Hello!"
    Resolver-->>Config: Resolved value
```

## onFinish Lifecycle Hook Flow

How `onFinish` executes after streaming completes (Option B: direct callbacks):

```mermaid
sequenceDiagram
    participant LLM as llmPrimitive
    participant SDK as streamText
    participant Registry as callbackRegistry
    participant Callback as persistConversation

    LLM->>SDK: streamText({ onFinish, onError })
    SDK->>SDK: Stream tokens to client
    
    Note over SDK: Stream completes
    
    SDK->>LLM: onFinish({ text, usage, totalUsage, steps })
    LLM->>LLM: config.onFinish = "persistConversation"
    LLM->>Registry: callbackRegistry["persistConversation"]
    Registry-->>LLM: callback function
    LLM->>Callback: callback({ text, usage, totalUsage, steps })
    Callback->>Callback: Save to database
    Callback-->>LLM: Done
    
    Note over LLM: Response already sent to client
```
