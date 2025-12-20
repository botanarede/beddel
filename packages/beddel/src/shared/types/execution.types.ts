/**
 * Execution Types - Shared between client and server
 * Used for tracking and displaying execution progress
 */

/**
 * Execution result from a workflow step
 */
export interface ExecutionResult<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  duration?: number;
  metadata?: Record<string, unknown>;
}

/**
 * Workflow execution status
 */
export type ExecutionStatus = 'pending' | 'running' | 'success' | 'error' | 'cancelled';

/**
 * Workflow execution summary
 */
export interface ExecutionSummary {
  agentId: string;
  status: ExecutionStatus;
  startTime: number;
  endTime?: number;
  totalDuration?: number;
  stepsCompleted: number;
  totalSteps: number;
  error?: string;
}

/**
 * Execution log entry
 */
export interface ExecutionLogEntry {
  timestamp: number;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  step?: string;
  metadata?: Record<string, unknown>;
}
