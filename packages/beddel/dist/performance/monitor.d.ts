export interface PerformanceMetric {
    metric: string;
    value: number;
    timestamp: Date;
    executionId: string;
    tenantId?: string;
    context?: any;
}
export interface PerformanceSnapshot {
    timestamp: Date;
    metrics: Record<string, number[]>;
    averages: Record<string, number>;
    violations: Violation[];
    recommendations: Recommendation[];
}
export interface Violation {
    metric: string;
    value: number;
    target: number;
    severity: "warning" | "critical";
    timestamp: Date;
    executionId: string;
}
export interface Recommendation {
    type: "performance" | "memory" | "security" | "scaling";
    priority: "high" | "medium" | "low";
    description: string;
    action: string;
    estimatedImpact: number;
}
export interface BenchmarkResult {
    label: string;
    iterations: number;
    averageTime: number;
    minTime: number;
    maxTime: number;
    payloadSize?: number;
}
export declare class PerformanceMonitor {
    private metrics;
    private violations;
    private recommendations;
    private readonly retentionPeriod;
    private readonly alertThreshold;
    private readonly criticalThreshold;
    constructor();
    /**
     * Record a performance metric
     */
    recordMetric(metric: PerformanceMetric): void;
    /**
     * Record execution performance metrics
     */
    recordExecution(executionId: string, executionTime: number, memoryUsed: number, tenantId?: string): void;
    /**
     * Simple benchmarking helper so downstream modules can compare strategies.
     */
    benchmark<T>(fn: () => Promise<T> | T, label: string, iterations?: number, payloadSize?: number): Promise<BenchmarkResult>;
    /**
     * Check for performance violations
     */
    private checkViolation;
    /**
     * Log violations for monitoring
     */
    private logViolation;
    /**
     * Generate performance recommendations
     */
    private generateRecommendations;
    /**
     * Get current performance snapshot
     */
    getSnapshot(): PerformanceSnapshot;
    /**
     * Get performance statistics for a specific period
     */
    getStats(metric: string, period?: number): {
        average: number;
        min: number;
        max: number;
        count: number;
        violations: number;
    };
    /**
     * Check if performance is within acceptable ranges
     */
    isPerformanceHealthy(): boolean;
    /**
     * Get performance alerts
     */
    getAlerts(): {
        warnings: Violation[];
        criticals: Violation[];
    };
    /**
     * Cleanup metrics older than retention period
     */
    private cleanupOldMetrics;
    /**
     * Start periodic cleanup interval
     */
    private startCleanupInterval;
    /**
     * Get performance summary
     */
    getPerformanceSummary(): {
        overall: "excellent" | "good" | "warning" | "critical";
        executionTime: number;
        memoryUsage: number;
        successRate: number;
        alerts: number;
        recommendations: number;
    };
    /**
     * Dump performance data for analysis
     */
    dumpData(): string;
    /**
     * Dispose of monitor resources
     */
    dispose(): void;
}
export declare const performanceMonitor: PerformanceMonitor;
export default PerformanceMonitor;
//# sourceMappingURL=monitor.d.ts.map