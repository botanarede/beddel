import { IsolatedRuntimeManager } from "../runtime/isolatedRuntime";
export interface AutoscaleConfig {
    enabled: boolean;
    minPoolSize: number;
    maxPoolSize: number;
    scaleUpThreshold: number;
    scaleDownThreshold: number;
    scaleInterval: number;
    scaleUpFactor: number;
    scaleDownFactor: number;
    metricsWindow: number;
    safetyMargin: number;
}
export interface AutoscaleDecision {
    action: "scale_up" | "scale_down" | "maintain";
    currentSize: number;
    targetSize: number;
    reason: string;
    timestamp: Date;
    metrics: {
        avgExecutionTime: number;
        avgMemoryUsage: number;
        successRate: number;
        poolUtilization: number;
    };
}
export declare class AutoscaleSystem {
    private runtimeManager;
    private config;
    private isRunning;
    private currentDecision;
    private scalingHistory;
    private lastScaleTime;
    private readonly defaultConfig;
    constructor(runtimeManager: IsolatedRuntimeManager, config: AutoscaleConfig);
    /**
     * Start autoscaling monitoring
     */
    start(): void;
    /**
     * Stop autoscaling monitoring
     */
    stop(): void;
    /**
     * Main monitoring loop
     */
    private monitoringLoop;
    /**
     * Evaluate scaling decision based on current metrics
     */
    private evaluateScalingDecision;
    /**
     * Execute scaling decision
     */
    private executeScalingDecision;
    /**
     * Scale up pool size
     */
    private scaleUp;
    /**
     * Scale down pool size
     */
    private scaleDown;
    /**
     * Get current autoscaling status
     */
    getStatus(): {
        isRunning: boolean;
        currentDecision: AutoscaleDecision | null;
        lastScaleTime: Date;
        scalingHistory: AutoscaleDecision[];
        config: AutoscaleConfig;
    };
    /**
     * Update autoscaling configuration
     */
    updateConfig(newConfig: Partial<AutoscaleConfig>): void;
    /**
     * Get scaling recommendations
     */
    getRecommendations(): string[];
    /**
     * Get current performance stats for scaling decisions
     */
    private getCurrentStats;
    /**
     * Predict optimal pool size based on current metrics
     */
    predictOptimalPoolSize(): {
        recommended: number;
        current: number;
        confidence: "high" | "medium" | "low";
        factors: string[];
    };
}
export declare let autoscaleSystem: AutoscaleSystem | null;
export declare function initializeAutoscaling(runtimeManager: IsolatedRuntimeManager, config?: Partial<AutoscaleConfig>): AutoscaleSystem;
export declare function getAutoscalingConfig(): AutoscaleConfig | null;
export default AutoscaleSystem;
//# sourceMappingURL=autoscaling.d.ts.map