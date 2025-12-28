/**
 * Beddel Protocol - Chat Primitive
 * 
 * DESIGN DECISION: This primitive ALWAYS streams. There is no `stream` config option.
 * Streaming behavior is semantically determined by primitive type:
 * - `chat` → Always streams (frontend UX)
 * - `llm` → Never streams (workflow chaining)
 * 
 * MESSAGE CONVERSION: Uses `convertToModelMessages()` because input comes from
 * `useChat` hook which sends `UIMessage[]` format. The AI SDK v6 `streamText`
 * expects `ModelMessage[]` format.
 * 
 * Use this primitive when:
 * - Input comes from useChat frontend hook
 * - You need streaming responses to the client
 * 
 * Server-only: Uses Vercel AI SDK Core.
 */

import {
    streamText,
    convertToModelMessages,
    stepCountIs,
    type UIMessage,
} from 'ai';
import type { StepConfig, ExecutionContext, PrimitiveHandler } from '../types';
import { resolveVariables } from '../core/variable-resolver';
import { createModel } from '../providers';
import { mapTools, callbackRegistry, type LlmConfig } from './llm-core';

/**
 * Chat Primitive Handler
 * 
 * Converts UIMessage[] (from useChat) to ModelMessage[] and streams response.
 * Always uses streaming mode for responsive frontend UX.
 * 
 * @param config - Step configuration from YAML
 * @param context - Execution context with input and variables
 * @returns Response (always streaming)
 */
export const chatPrimitive: PrimitiveHandler = async (
    config: StepConfig,
    context: ExecutionContext
): Promise<Response> => {
    const llmConfig = config as LlmConfig;

    const model = createModel(llmConfig.provider || 'google', {
        model: llmConfig.model || 'gemini-1.5-flash',
    });

    // Resolve and convert UIMessage to ModelMessage
    const uiMessages = resolveVariables(llmConfig.messages, context) as UIMessage[];
    const messages = await convertToModelMessages(uiMessages);

    const hasTools = llmConfig.tools && llmConfig.tools.length > 0;
    const tools = hasTools ? mapTools(llmConfig.tools!) : undefined;

    // Resolve system prompt (may contain $stepResult.* variables from previous steps)
    const system = resolveVariables(llmConfig.system, context) as string | undefined;

    const result = streamText({
        model,
        messages,
        system,
        stopWhen: hasTools ? stepCountIs(5) : undefined,
        tools,
        onFinish: async ({ text, finishReason, usage, totalUsage, steps, response }) => {
            if (llmConfig.onFinish) {
                const callback = callbackRegistry[llmConfig.onFinish];
                if (callback) {
                    await callback({ text, finishReason, usage, totalUsage, steps, response });
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

    return result.toUIMessageStreamResponse();
};
