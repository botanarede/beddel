/**
 * Isolated Runtime Manager - Isolated VM v5 Implementation
 * Provides ultra-secure isolated execution environment with zero-trust architecture
 */
import * as ivm from "isolated-vm";
import { RuntimeConfig, SecurityProfile } from "../config";
import { EventEmitter } from "events";
export interface RuntimeContext {
    isolate: ivm.Isolate;
    context: ivm.Context;
    jail: ivm.Reference;
    executionCount: number;
    createdAt: Date;
    lastUsedAt: Date;
    memoryUsage: number;
    securityProfile: SecurityProfile;
}
export interface ExecutionResult<T = any> {
    success: boolean;
    result?: T;
    error?: Error;
    executionTime: number;
    memoryUsed: number;
    auditHash?: string;
    timestamp: Date;
    securityScore?: number;
    warnings?: string[];
}
export interface ExecutionOptions {
    code: string;
    context?: Record<string, any>;
    securityProfile?: string;
    timeout?: number;
    memoryLimit?: number;
    tenantId?: string;
    auditData?: any;
    scanForSecurity?: boolean;
}
export declare class IsolatedRuntimeError extends Error {
    readonly code: string;
    readonly context?: any | undefined;
    constructor(message: string, code: string, context?: any | undefined);
}
export declare class IsolatedRuntimeManager extends EventEmitter {
    private config;
    private isolates;
    private pool;
    private activeExecutions;
    private metrics;
    private readonly maxPoolSize;
    private readonly minPoolSize;
    private readonly cleanupInterval;
    constructor(config?: RuntimeConfig);
    /**
     * Initialize the isolate pool with minimum required isolates
     */
    private initializePool;
    /**
     * Create a new isolated context with specified security profile
     */
    private createIsolate;
    /**
     * Execute code in isolated environment
     */
    execute<T = any>(options: ExecutionOptions): Promise<ExecutionResult<T>>;
    /**
     * Execute code in specific isolate context
     */
    private executeInIsolate;
    /**
     * Get or create isolate for execution
     */
    private getOrCreateIsolate;
    /**
     * Validate execution options
     */
    private validateExecutionOptions;
    /**
     * Calculate memory usage for isolate
     */
    private getMemoryUsage;
    /**
     * Update metrics tracking
     */
    private updateMetrics;
    /**
     * Generate unique execution ID
     */
    private generateExecutionId;
    /**
     * Generate audit hash for execution
     */
    private generateAuditHash;
    /**
     * Cleanup idle isolates
     */
    private cleanupPool;
    /**
     * Get current metrics
     */
    getMetrics(): Record<string, number[]>;
    /**
     * Get pool statistics
     */
    getPoolStats(): {
        totalIsolates: number;
        poolSize: number;
        activeExecutions: number;
        minPoolSize: number;
        maxPoolSize: number;
    };
    /**
     * Dispose of all isolates and cleanup resources
     */
    dispose(): Promise<void>;
}
export declare const runtimeManager: IsolatedRuntimeManager;
export default IsolatedRuntimeManager;
//# sourceMappingURL=isolatedRuntime.d.ts.map