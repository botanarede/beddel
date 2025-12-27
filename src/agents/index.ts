/**
 * Built-in Agents Registry
 * 
 * Lists all agents bundled with the beddel package.
 * These are available automatically without user configuration.
 */

import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

// Get the directory where built-in agents are located
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * List of built-in agent IDs available in the package
 */
export const BUILTIN_AGENTS = [
  'assistant',
  'assistant-bedrock', 
  'assistant-openrouter',
  'text-generator',
  'multi-step-assistant',
] as const;

export type BuiltinAgentId = typeof BUILTIN_AGENTS[number];

/**
 * Get the absolute path to the built-in agents directory
 */
export function getBuiltinAgentsPath(): string {
  return __dirname;
}

/**
 * Check if an agent ID is a built-in agent
 */
export function isBuiltinAgent(agentId: string): agentId is BuiltinAgentId {
  return BUILTIN_AGENTS.includes(agentId as BuiltinAgentId);
}

/**
 * Get the full path to a built-in agent YAML file
 */
export function getBuiltinAgentPath(agentId: BuiltinAgentId): string {
  return join(__dirname, `${agentId}.yaml`);
}
