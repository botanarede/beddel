import { RuntimeConfig } from "../config";
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
export declare class IsolatedRuntimeError extends Error {
    readonly code: string;
    constructor(message: string, code: string);
}
/**
 * Simple Isolated Runtime Manager
 * Provides basic isolated execution functionality
 */
export declare class SimpleIsolatedRuntimeManager {
    private config;
    private metrics;
    constructor(config?: RuntimeConfig);
    /**
     * Execute code in isolated environment
     */
    execute<T = any>(options: ExecutionOptions): Promise<ExecutionResult<T>>;
    /**
     * Execute code in isolated context
     */
    private executeInIsolate;
    /**
     * Get memory usage for isolate
     */
    private getMemoryUsage;
    /**
     * Validate execution options
     */
    private validateExecutionOptions;
    /**
     * Update metrics tracking
     */
    private updateMetrics;
    /**
     * Get current metrics
     */
    getMetrics(): Record<string, number[]>;
}
export declare const runtimeManager: SimpleIsolatedRuntimeManager;
export default SimpleIsolatedRuntimeManager;
//# sourceMappingURL=simpleRuntime.d.ts.map