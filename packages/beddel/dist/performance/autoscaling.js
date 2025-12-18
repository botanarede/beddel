"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.autoscaleSystem = exports.AutoscaleSystem = void 0;
exports.initializeAutoscaling = initializeAutoscaling;
exports.getAutoscalingConfig = getAutoscalingConfig;
/**
 * Autoscaling System - Dynamic Pool Management
 * Automatically adjusts isolate pool size based on performance metrics
 */
const monitor_1 = require("./monitor");
class AutoscaleSystem {
    constructor(runtimeManager, config) {
        this.runtimeManager = runtimeManager;
        this.config = config;
        this.isRunning = false;
        this.currentDecision = null;
        this.scalingHistory = [];
        this.lastScaleTime = 0;
        this.defaultConfig = {
            enabled: true,
            minPoolSize: 5,
            maxPoolSize: 100,
            scaleUpThreshold: 55, // 55ms - slightly above target
            scaleDownThreshold: 30, // 30ms - comfortable below target
            scaleInterval: 30000, // 30 seconds
            scaleUpFactor: 1.25, // Increase by 25%
            scaleDownFactor: 0.8, // Decrease by 20%
            metricsWindow: 60000, // 1 minute window
            safetyMargin: 1.2, // 20% safety margin
        };
    }
    /**
     * Start autoscaling monitoring
     */
    start() {
        if (this.isRunning)
            return;
        this.isRunning = true;
        this.lastScaleTime = Date.now();
        // Start monitoring loop
        this.monitoringLoop();
    }
    /**
     * Stop autoscaling monitoring
     */
    stop() {
        this.isRunning = false;
    }
    /**
     * Main monitoring loop
     */
    monitoringLoop() {
        if (!this.isRunning)
            return;
        this.evaluateScalingDecision()
            .then((decision) => {
            if (decision.action !== "maintain") {
                this.executeScalingDecision(decision);
            }
            this.currentDecision = decision;
            this.scalingHistory.push(decision);
            // Keep only last 100 decisions
            if (this.scalingHistory.length > 100) {
                this.scalingHistory.shift();
            }
        })
            .catch((error) => {
            console.error("Autoscaling evaluation error:", error);
        });
        // Schedule next evaluation
        setTimeout(() => this.monitoringLoop(), this.config.scaleInterval);
    }
    /**
     * Evaluate scaling decision based on current metrics
     */
    async evaluateScalingDecision() {
        const currentPoolStats = this.runtimeManager.getPoolStats();
        const performanceSnapshot = monitor_1.performanceMonitor.getSnapshot();
        const recentMetricsWindow = monitor_1.performanceMonitor.getStats("executionTime", this.config.metricsWindow);
        // Calculate current average metrics
        const avgExecutionTime = recentMetricsWindow.average;
        const successRate = performanceSnapshot.averages["successRate"] || 99.9;
        const avgMemoryUsage = performanceSnapshot.averages["memoryUsage"] || 2.0;
        // Calculate current pool utilization
        const totalIsolates = currentPoolStats.totalIsolates;
        const activeExecutions = currentPoolStats.activeExecutions;
        const poolUtilization = activeExecutions / totalIsolates || 0;
        const currentSize = totalIsolates;
        let targetSize = currentSize;
        let action = "maintain";
        let reason = "Performance within acceptable ranges";
        const now = Date.now();
        // Prevent frequent scaling (rate limiting)
        if (now - this.lastScaleTime < this.config.scaleInterval / 2) {
            return {
                action: "maintain",
                currentSize,
                targetSize: currentSize,
                reason: "Rate limiting in effect",
                timestamp: new Date(now),
                metrics: {
                    avgExecutionTime,
                    avgMemoryUsage,
                    successRate,
                    poolUtilization,
                },
            };
        }
        // High memory usage detection
        if (avgMemoryUsage > 5.0) {
            // >5MB average usage
            action = "scale_up";
            targetSize = Math.min(this.config.maxPoolSize, Math.max(currentSize * this.config.safetyMargin, currentSize + 2));
            reason = `High memory usage detected (${avgMemoryUsage.toFixed(1)}MB avg)`;
        }
        // Long execution time detection
        else if (avgExecutionTime >
            this.config.scaleUpThreshold * this.config.safetyMargin) {
            action = "scale_up";
            targetSize = Math.min(this.config.maxPoolSize, Math.ceil(currentSize * this.config.scaleUpFactor));
            reason = `Execution time exceed threshold (${avgExecutionTime.toFixed(1)}ms > ${this.config.scaleUpThreshold}ms)`;
        }
        // High pool utilization detection
        else if (poolUtilization > 0.8) {
            action = "scale_up";
            targetSize = Math.min(this.config.maxPoolSize, Math.ceil(currentSize * this.config.scaleUpFactor));
            reason = `High pool utilization (${(poolUtilization * 100).toFixed(1)}%)`;
        }
        // Low pool utilization and fast execution
        else if (avgExecutionTime < this.config.scaleDownThreshold &&
            poolUtilization < 0.3 &&
            currentSize > this.config.minPoolSize * 2) {
            action = "scale_down";
            targetSize = Math.max(this.config.minPoolSize, Math.ceil(currentSize * this.config.scaleDownFactor));
            reason = `Low utilization and fast execution (${avgExecutionTime.toFixed(1)}ms < ${this.config.scaleDownThreshold}ms)`;
        }
        // Ensure targetSize is within bounds
        targetSize = Math.max(this.config.minPoolSize, targetSize);
        targetSize = Math.min(this.config.maxPoolSize, targetSize);
        // If action is to scale but targetSize equals currentSize, maintain current size
        if (action !== "maintain" && targetSize === currentSize) {
            action = "maintain";
            reason = "Target size equals current size";
        }
        return {
            action,
            currentSize,
            targetSize,
            reason,
            timestamp: new Date(now),
            metrics: {
                avgExecutionTime,
                avgMemoryUsage,
                successRate,
                poolUtilization,
            },
        };
    }
    /**
     * Execute scaling decision
     */
    executeScalingDecision(decision) {
        if (!this.config.enabled)
            return;
        const currentTime = Date.now();
        const timeSinceLastScale = currentTime - this.lastScaleTime;
        // Additional safety check for scaling frequency
        if (timeSinceLastScale < this.config.scaleInterval / 3) {
            return; // Too soon to scale again
        }
        console.log(`[AUTOSCALE] ${decision.action.toUpperCase()}: Current: ${decision.currentSize} -> Target: ${decision.targetSize}`);
        console.log(`[AUTOSCALE] Reason: ${decision.reason}`);
        console.log(`[AUTOSCALE] Metrics: Execution=${decision.metrics.avgExecutionTime.toFixed(1)}ms, Memory=${decision.metrics.avgMemoryUsage.toFixed(1)}MB, Utilization=${decision.metrics.poolUtilization.toFixed(1)}`);
        if (decision.action === "scale_up") {
            this.scaleUp(decision.targetSize);
        }
        else if (decision.action === "scale_down") {
            this.scaleDown(decision.targetSize);
        }
        this.lastScaleTime = currentTime;
    }
    /**
     * Scale up pool size
     */
    scaleUp(targetSize) {
        const currentStats = this.runtimeManager.getPoolStats();
        const currentSize = currentStats.totalIsolates;
        // Validate scaling decisions
        if (targetSize < currentSize || targetSize > this.config.maxPoolSize) {
            console.warn(`[AUTOSCALE] Invalid scale-up target: ${targetSize} (current: ${currentSize}, max: ${this.config.maxPoolSize})`);
            return;
        }
        // Pool scaling is handled by the runtime manager
        console.log(`[AUTOSCALE] Scaling up from ${currentSize} to ${targetSize}`);
        // The actual pool scaling would be implemented in the IsolatedRuntimeManager
        // For now, we log the intention
        console.log(`[AUTOSCALE EVENT] scale_up from: ${currentSize}, to: ${targetSize}`);
        // Pool scaling logic would go here
    }
    /**
     * Scale down pool size
     */
    scaleDown(targetSize) {
        const currentStats = this.runtimeManager.getPoolStats();
        const currentSize = currentStats.totalIsolates;
        // Validate scaling decisions
        if (targetSize > currentSize || targetSize < this.config.minPoolSize) {
            console.warn(`[AUTOSCALE] Invalid scale-down target: ${targetSize} (current: ${currentSize}, min: ${this.config.minPoolSize})`);
            return;
        }
        console.log(`[AUTOSCALE] Scaling down from ${currentSize} to ${targetSize}`);
        console.log(`[AUTOSCALE] scale_down from: ${currentSize}, to: ${targetSize}`);
        // Pool scaling logic would go here
    }
    /**
     * Get current autoscaling status
     */
    getStatus() {
        return {
            isRunning: this.isRunning,
            currentDecision: this.currentDecision,
            lastScaleTime: new Date(this.lastScaleTime),
            scalingHistory: [...this.scalingHistory],
            config: { ...this.config },
        };
    }
    /**
     * Update autoscaling configuration
     */
    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
        console.log("[AUTOSCALE] Configuration updated");
    }
    /**
     * Get scaling recommendations
     */
    getRecommendations() {
        const snapshot = monitor_1.performanceMonitor.getSnapshot();
        const alerts = monitor_1.performanceMonitor.getAlerts(); // Use proper method
        const currentStats = this.getCurrentStats();
        const recommendations = [];
        // High execution time recommendation
        if (currentStats.avgExecutionTime > this.config.scaleUpThreshold) {
            recommendations.push(`Execution time (${currentStats.avgExecutionTime.toFixed(1)}ms) exceeds scale-up threshold (${this.config.scaleUpThreshold}ms). Consider scaling up.`);
        }
        // Memory usage recommendation
        if (currentStats.avgMemoryUsage > 3.0) {
            recommendations.push(`High memory usage detected (${currentStats.avgMemoryUsage.toFixed(1)}MB). Review memory patterns and consider scaling adjustments.`);
        }
        // Critical violation recommendation
        if (alerts.criticals.length > 5) {
            recommendations.push(`Multiple critical violations detected (${alerts.criticals.length}). Immediate attention recommended.`);
        }
        return recommendations;
    }
    /**
     * Get current performance stats for scaling decisions
     */
    getCurrentStats() {
        const snapshot = monitor_1.performanceMonitor.getSnapshot();
        return {
            avgExecutionTime: snapshot.averages["executionTime"] || 50,
            avgMemoryUsage: snapshot.averages["memoryUsage"] || 2,
            successRate: snapshot.averages["successRate"] || 99.9,
        };
    }
    /**
     * Predict optimal pool size based on current metrics
     */
    predictOptimalPoolSize() {
        const currentStats = this.runtimeManager.getPoolStats();
        const currentSize = currentStats.totalIsolates;
        const snapshot = monitor_1.performanceMonitor.getSnapshot();
        const avgExecutionTime = snapshot.averages["executionTime"] || 50;
        const poolUtilization = currentStats.activeExecutions / currentSize || 0;
        let recommended = currentSize;
        let confidence = "medium";
        const factors = [];
        // Performance-based recommendation
        if (avgExecutionTime > this.config.scaleUpThreshold * 2) {
            recommended = Math.ceil(currentSize * 1.5);
            confidence = "high";
            factors.push(`High execution time (${avgExecutionTime.toFixed(1)}ms)`);
        }
        else if (avgExecutionTime < this.config.scaleDownThreshold / 2) {
            recommended = Math.max(this.config.minPoolSize, Math.floor(currentSize * 0.7));
            factors.push(`Low execution time (${avgExecutionTime.toFixed(1)}ms)`);
        }
        // Utilization-based recommendation
        if (poolUtilization > 0.9) {
            recommended = Math.ceil(recommended * 1.2);
            confidence = "high";
            factors.push(`High pool utilization (${(poolUtilization * 100).toFixed(1)}%)`);
        }
        else if (poolUtilization < 0.2) {
            recommended = Math.floor(recommended * 0.8);
            factors.push(`Low pool utilization (${(poolUtilization * 100).toFixed(1)}%)`);
        }
        // Ensure bounds
        recommended = Math.max(this.config.minPoolSize, recommended);
        recommended = Math.min(this.config.maxPoolSize, recommended);
        return {
            recommended,
            current: currentSize,
            confidence,
            factors,
        };
    }
}
exports.AutoscaleSystem = AutoscaleSystem;
// Global autoscaling instance
exports.autoscaleSystem = null;
function initializeAutoscaling(runtimeManager, config) {
    const baseConfig = {
        enabled: true,
        minPoolSize: 5,
        maxPoolSize: 100,
        scaleUpThreshold: 55,
        scaleDownThreshold: 30,
        scaleInterval: 30000,
        scaleUpFactor: 1.25,
        scaleDownFactor: 0.8,
        metricsWindow: 60000,
        safetyMargin: 1.2,
    };
    // Merge with default config
    const mergedConfig = {
        ...baseConfig,
        ...config,
    };
    exports.autoscaleSystem = new AutoscaleSystem(runtimeManager, mergedConfig);
    return exports.autoscaleSystem;
}
// Make config accessible
function getAutoscalingConfig() {
    return exports.autoscaleSystem ? exports.autoscaleSystem.getStatus().config : null;
}
exports.default = AutoscaleSystem;
//# sourceMappingURL=autoscaling.js.map