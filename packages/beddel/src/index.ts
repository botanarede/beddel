/**
 * Beddel - Parser YAML seguro com FAILSAFE_SCHEMA e Runtime Isolado
 *
 * Open source package para parsing YAML com foco máximo em segurança
 * Implementa FAILSAFE_SCHEMA, validações rigorosas, runtime isolado e multi-tenant isolation
 */

// YAML Parser exports
export {
  SecureYamlParser,
  createSecureYamlParser,
  parseSecureYaml,
} from "./parser/secure-yaml-parser";

// Runtime Isolado exports
export {
  IsolatedRuntimeManager,
  runtimeManager,
} from "./runtime/isolatedRuntime";
export type {
  ExecutionOptions,
  ExecutionResult,
  RuntimeContext,
} from "./runtime/isolatedRuntime";

// Simple Runtime exports
export {
  SimpleIsolatedRuntimeManager,
  runtimeManager as simpleRuntimeManager,
  IsolatedRuntimeError as SimpleRuntimeError,
} from "./runtime/simpleRuntime";
export type {
  ExecutionOptions as SimpleExecutionOptions,
  ExecutionResult as SimpleExecutionResult,
} from "./runtime/simpleRuntime";

// Declarative runtime exports
export {
  DeclarativeAgentInterpreter,
  declarativeInterpreter,
} from "./runtime/declarativeAgentRuntime";
export type {
  YamlAgentDefinition,
  YamlAgentInterpreterOptions,
  YamlExecutionResult,
} from "./runtime/declarativeAgentRuntime";
export {
  DeclarativeSchemaCompiler,
  DeclarativeSchemaValidationError,
  SchemaCompilationError,
} from "./runtime/schemaCompiler";

// Agent registry exports
export { AgentRegistry, agentRegistry } from "./agents/registry";
export type { AgentRegistration } from "./agents/registry";

// Configuration exports
export {
  runtimeConfig,
  securityProfiles,
  performanceTargets,
  auditConfig,
} from "./config";
export type {
  RuntimeConfig,
  SecurityProfile,
  PerformanceTarget,
  AuditConfig,
} from "./config";

// Error exports
export {
  YAMLBaseError,
  YAMLParseError,
  YAMLSecurityError,
  YAMLPerformanceError,
} from "./errors";

// Security exports
export { SecurityScanner } from "./security/scanner";
export { SecurityScore } from "./security/score";
export {
  SecurityManager,
  SecurityMonitor,
  securityMonitor,
  SecurityDashboard,
  securityDashboard,
  ThreatDetectionEngine,
  AnomalyDetector,
  ThreatMLModel,
} from "./security";
export type {
  AlertLevel,
  SecurityEvent,
  ThreatAnalysis,
  DashboardConfig,
  SecurityMetric,
} from "./security";
export { AuditService } from "./runtime/audit";

// Performance exports
export { PerformanceMonitor } from "./performance/monitor";
export { default as AutoScaler } from "./performance/autoscaling";

// Multi-Tenant Firebase exports
export { MultiTenantFirebaseManager } from "./firebase/tenantManager";
export type {
  TenantConfig,
  TenantIsolationResult,
} from "./firebase/tenantManager";

// Compliance exports
export { GDPRCompliance } from "./compliance/gdprEngine";
export { LGPDCompliance } from "./compliance/lgpdEngine";
export type { GDPRConfig, GDPRComplianceResult } from "./compliance/gdprEngine";
export type { LGPDConfig, LGPDComplianceResult } from "./compliance/lgpdEngine";

// Integration: Secure YAML Parser with Isolated Runtime
export { SecureYamlRuntime } from "./integration/secure-yaml-runtime";

// Shared types
export type { ExecutionContext } from "./types/executionContext";

// Shared agent types (client-safe)
export type {
  AgentMetadata,
  AgentResponse,
  ExecutionStep,
  WorkflowStepType,
  AgentCategory,
} from "./shared/types/agent.types";

// Chat agent exports (client-safe)
export type {
  ChatHandlerParams,
  ChatHandlerResult,
  ChatMetadata,
} from "./agents/chat/chat.types";
export { chatMetadata } from "./agents/chat";

// RAG types (client-safe)
export type { ConversationMessage } from "./agents/rag/rag.types";

// Server/runtime exports
export * as Server from "./server";
