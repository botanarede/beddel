/**
 * Beddel Protocol - LLM Primitive
 * 
 * Core primitive for AI text generation with dual-mode support:
 * - Stream Mode: Uses streamText → returns Response via toUIMessageStreamResponse()
 * - Block Mode: Uses generateText → returns JSON object { text, usage }
 * 
 * Supports tools via mapTools() which bridges YAML definitions to Vercel AI SDK tools.
 * Requires GEMINI_API_KEY environment variable.
 * 
 * Server-only: Uses Vercel AI SDK Core which requires Node.js.
 * 
 * AI SDK v6 Compatibility:
 * - Frontend (useChat) sends UIMessage[] with { parts: [...] } format
 * - Backend (streamText/generateText) expects ModelMessage[] with { content: ... }
 * - convertToModelMessages() bridges this gap automatically
 */

import {
    streamText,
    generateText,
    dynamicTool,
    stepCountIs,
    convertToModelMessages,
    type ModelMessage,
    type UIMessage,
    type ToolSet,
} from 'ai';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import type { StepConfig, ExecutionContext, PrimitiveHandler } from '../types';
import { toolRegistry, type ToolImplementation } from '../tools';
import { resolveVariables } from '../core/variable-resolver';

/**
 * Callback function type for lifecycle hooks (onFinish, onError).
 */
export type CallbackFn = (payload: Record<string, unknown>) => void | Promise<void>;

/**
 * Registry for consumer-registered callbacks.
 * Populated by the application using Beddel.
 */
export const callbackRegistry: Record<string, CallbackFn> = {};

/**
 * Register a callback function for lifecycle hooks.
 * 
 * @param name - Unique identifier for the callback
 * @param callback - Function to execute when hook is triggered
 * 
 * @example
 * registerCallback('persistConversation', async ({ text, usage }) => {
 *   await db.saveMessage(text, usage);
 * });
 */
export function registerCallback(name: string, callback: CallbackFn): void {
    if (callbackRegistry[name]) {
        console.warn(`[Beddel] Callback '${name}' already registered, overwriting.`);
    }
    callbackRegistry[name] = callback;
}



/**
 * Tool definition from YAML config.
 */
interface YamlToolDefinition {
    name: string;
    description?: string;
}

/**
 * LLM step configuration from YAML.
 */
interface LlmConfig extends StepConfig {
    model?: string;
    stream?: boolean;
    system?: string;
    messages?: string | ModelMessage[];
    tools?: YamlToolDefinition[];
    onFinish?: string;
    onError?: string;
}

/**
 * Maps YAML tool definitions to Vercel AI SDK tool objects.
 * 
 * YAML defines intent (name, optional description override).
 * Registry provides implementation (parameters, execute).
 * Uses dynamicTool for flexible type support with unknown input/output types.
 * 
 * @param toolDefinitions - Array of tool definitions from YAML config
 * @returns Record of Vercel AI SDK tools (ToolSet)
 */
function mapTools(toolDefinitions: YamlToolDefinition[]): ToolSet {
    const tools: ToolSet = {};

    for (const def of toolDefinitions) {
        const impl: ToolImplementation | undefined = toolRegistry[def.name];
        if (!impl) {
            console.warn(`[Beddel] Tool '${def.name}' not found in registry, skipping.`);
            continue;
        }

        // Use dynamicTool for flexible type handling with registry-defined tools
        tools[def.name] = dynamicTool({
            description: def.description || impl.description, // YAML can override
            inputSchema: impl.parameters,
            execute: async (args: unknown) => {
                return impl.execute(args as Record<string, unknown>);
            },
        });
    }

    return tools;
}

/**
 * LLM Primitive Handler
 * 
 * Dual-mode support via config.stream:
 * - stream: true → Uses streamText → returns result.toUIMessageStreamResponse()
 * - stream: false → Uses generateText → returns { text, usage }
 * 
 * When tools are present, stopWhen is set to stepCountIs(5) to enable tool loops.
 * 
 * AI SDK v6: Converts UIMessage[] (from useChat) to ModelMessage[] automatically.
 * 
 * @param config - Step configuration from YAML (model, stream, system, messages, tools)
 * @param context - Execution context with input and variables
 * @returns Response (streaming) or Record (blocking mode)
 */
export const llmPrimitive: PrimitiveHandler = async (
    config: StepConfig,
    context: ExecutionContext
): Promise<Response | Record<string, unknown>> => {
    const llmConfig = config as LlmConfig;

    // Initialize Google Generative AI provider
    const google = createGoogleGenerativeAI({
        apiKey: process.env.GEMINI_API_KEY,
    });
    const model = google(llmConfig.model || 'gemini-1.5-flash');

    // Resolve messages from context (e.g., $input.messages)
    // AI SDK v6: Frontend sends UIMessage[], we convert to ModelMessage[]
    const rawMessages = resolveVariables(llmConfig.messages, context) as UIMessage[];
    const messages = await convertToModelMessages(rawMessages);

    // Map YAML tools to Vercel AI SDK format
    const hasTools = llmConfig.tools && llmConfig.tools.length > 0;
    const tools = hasTools ? mapTools(llmConfig.tools!) : undefined;

    if (llmConfig.stream) {
        // STREAMING MODE: Returns HTTP response directly
        const result = streamText({
            model,
            messages,
            system: llmConfig.system,
            // Enable tool loop if tools exist (default is stepCountIs(1))
            stopWhen: hasTools ? stepCountIs(5) : undefined,
            tools,
            // Lifecycle hooks (AI SDK v6 signature)
            onFinish: async ({ text, finishReason, usage, totalUsage, steps, response }) => {
                if (llmConfig.onFinish) {
                    const callback = callbackRegistry[llmConfig.onFinish];
                    if (callback) {
                        await callback({
                            text,
                            finishReason,
                            usage,
                            totalUsage,
                            steps,
                            response,
                        });
                    }
                }
            },
            onError: ({ error }) => {
                if (llmConfig.onError) {
                    const callback = callbackRegistry[llmConfig.onError];
                    if (callback) {
                        callback({ error });
                    }
                }
                console.error('[Beddel] Stream error:', error);
            },
        });

        // Return streaming response - Executor will detect this and return to client immediately
        // AI SDK v6: toUIMessageStreamResponse() for useChat compatibility
        return result.toUIMessageStreamResponse();
    } else {
        // BLOCKING MODE: Returns data for next workflow step
        const result = await generateText({
            model,
            messages,
            system: llmConfig.system,
            // Enable tool loop if tools exist (default is stepCountIs(1))
            stopWhen: hasTools ? stepCountIs(5) : undefined,
            tools,
        });

        return {
            text: result.text,
            usage: result.usage,
        };
    }
};
