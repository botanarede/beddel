"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.securityMonitor = exports.MetricsCollector = exports.AlertManager = exports.ThreatMLModel = exports.AnomalyDetector = exports.ThreatDetectionEngine = exports.SecurityMonitor = exports.AlertLevel = void 0;
const events_1 = require("events");
const auditTrail_1 = require("../audit/auditTrail");
const config_1 = require("../config");
var AlertLevel;
(function (AlertLevel) {
    AlertLevel["INFO"] = "info";
    AlertLevel["WARNING"] = "warning";
    AlertLevel["CRITICAL"] = "critical";
    AlertLevel["EMERGENCY"] = "emergency";
})(AlertLevel || (exports.AlertLevel = AlertLevel = {}));
class SecurityMonitor extends events_1.EventEmitter {
    constructor() {
        super();
        this.isMonitoring = false;
        this.threatDetector = new ThreatDetectionEngine();
        this.alertManager = new AlertManager();
        this.metricsCollector = new MetricsCollector();
        this.auditTrail = new auditTrail_1.AuditTrail();
        this.securityConfig = {
            alertThreshold: config_1.runtimeConfig.securityScore >= 9.5 ? 0.7 : 0.6,
        };
    }
    static getInstance() {
        if (!SecurityMonitor.instance) {
            SecurityMonitor.instance = new SecurityMonitor();
        }
        return SecurityMonitor.instance;
    }
    startMonitoring() {
        if (this.isMonitoring) {
            return;
        }
        this.isMonitoring = true;
        this.emit("monitoringStarted", { timestamp: new Date() });
        this.logEvent("system", "monitoring_started", { version: "2025.1.0" });
    }
    stopMonitoring() {
        if (!this.isMonitoring) {
            return;
        }
        this.isMonitoring = false;
        this.emit("monitoringStopped", { timestamp: new Date() });
        this.logEvent("system", "monitoring_stopped", { reason: "manual" });
    }
    isMonitoringActive() {
        return this.isMonitoring;
    }
    async monitorActivity(tenantId, operation, metadata) {
        if (!this.isMonitoring) {
            throw new Error("Security monitoring is not active");
        }
        const eventId = this.generateEventId();
        const timestamp = new Date();
        // Perform threat analysis
        const threatAnalysis = await this.threatDetector.analyze(tenantId, operation, metadata);
        const securityEvent = {
            id: eventId,
            tenantId,
            operation,
            metadata,
            timestamp,
            riskScore: threatAnalysis.riskScore,
            alertLevel: this.determineAlertLevel(threatAnalysis.riskScore),
        };
        // Log to audit trail
        await this.logSecurityEvent(securityEvent);
        // Check if alert needs to be triggered
        if (securityEvent.riskScore > this.securityConfig.alertThreshold) {
            await this.triggerSecurityAlert(securityEvent);
        }
        // Emit event for real-time dashboards
        this.emit("securityEvent", securityEvent);
        this.metricsCollector.recordEvent(securityEvent);
        return securityEvent;
    }
    generateEventId() {
        return `sec-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }
    determineAlertLevel(riskScore) {
        if (riskScore >= 0.9)
            return AlertLevel.EMERGENCY;
        if (riskScore >= 0.7)
            return AlertLevel.CRITICAL;
        if (riskScore >= 0.4)
            return AlertLevel.WARNING;
        return AlertLevel.INFO;
    }
    async logSecurityEvent(event) {
        await this.auditTrail.logOperation({
            operationId: event.id,
            tenantId: event.tenantId,
            operation: `security_${event.operation}`,
            data: {
                metadata: event.metadata,
                riskScore: event.riskScore,
                alertLevel: event.alertLevel,
            },
            timestamp: event.timestamp,
            success: true,
        });
    }
    async triggerSecurityAlert(event) {
        await this.alertManager.sendAlert(event);
        this.emit("securityAlert", event);
    }
    async logEvent(tenantId, operation, metadata, riskScore = 0.1) {
        return this.monitorActivity(tenantId, operation, metadata);
    }
    getMetrics() {
        return this.metricsCollector.getMetrics();
    }
    getThreatStatistics() {
        return this.threatDetector.getStatistics();
    }
}
exports.SecurityMonitor = SecurityMonitor;
// Supporting Classes
class ThreatDetectionEngine {
    constructor() {
        this.patterns = new Map();
        this.initializePatterns();
        this.anomalyDetector = new AnomalyDetector();
        this.mlModel = new ThreatMLModel();
    }
    initializePatterns() {
        this.patterns.set("brute_force", /multiple_failed_attempts|rapid_login_sequence/i);
        this.patterns.set("sql_injection", /union.*select|drop.*table|exec.*\(.*\)/i);
        this.patterns.set("data_exfiltration", /bulk.*export|mass.*download|unusual.*access/i);
        this.patterns.set("cross_tenant", /cross.*tenant|tenant.*injection|unauthorized.*access/i);
        this.patterns.set("lgpd_violation", /unauthorized.*data|consent.*violation|retention.*breach/i);
    }
    async analyze(tenantId, operation, metadata) {
        let riskScore = 0.1; // Base risk
        let threatType = "low_risk";
        let confidence = 0.9;
        // Pattern matching
        for (const [patternName, pattern] of this.patterns) {
            if (pattern.test(operation) || pattern.test(JSON.stringify(metadata))) {
                riskScore += patternName === "emergency" ? 0.8 : 0.4;
                threatType = patternName;
                break;
            }
        }
        // Anomaly detection
        const anomalyScore = await this.anomalyDetector.detectAnomaly(tenantId, operation, metadata);
        riskScore += anomalyScore * 0.3;
        // ML model prediction
        const mlScore = await this.mlModel.predict(tenantId, operation, metadata);
        riskScore += mlScore * 0.2;
        // Cap risk score at 1.0
        riskScore = Math.min(riskScore, 1.0);
        const recommendations = this.generateRecommendations(riskScore, threatType);
        return {
            riskScore,
            threatType,
            confidence,
            recommendations,
        };
    }
    generateRecommendations(riskScore, threatType) {
        const recommendations = [];
        if (riskScore > 0.7) {
            recommendations.push("Immediate investigation required");
            recommendations.push("Consider tenant isolation");
            recommendations.push("Notify security team");
        }
        else if (riskScore > 0.4) {
            recommendations.push("Monitor closely");
            recommendations.push("Check access logs");
            recommendations.push("Review permissions");
        }
        else {
            recommendations.push("Routine monitoring");
            recommendations.push("Document pattern");
        }
        return recommendations;
    }
    getStatistics() {
        return {
            patternsLoaded: this.patterns.size,
            lastUpdate: new Date().toISOString(),
            mlModelVersion: "2025.1.0",
        };
    }
}
exports.ThreatDetectionEngine = ThreatDetectionEngine;
class AnomalyDetector {
    constructor() {
        this.normalPatterns = new Map();
        this.anomalyThreshold = 2.5;
    }
    async detectAnomaly(tenantId, operation, metadata) {
        const key = `${tenantId}:${operation}`;
        const currentTime = new Date().getTime();
        if (!this.normalPatterns.has(key)) {
            this.normalPatterns.set(key, []);
        }
        const patterns = this.normalPatterns.get(key);
        // Simple time-based anomaly detection
        if (patterns.length > 10) {
            const timeInterval = currentTime - patterns[patterns.length - 1].timestamp;
            // Check if current operation is happening too frequently
            if (timeInterval < 1000) {
                // Less than 1 second
                return 0.6; // High anomaly score
            }
            // Check for unusual velocity
            const intervals = [];
            for (let i = 1; i < patterns.length; i++) {
                intervals.push(patterns[i].timestamp - patterns[i - 1].timestamp);
            }
            const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
            const currentDeviation = Math.abs(timeInterval - avgInterval) / avgInterval;
            if (currentDeviation > this.anomalyThreshold) {
                return 0.4;
            }
        }
        // Store current pattern
        patterns.push({
            timestamp: currentTime,
            metadata: metadata,
        });
        // Keep only recent patterns (last 24 hours)
        const cutoff = currentTime - 24 * 60 * 60 * 1000;
        this.normalPatterns.set(key, patterns.filter((p) => p.timestamp > cutoff));
        return 0.0; // Normal behavior
    }
}
exports.AnomalyDetector = AnomalyDetector;
class ThreatMLModel {
    constructor() {
        this.modelWeights = new Map();
        this.initializeModel();
    }
    initializeModel() {
        // Simplified ML model weights
        this.modelWeights.set("tenant_historical_access", 0.3);
        this.modelWeights.set("operation_frequency", 0.4);
        this.modelWeights.set("metadata_complexity", 0.2);
        this.modelWeights.set("time_based_anomaly", 0.1);
    }
    async predict(tenantId, operation, metadata) {
        // Simplified ML prediction
        let score = 0.0;
        // Higher risk for operations outside business hours
        const hour = new Date().getHours();
        if (hour < 6 || hour > 22) {
            score += 0.3;
        }
        // Higher risk for complex metadata
        if (JSON.stringify(metadata).length > 1000) {
            score += 0.2;
        }
        // Higher risk for bulk operations
        if (operation.includes("bulk") || operation.includes("mass")) {
            score += 0.4;
        }
        // Higher risk for cross-tenant operations
        if (operation.includes("cross") || operation.includes("tenant")) {
            score += 0.5;
        }
        return Math.min(score, 0.8);
    }
}
exports.ThreatMLModel = ThreatMLModel;
class AlertManager {
    constructor() {
        this.alertHistory = new Map();
        this.MAX_ALERTS_PER_TENANT = 100;
    }
    async sendAlert(event) {
        const key = event.tenantId;
        if (!this.alertHistory.has(key)) {
            this.alertHistory.set(key, []);
        }
        const alerts = this.alertHistory.get(key);
        alerts.push(event);
        // Keep only recent alerts
        if (alerts.length > this.MAX_ALERTS_PER_TENANT) {
            alerts.shift();
        }
        // Log the alert
        console.warn(`[SECURITY_ALERT] Tenant: ${event.tenantId}, Risk: ${event.riskScore}, Operation: ${event.operation}`);
    }
    getAlertHistory(tenantId) {
        return this.alertHistory.get(tenantId) || [];
    }
    getAlertSummary() {
        const summary = {};
        for (const [tenantId, alerts] of this.alertHistory) {
            summary[tenantId] = {
                totalAlerts: alerts.length,
                criticalAlerts: alerts.filter((a) => a.riskScore > 0.7).length,
                lastAlert: alerts[alerts.length - 1]?.timestamp,
            };
        }
        return summary;
    }
}
exports.AlertManager = AlertManager;
class MetricsCollector {
    constructor() {
        this.metrics = {
            totalEvents: 0,
            totalAlerts: 0,
            alertsByLevel: {
                info: 0,
                warning: 0,
                critical: 0,
                emergency: 0,
            },
            averageRiskScore: 0,
            lastUpdate: null,
        };
    }
    recordEvent(event) {
        this.metrics.totalEvents++;
        this.metrics.totalAlerts += event.riskScore > 0.7 ? 1 : 0;
        this.metrics.alertsByLevel[event.alertLevel]++;
        // Update average risk score
        this.metrics.averageRiskScore =
            (this.metrics.averageRiskScore * (this.metrics.totalEvents - 1) +
                event.riskScore) /
                this.metrics.totalEvents;
        this.metrics.lastUpdate = new Date().toISOString();
    }
    getMetrics() {
        return {
            ...this.metrics,
            alertRate: this.metrics.totalEvents > 0
                ? this.metrics.totalAlerts / this.metrics.totalEvents
                : 0,
        };
    }
    resetMetrics() {
        this.metrics = {
            totalEvents: 0,
            totalAlerts: 0,
            alertsByLevel: {
                info: 0,
                warning: 0,
                critical: 0,
                emergency: 0,
            },
            averageRiskScore: 0,
            lastUpdate: null,
        };
    }
}
exports.MetricsCollector = MetricsCollector;
// Export singleton instance
exports.securityMonitor = SecurityMonitor.getInstance();
//# sourceMappingURL=monitor.js.map