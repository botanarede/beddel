/**
 * Beddel Protocol - Call Agent Primitive
 * 
 * Enables recursive workflow execution by calling other agents.
 * This primitive loads and executes another agent's workflow,
 * passing input and returning the result.
 * 
 * Server-only: Uses loadYaml and WorkflowExecutor.
 */

import type { StepConfig, ExecutionContext, PrimitiveHandler } from '../types';
import { loadYaml } from '../core/parser';
import { WorkflowExecutor } from '../core/workflow';
import { resolveVariables } from '../core/variable-resolver';
import { join } from 'path';
import { access } from 'fs/promises';
import { getBuiltinAgentsPath } from '../agents';

/**
 * Call Agent step configuration from YAML.
 */
interface CallAgentConfig extends StepConfig {
    /** Agent ID to call (e.g., 'text-generator') */
    agentId: string;
    /** Input to pass to the agent (can use $input.* or $stepResult.*) */
    input?: unknown;
    /** Path to user agents (defaults to 'src/agents') */
    agentsPath?: string;
}

/**
 * Check if a file exists at the given path
 */
async function fileExists(path: string): Promise<boolean> {
    try {
        await access(path);
        return true;
    } catch {
        return false;
    }
}

/**
 * Resolve agent path with fallback chain:
 * 1. User agents (agentsPath) - allows override
 * 2. Built-in agents (package) - fallback
 */
async function resolveAgentPath(
    agentId: string,
    agentsPath: string
): Promise<string> {
    // 1. First: try user agents
    const userPath = join(process.cwd(), agentsPath, `${agentId}.yaml`);
    if (await fileExists(userPath)) {
        return userPath;
    }

    // 2. Fallback: built-in agents from package
    const builtinPath = join(getBuiltinAgentsPath(), `${agentId}.yaml`);
    if (await fileExists(builtinPath)) {
        return builtinPath;
    }

    throw new Error(`[Beddel] Agent not found: ${agentId}`);
}

/**
 * Call Agent Primitive Handler
 * 
 * Loads another agent's YAML and executes its workflow.
 * 
 * IMPORTANT: If the called agent returns a Response (streaming),
 * this primitive will return that Response, causing the parent
 * workflow to also return immediately.
 * 
 * For multi-step workflows, ensure called agents use stream: false
 * so their results can be captured and passed to subsequent steps.
 * 
 * @param config - Step configuration (agentId, input)
 * @param context - Execution context with input and variables
 * @returns Result from called agent (Response or Record)
 */
export const callAgentPrimitive: PrimitiveHandler = async (
    config: StepConfig,
    context: ExecutionContext
): Promise<Response | Record<string, unknown>> => {
    const callConfig = config as CallAgentConfig;

    if (!callConfig.agentId) {
        throw new Error('[Beddel] call-agent requires agentId in config');
    }

    // Resolve the input to pass to the agent
    const agentInput = callConfig.input 
        ? resolveVariables(callConfig.input, context)
        : context.input;

    // Resolve agent path
    const agentsPath = callConfig.agentsPath || 'src/agents';
    const agentPath = await resolveAgentPath(callConfig.agentId, agentsPath);

    // Load and execute the agent
    const yaml = await loadYaml(agentPath);
    const executor = new WorkflowExecutor(yaml);
    const result = await executor.execute(agentInput);

    return result;
};
