/**
 * Beddel Protocol - Primitive Handler Registry
 * 
 * This registry maps step types to their handler implementations.
 * Following Expansion Pack Pattern from BMAD-METHOD™ for extensibility.
 * 
 * Server-only: Handlers may use Node.js APIs and external services.
 */

import type { PrimitiveHandler, StepConfig, ExecutionContext } from '../types';
import { chatPrimitive } from './chat';
import { llmPrimitive } from './llm';
import { outputPrimitive } from './output';
import { callAgentPrimitive } from './call-agent';

// Re-export from llm-core for consumer access
export { registerCallback, callbackRegistry } from './llm-core';
export { chatPrimitive } from './chat';
export { llmPrimitive } from './llm';
export { callAgentPrimitive } from './call-agent';

/**
 * Registry of primitive handlers keyed by step type.
 * 
 * Primitives:
 * - 'chat': Frontend chat interface (UIMessage with 'parts' → converts to ModelMessage)
 * - 'llm': Workflow/API calls (ModelMessage with 'content' → direct use)
 * - 'output-generator': Deterministic variable mapping
 * - 'call-agent': Sub-agent invocation
 */
export const handlerRegistry: Record<string, PrimitiveHandler> = {
    /**
     * Chat Primitive - Frontend chat interface.
     * Converts UIMessage (from useChat) to ModelMessage.
     * Use for: API routes serving useChat frontend hooks.
     */
    'chat': chatPrimitive,

    /**
     * LLM Primitive - Direct LLM calls for workflows.
     * Uses ModelMessage format directly without conversion.
     * Use for: Internal workflows, call-agent, API calls.
     */
    'llm': llmPrimitive,

    /**
     * Output Generator Primitive - Deterministic JSON transform.
     * Resolves variable references in templates.
     */
    'output-generator': outputPrimitive,

    /**
     * Call Agent Primitive - Sub-agent invocation.
     * Loads and executes another agent's workflow.
     */
    'call-agent': callAgentPrimitive,
};

/**
 * Register a custom primitive handler in the registry.
 * 
 * @param type - Step type identifier (e.g., 'my-custom-primitive')
 * @param handler - PrimitiveHandler function
 */
export function registerPrimitive(type: string, handler: PrimitiveHandler): void {
    if (handlerRegistry[type]) {
        console.warn(`[Beddel] Primitive '${type}' already registered, overwriting.`);
    }
    handlerRegistry[type] = handler;
}
