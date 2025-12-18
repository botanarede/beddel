/**
 * Simple Isolated Runtime - Isolated VM v5 Implementation
 * Provides ultra-secure isolated execution environment with zero-trust architecture
 * Simplified version with core functionality
 */
import * as ivm from "isolated-vm";
import { runtimeConfig, securityProfiles, RuntimeConfig } from "../config";

export interface ExecutionResult<T = any> {
  success: boolean;
  result?: T;
  error?: string;
  executionTime: number;
  memoryUsed: number;
  timestamp: Date;
}

export interface ExecutionOptions {
  code: string;
  context?: Record<string, any>;
  securityProfile?: string;
  timeout?: number;
  memoryLimit?: number;
  tenantId?: string;
}

export class IsolatedRuntimeError extends Error {
  constructor(message: string, public readonly code: string) {
    super(message);
    this.name = "IsolatedRuntimeError";
  }
}

/**
 * Simple Isolated Runtime Manager
 * Provides basic isolated execution functionality
 */
export class SimpleIsolatedRuntimeManager {
  private metrics: Map<string, number[]> = new Map();

  constructor(private config: RuntimeConfig = runtimeConfig) {}

  /**
   * Execute code in isolated environment
   */
  public async execute<T = any>(
    options: ExecutionOptions
  ): Promise<ExecutionResult<T>> {
    const startTime = Date.now();

    try {
      // Validate input
      this.validateExecutionOptions(options);

      // Get security profile
      const profileName =
        options.securityProfile || this.config.defaultSecurityProfile;
      const securityProfile = securityProfiles[profileName];

      // Create isolated environment
      const result = await this.executeInIsolate<T>(options, securityProfile);

      const executionTime = Date.now() - startTime;
      result.executionTime = executionTime;

      this.updateMetrics("executionTime", executionTime);
      this.updateMetrics("successRate", result.success ? 1 : 0);

      return result;
    } catch (error) {
      const executionTime = Date.now() - startTime;

      return {
        success: false,
        error: error instanceof Error ? error.message : String(error),
        executionTime,
        memoryUsed: 0,
        timestamp: new Date(),
      };
    }
  }

  /**
   * Execute code in isolated context
   */
  private async executeInIsolate<T>(
    options: ExecutionOptions,
    securityProfile: any
  ): Promise<ExecutionResult<T>> {
    const startTime = Date.now();

    try {
      // Create isolate with memory limit
      const isolate = new ivm.Isolate({
        memoryLimit: securityProfile.memoryLimit,
      });

      // Create context
      const context = await isolate.createContext();

      try {
        // Setup execution
        const script = await isolate.compileScript(options.code);

        // Execute script
        const result = await script.run(context, {
          timeout: options.timeout || securityProfile.timeout,
        });

        // Get memory usage
        const memoryUsed = await this.getMemoryUsage(isolate);

        return {
          success: true,
          result: result as T,
          executionTime: Date.now() - startTime,
          memoryUsed,
          timestamp: new Date(),
        };
      } finally {
        // Always dispose isolate
        isolate.dispose();
      }
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : String(error),
        executionTime: Date.now() - startTime,
        memoryUsed: 0,
        timestamp: new Date(),
      };
    }
  }

  /**
   * Get memory usage for isolate
   */
  private async getMemoryUsage(isolate: ivm.Isolate): Promise<number> {
    try {
      const stats = await isolate.getHeapStatistics();
      return (stats.used_heap_size || 0) / (1024 * 1024); // MB
    } catch (error) {
      return 0;
    }
  }

  /**
   * Validate execution options
   */
  private validateExecutionOptions(options: ExecutionOptions): void {
    if (!options.code || typeof options.code !== "string") {
      throw new IsolatedRuntimeError(
        "Code must be a non-empty string",
        "INVALID_CODE"
      );
    }

    if (options.code.length > 1024 * 1024) {
      throw new IsolatedRuntimeError(
        "Code exceeds maximum size limit (1MB)",
        "CODE_TOO_LARGE"
      );
    }

    const memoryLimit = options.memoryLimit || this.config.memoryLimit;
    if (memoryLimit > 8) {
      throw new IsolatedRuntimeError(
        "Memory limit exceeds maximum allowed (8MB)",
        "MEMORY_LIMIT_EXCEEDED"
      );
    }
  }

  /**
   * Update metrics tracking
   */
  private updateMetrics(metric: string, value: number): void {
    if (!this.metrics.has(metric)) {
      this.metrics.set(metric, []);
    }

    const values = this.metrics.get(metric)!;
    values.push(value);

    // Keep only last 100 values
    if (values.length > 100) {
      values.shift();
    }
  }

  /**
   * Get current metrics
   */
  public getMetrics(): Record<string, number[]> {
    return Object.fromEntries(this.metrics);
  }
}

// Singleton instance
export const runtimeManager = new SimpleIsolatedRuntimeManager();
export default SimpleIsolatedRuntimeManager;
