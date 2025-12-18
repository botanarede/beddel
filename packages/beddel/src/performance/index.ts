/**
 * Performance Module - Index
 * Exports all performance monitoring capabilities for the Beddel runtime
 */

export * from "./monitor";
export * from "./benchmark";
export * from "./autoscaling";

// Re-export key types for convenience
export type {
  PerformanceMonitor,
  PerformanceMetric,
  PerformanceSnapshot,
  Violation,
  Recommendation,
} from "./monitor";

export type { BenchmarkResult, BenchmarkSuite, TestCase } from "./benchmark";

export type {
  AutoscaleConfig,
  AutoscaleDecision,
  AutoscaleSystem,
} from "./autoscaling";

// Export individual instances
export { performanceMonitor } from "./monitor";
export { benchmarkSystem, initializeBenchmarks } from "./benchmark";
export {
  autoscaleSystem,
  initializeAutoscaling,
  getAutoscalingConfig,
} from "./autoscaling";
