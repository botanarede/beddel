"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.performanceMonitor = exports.PerformanceMonitor = void 0;
/**
 * Performance Monitor - Execution Performance Tracking
 * Monitors execution performance with <50ms target and memory tracking
 */
const node_perf_hooks_1 = require("node:perf_hooks");
const config_1 = require("../config");
class PerformanceMonitor {
    constructor() {
        this.metrics = new Map();
        this.violations = [];
        this.recommendations = [];
        this.retentionPeriod = 60 * 60 * 1000; // 1 hour
        this.alertThreshold = 0.8; // 80% of target
        this.criticalThreshold = 1.5; // 150% of target
        this.startCleanupInterval();
    }
    /**
     * Record a performance metric
     */
    recordMetric(metric) {
        if (!this.metrics.has(metric.metric)) {
            this.metrics.set(metric.metric, []);
        }
        const metrics = this.metrics.get(metric.metric);
        metrics.push(metric);
        // Check for violations
        const target = config_1.performanceTargets.find((t) => t.metric === metric.metric);
        if (target) {
            const violation = this.checkViolation(metric, target);
            if (violation) {
                this.violations.push(violation);
                this.logViolation(violation);
            }
        }
        // Keep only metrics within retention period
        this.cleanupOldMetrics(metric.metric, this.retentionPeriod);
    }
    /**
     * Record execution performance metrics
     */
    recordExecution(executionId, executionTime, memoryUsed, tenantId) {
        const timestamp = new Date();
        // Record execution time
        this.recordMetric({
            metric: "executionTime",
            value: executionTime,
            timestamp,
            executionId,
            tenantId,
        });
        // Record memory usage
        this.recordMetric({
            metric: "memoryUsage",
            value: memoryUsed,
            timestamp,
            executionId,
            tenantId,
        });
        // Generate recommendations based on metrics
        this.generateRecommendations(executionTime, memoryUsed, tenantId);
    }
    /**
     * Simple benchmarking helper so downstream modules can compare strategies.
     */
    async benchmark(fn, label, iterations = 1, payloadSize) {
        if (iterations < 1) {
            throw new Error("Benchmark iterations must be >= 1");
        }
        const samples = [];
        for (let i = 0; i < iterations; i++) {
            const start = node_perf_hooks_1.performance.now();
            await Promise.resolve(fn());
            const duration = node_perf_hooks_1.performance.now() - start;
            samples.push(duration);
            this.recordMetric({
                metric: "benchmark",
                value: duration,
                timestamp: new Date(),
                executionId: `${label}-${i}`,
            });
        }
        const averageTime = samples.reduce((total, value) => total + value, 0) / samples.length;
        return {
            label,
            iterations,
            averageTime,
            minTime: Math.min(...samples),
            maxTime: Math.max(...samples),
            payloadSize,
        };
    }
    /**
     * Check for performance violations
     */
    checkViolation(metric, target) {
        const threshold = target.threshold;
        const isViolation = metric.value > threshold;
        if (!isViolation)
            return null;
        const severity = metric.value > target.target * this.criticalThreshold
            ? "critical"
            : "warning";
        return {
            metric: metric.metric,
            value: metric.value,
            target: target.target,
            severity,
            timestamp: metric.timestamp,
            executionId: metric.executionId,
        };
    }
    /**
     * Log violations for monitoring
     */
    logViolation(violation) {
        const message = `[PERFORMANCE_${violation.severity.toUpperCase()}] ${violation.metric}: ${violation.value} ${config_1.performanceTargets
            .find((t) => t.metric === violation.metric)
            ?.unit?.toLowerCase()} (target: ${violation.target}) - Execution ID: ${violation.executionId}`;
        console.log(`[${violation.timestamp.toISOString()}] ${message}`);
    }
    /**
     * Generate performance recommendations
     */
    generateRecommendations(executionTime, memoryUsed, tenantId) {
        const executionTimeTarget = config_1.performanceTargets.find((t) => t.metric === "executionTime")?.target ||
            50;
        const memoryTarget = config_1.performanceTargets.find((t) => t.metric === "memoryUsage")?.target || 2;
        // Execution time recommendations
        if (executionTime > executionTimeTarget * 1.2) {
            this.recommendations.push({
                type: "performance",
                priority: "high",
                description: `Execution time ${executionTime}ms exceeds target by ${(((executionTime - executionTimeTarget) / executionTimeTarget) *
                    100).toFixed(1)}%`,
                action: "Consider optimizing code complexity or splitting execution",
                estimatedImpact: -30, // 30% improvement
            });
        }
        // Memory usage recommendations
        if (memoryUsed > memoryTarget * 1.5) {
            this.recommendations.push({
                type: "memory",
                priority: "medium",
                description: `Memory usage ${memoryUsed}MB exceeds target by ${(((memoryUsed - memoryTarget) / memoryTarget) *
                    100).toFixed(1)}%`,
                action: "Review memory allocation patterns and object cleanup",
                estimatedImpact: -25,
            });
        }
        // Pool scaling recommendations
        if (executionTime > executionTimeTarget * 1.5) {
            this.recommendations.push({
                type: "scaling",
                priority: "medium",
                description: "Pool may need scaling due to high execution times",
                action: "Consider increasing pool size or optimizing isolation setup",
                estimatedImpact: -20,
            });
        }
    }
    /**
     * Get current performance snapshot
     */
    getSnapshot() {
        const snapshot = {
            timestamp: new Date(),
            metrics: {},
            averages: {},
            violations: [...this.violations],
            recommendations: [...this.recommendations],
        };
        // Calculate averages for each metric
        for (const target of config_1.performanceTargets) {
            const metrics = this.metrics.get(target.metric) || [];
            if (metrics.length > 0) {
                const values = metrics.map((m) => m.value);
                const average = values.reduce((a, b) => a + b, 0) / values.length;
                snapshot.metrics[target.metric] = values;
                snapshot.averages[target.metric] = Math.round(average * 100) / 100;
            }
        }
        return snapshot;
    }
    /**
     * Get performance statistics for a specific period
     */
    getStats(metric, period = 5 * 60 * 1000) {
        const metrics = this.metrics.get(metric) || [];
        const cutoff = new Date(Date.now() - period);
        const recentMetrics = metrics.filter((m) => m.timestamp >= cutoff);
        if (recentMetrics.length === 0) {
            return {
                average: 0,
                min: 0,
                max: 0,
                count: 0,
                violations: 0,
            };
        }
        const values = recentMetrics.map((m) => m.value);
        const target = config_1.performanceTargets.find((t) => t.metric === metric);
        return {
            average: values.reduce((a, b) => a + b, 0) / recentMetrics.length,
            min: Math.min(...values),
            max: Math.max(...values),
            count: recentMetrics.length,
            violations: this.violations.filter((v) => {
                return (v.metric === metric &&
                    v.timestamp >= cutoff &&
                    v.value > (target?.target || 0));
            }).length,
        };
    }
    /**
     * Check if performance is within acceptable ranges
     */
    isPerformanceHealthy() {
        const snapshot = this.getSnapshot();
        // Check if any critical violations in last 5 minutes
        const recentViolations = this.violations.filter((v) => v.timestamp >= new Date(Date.now() - 5 * 60 * 1000) &&
            v.severity === "critical");
        if (recentViolations.length > 3) {
            return false; // More than 3 critical violations
        }
        // Check if averages are within acceptable ranges
        for (const target of config_1.performanceTargets) {
            const average = snapshot.averages[target.metric];
            if (average && average > target.target * this.alertThreshold) {
                return false; // Performance target exceeded
            }
        }
        return true;
    }
    /**
     * Get performance alerts
     */
    getAlerts() {
        const now = new Date();
        const recentViolations = this.violations.filter((v) => v.timestamp >= new Date(now.getTime() - 15 * 60 * 1000) // Last 15 minutes
        );
        return {
            warnings: recentViolations.filter((v) => v.severity === "warning"),
            criticals: recentViolations.filter((v) => v.severity === "critical"),
        };
    }
    /**
     * Cleanup metrics older than retention period
     */
    cleanupOldMetrics(metric, maxAge) {
        const metrics = this.metrics.get(metric) || [];
        const cutoff = new Date(Date.now() - maxAge);
        const filteredMetrics = metrics.filter((m) => m.timestamp >= cutoff);
        this.metrics.set(metric, filteredMetrics);
    }
    /**
     * Start periodic cleanup interval
     */
    startCleanupInterval() {
        setInterval(() => {
            for (const [metric] of this.metrics) {
                this.cleanupOldMetrics(metric, this.retentionPeriod);
            }
            // Remove old violations
            const cutoff = new Date(Date.now() - this.retentionPeriod);
            this.violations = this.violations.filter((v) => v.timestamp >= cutoff);
            // Remove old recommendations
            if (this.recommendations.length > 100) {
                this.recommendations = this.recommendations.slice(-100);
            }
        }, this.retentionPeriod / 2);
    }
    /**
     * Get performance summary
     */
    getPerformanceSummary() {
        const snapshot = this.getSnapshot();
        const alerts = this.getAlerts();
        // Calculate overall performance rating
        let overall = "excellent";
        if (alerts.criticals.length > 0)
            overall = "critical";
        else if (alerts.warnings.length > 3)
            overall = "warning";
        else if (alerts.warnings.length > 0)
            overall = "good";
        return {
            overall,
            executionTime: snapshot.averages["executionTime"] || 0,
            memoryUsage: snapshot.averages["memoryUsage"] || 0,
            successRate: snapshot.averages["successRate"] || 99.9,
            alerts: alerts.warnings.length + alerts.criticals.length,
            recommendations: this.recommendations.length,
        };
    }
    /**
     * Dump performance data for analysis
     */
    dumpData() {
        const snapshot = this.getSnapshot();
        const summary = this.getPerformanceSummary();
        return JSON.stringify({
            snapshot,
            summary,
            violations: this.violations.slice(-50), // Last 50 violations
            recommendations: this.recommendations.slice(-20), // Last 20 recommendations
        }, null, 2);
    }
    /**
     * Dispose of monitor resources
     */
    dispose() {
        this.metrics.clear();
        this.violations = [];
        this.recommendations = [];
    }
}
exports.PerformanceMonitor = PerformanceMonitor;
// Singleton instance
exports.performanceMonitor = new PerformanceMonitor();
exports.default = PerformanceMonitor;
//# sourceMappingURL=monitor.js.map