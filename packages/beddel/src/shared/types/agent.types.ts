/**
 * Shared Agent Types - Safe for client and server
 * These types contain no sensitive data and can be used in both environments
 */

/**
 * Agent metadata - safe for client display
 */
export interface AgentMetadata {
  id: string;
  name: string;
  description: string;
  category: string;
  route: string;
  tags?: string[];
}

/**
 * Generic agent response wrapper
 */
export interface AgentResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  timestamp?: string;
}

/**
 * Execution step tracking for workflow visualization
 */
export interface ExecutionStep {
  agent: string;
  action: string;
  status: 'running' | 'success' | 'error';
  startTime: number;
  endTime?: number;
  duration?: number;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  error?: string;
  description?: string;
  phase?: 'orchestration' | 'vectorization' | 'storage' | 'retrieval' | 'ingestion' | 'generation';
}

/**
 * Workflow step types supported by the runtime
 * Includes both English (preferred) and legacy (Portuguese) names
 */
export type WorkflowStepType =
  // English step types (preferred)
  | 'joke'
  | 'translation'
  | 'image'
  | 'vectorize'
  | 'mcp-tool'
  | 'chromadb'
  | 'gitmcp'
  | 'rag'
  | 'chat'
  | 'output-generator'
  | 'builtin-agent'
  | 'custom-action'
  // Legacy step types (backward compatibility)
  | 'genkit-joke'
  | 'genkit-translation'
  | 'genkit-image'
  | 'gemini-vectorize';

/**
 * Agent categories for organization
 */
export type AgentCategory =
  | 'utility'
  | 'translation'
  | 'image'
  | 'mcp'
  | 'vectorization'
  | 'storage'
  | 'retrieval'
  | 'orchestration';
