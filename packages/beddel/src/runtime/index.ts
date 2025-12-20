/**
 * Runtime Module - Server-only exports
 *
 * This module provides the declarative agent runtime and workflow execution.
 * All exports in this module are server-only.
 */

// Main runtime exports
export { DeclarativeAgentInterpreter, declarativeInterpreter } from './declarativeAgentRuntime';
export type { YamlAgentDefinition, YamlAgentInterpreterOptions, YamlExecutionResult } from './declarativeAgentRuntime';

// Workflow executor exports
export {
  executeWorkflowStep,
  getAvailableStepTypes,
  isStepTypeSupported,
  // Individual handlers for direct use
  executeJokeHandler,
  executeTranslationHandler,
  executeImageHandler,
  executeMcpToolHandler,
  executeVectorizeHandler,
  executeChromaDBHandler,
  executeGitMcpHandler,
  executeRagHandler,
  executeChatHandler,
} from './workflowExecutor';

// Schema compiler exports
export { DeclarativeSchemaCompiler, DeclarativeSchemaValidationError } from './schemaCompiler';
export type { DeclarativeSchemaPhase } from './schemaCompiler';
