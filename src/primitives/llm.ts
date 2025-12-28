/**
 * Beddel Protocol - LLM Primitive
 * 
 * Primitive for workflow/API calls using standard message format.
 * NEVER streams - always returns complete result for workflow chaining.
 * Expects ModelMessage format (with 'content' property) directly.
 * 
 * Use this primitive when:
 * - Building multi-step workflows
 * - Result needs to be passed to next step
 * - Called from call-agent or other workflow steps
 * 
 * Server-only: Uses Vercel AI SDK Core.
 */

import { generateText, stepCountIs, type ModelMessage } from 'ai';
import type { StepConfig, ExecutionContext, PrimitiveHandler } from '../types';
import { resolveVariables } from '../core/variable-resolver';
import { createModel } from '../providers';
import { mapTools, type LlmConfig } from './llm-core';

/**
 * LLM Primitive Handler
 * 
 * Uses ModelMessage[] directly and returns complete result (no streaming).
 * Designed for workflow steps where result is needed for subsequent steps.
 * 
 * @param config - Step configuration from YAML
 * @param context - Execution context with input and variables
 * @returns Record with text and usage (never streams)
 */
export const llmPrimitive: PrimitiveHandler = async (
    config: StepConfig,
    context: ExecutionContext
): Promise<Record<string, unknown>> => {
    const llmConfig = config as LlmConfig;

    const model = createModel(llmConfig.provider || 'google', {
        model: llmConfig.model || 'gemini-1.5-flash',
    });

    // Resolve messages - already in ModelMessage format
    const messages = resolveVariables(llmConfig.messages, context) as ModelMessage[];

    const hasTools = llmConfig.tools && llmConfig.tools.length > 0;
    const tools = hasTools ? mapTools(llmConfig.tools!) : undefined;

    // Resolve system prompt (may contain $stepResult.* variables from previous steps)
    const system = resolveVariables(llmConfig.system, context) as string | undefined;

    const result = await generateText({
        model,
        messages,
        system,
        stopWhen: hasTools ? stepCountIs(5) : undefined,
        tools,
    });

    return {
        text: result.text,
        usage: result.usage,
    };
};
