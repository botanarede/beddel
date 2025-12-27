/**
 * Beddel Protocol - LLM Core
 * 
 * Shared utilities for LLM primitives (chat and llm).
 * 
 * Server-only: Uses Vercel AI SDK Core.
 */

import { dynamicTool, type ToolSet } from 'ai';
import type { StepConfig } from '../types';
import { toolRegistry, type ToolImplementation } from '../tools';

/**
 * Callback function type for lifecycle hooks (onFinish, onError).
 */
export type CallbackFn = (payload: Record<string, unknown>) => void | Promise<void>;

/**
 * Registry for consumer-registered callbacks.
 */
export const callbackRegistry: Record<string, CallbackFn> = {};

/**
 * Register a callback function for lifecycle hooks.
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
export interface YamlToolDefinition {
    name: string;
    description?: string;
}

/**
 * LLM step configuration from YAML.
 */
export interface LlmConfig extends StepConfig {
    provider?: string;
    model?: string;
    system?: string;
    messages?: string | unknown[];
    tools?: YamlToolDefinition[];
    onFinish?: string;
    onError?: string;
}

/**
 * Maps YAML tool definitions to Vercel AI SDK tool objects.
 */
export function mapTools(toolDefinitions: YamlToolDefinition[]): ToolSet {
    const tools: ToolSet = {};

    for (const def of toolDefinitions) {
        const impl: ToolImplementation | undefined = toolRegistry[def.name];
        if (!impl) {
            console.warn(`[Beddel] Tool '${def.name}' not found in registry, skipping.`);
            continue;
        }

        tools[def.name] = dynamicTool({
            description: def.description || impl.description,
            inputSchema: impl.parameters,
            execute: async (args: unknown) => {
                return impl.execute(args as Record<string, unknown>);
            },
        });
    }

    return tools;
}
