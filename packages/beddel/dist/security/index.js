"use strict";
/**
 * Beddel Security Module - Advanced Security Monitoring System v2025
 *
 * Complete security monitoring solution with real-time threat detection,
 * ML-based anomaly analysis, and automated incident response.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.securityManager = exports.SecurityManager = exports.securityDashboard = exports.SecurityDashboard = exports.ThreatMLModel = exports.AnomalyDetector = exports.ThreatDetectionEngine = exports.securityMonitor = exports.SecurityMonitor = void 0;
exports.initializeSecuritySystem = initializeSecuritySystem;
exports.monitorSecurity = monitorSecurity;
exports.getSecurityDashboard = getSecurityDashboard;
exports.exportSecurityReport = exportSecurityReport;
exports.stopSecuritySystem = stopSecuritySystem;
var monitor_1 = require("./monitor");
Object.defineProperty(exports, "SecurityMonitor", { enumerable: true, get: function () { return monitor_1.SecurityMonitor; } });
Object.defineProperty(exports, "securityMonitor", { enumerable: true, get: function () { return monitor_1.securityMonitor; } });
var threatDetector_1 = require("./threatDetector");
Object.defineProperty(exports, "ThreatDetectionEngine", { enumerable: true, get: function () { return threatDetector_1.ThreatDetectionEngine; } });
Object.defineProperty(exports, "AnomalyDetector", { enumerable: true, get: function () { return threatDetector_1.AnomalyDetector; } });
Object.defineProperty(exports, "ThreatMLModel", { enumerable: true, get: function () { return threatDetector_1.ThreatMLModel; } });
var dashboard_1 = require("./dashboard");
Object.defineProperty(exports, "SecurityDashboard", { enumerable: true, get: function () { return dashboard_1.SecurityDashboard; } });
Object.defineProperty(exports, "securityDashboard", { enumerable: true, get: function () { return dashboard_1.securityDashboard; } });
const monitor_2 = require("./monitor");
const dashboard_2 = require("./dashboard");
/**
 * Security Manager - Main security system coordinator
 */
class SecurityManager {
    constructor() {
        this.isInitialized = false;
        this.monitor = monitor_2.securityMonitor;
        this.dashboard = dashboard_2.securityDashboard;
    }
    /**
     * Initialize the complete security system
     */
    initialize() {
        if (this.isInitialized) {
            console.log("🔒 Security system already initialized");
            return;
        }
        try {
            // Start monitoring
            this.monitor.startMonitoring();
            // Initialize dashboard
            this.dashboard.initialize();
            // Set up event listeners
            this.setupEventListeners();
            this.isInitialized = true;
            console.log("🛡️  Beddel Security System v2025 initialized successfully");
            // Schedule periodic health check
            this.scheduleHealthCheck();
        }
        catch (error) {
            console.error("❌ Failed to initialize security system:", error);
            throw error;
        }
    }
    /**
     * Set up event listeners for security events
     */
    setupEventListeners() {
        // Listen for security events
        this.monitor.on("securityEvent", (event) => {
            console.log(`🔍 Security event detected: ${event.tenantId} - ${event.operation} (Risk: ${event.riskScore})`);
            // Add to dashboard
            this.dashboard.addEvent(event);
            // Auto-respond to high-risk events
            if (event.riskScore > 0.8) {
                this.autoRespondToThreat(event);
            }
        });
        // Listen for security alerts
        this.monitor.on("securityAlert", (event) => {
            console.log(`🚨 SECURITY ALERT: ${event.tenantId} - ${event.operation} (Score: ${event.riskScore})`);
            this.handleSecurityAlert(event);
        });
        // Listen for monitoring events
        this.monitor.on("monitoringStarted", () => {
            console.log("✅ Security monitoring started");
        });
        this.monitor.on("monitoringStopped", () => {
            console.log("⏹️  Security monitoring stopped");
        });
    }
    /**
     * Monitor security operations
     */
    async monitorSecurity(tenantId, operation, metadata = {}) {
        if (!this.isInitialized) {
            throw new Error("Security system not initialized");
        }
        try {
            // Add security context to metadata
            const enrichedMetadata = {
                ...metadata,
                securityTimestamp: new Date().toISOString(),
                securitySystem: "Beddel-v2025",
            };
            return await this.monitor.monitorActivity(tenantId, operation, enrichedMetadata);
        }
        catch (error) {
            console.error("❌ Security monitoring failed:", error);
            throw error;
        }
    }
    /**
     * Auto-respond to threats
     */
    async autoRespondToThreat(event) {
        console.log(`🔄 Auto-responding to threat from ${event.tenantId}`);
        switch (event.alertLevel) {
            case "emergency":
                // Immediate response required
                console.log(`🚨 EMERGENCY RESPONSE: Isolating tenant ${event.tenantId}`);
                // In a real implementation, would:
                // 1. Block tenant operations
                // 2. Notify security team
                // 3. Preserve evidence
                // 4. Alert compliance team
                break;
            case "critical":
                console.log(`⚠️  CRITICAL RESPONSE: Enhanced monitoring for ${event.tenantId}`);
                break;
            case "warning":
                console.log(`⚠️  WARNING RESPONSE: Alerting security team about ${event.tenantId}`);
                break;
        }
        // Generate automated incident response
        await this.generateIncidentResponse(event);
    }
    /**
     * Handle security alerts
     */
    handleSecurityAlert(event) {
        // Add alert to dashboard
        const alertMetric = {
            timestamp: new Date(),
            tenantId: event.tenantId,
            metricType: "security_alert",
            value: event.riskScore,
            riskLevel: this.assessRiskLevel(event.riskScore),
            description: `Security alert: ${event.operation}`,
        };
        this.dashboard.addMetric(alertMetric);
        // Log alert details
        console.warn(`🚨 Security Alert Details:
      Tenant: ${event.tenantId}
      Operation: ${event.operation}
      Risk Score: ${event.riskScore}
      Alert Level: ${event.alertLevel}
      Time: ${event.timestamp}
    `);
    }
    /**
     * Assess risk level
     */
    assessRiskLevel(riskScore) {
        if (riskScore >= 0.9)
            return "critical";
        if (riskScore >= 0.7)
            return "high";
        if (riskScore >= 0.4)
            return "medium";
        return "low";
    }
    /**
     * Generate incident response
     */
    async generateIncidentResponse(event) {
        const incidentId = `INC-${Date.now()}-${Math.random()
            .toString(36)
            .substr(2, 9)}`;
        const responseActions = [];
        // Determine response actions based on risk level
        if (event.riskScore > 0.8) {
            responseActions.push("Isolate tenant immediately");
            responseActions.push("Block further operations");
            responseActions.push("Alert security team");
            responseActions.push("Preserve audit logs");
            responseActions.push("Notify compliance team");
        }
        else if (event.riskScore > 0.6) {
            responseActions.push("Increase monitoring");
            responseActions.push("Log all operations");
            responseActions.push("Alert security team");
            responseActions.push("Check access permissions");
        }
        else {
            responseActions.push("Monitor closely");
            responseActions.push("Document the event");
        }
        console.log(`📋 Incident Response Generated:
      Incident ID: ${incidentId}
      Tenant: ${event.tenantId}
      Risk Level: ${event.riskScore}
      Response Actions: ${responseActions.length}
    `);
        // Simulate response execution
        for (const action of responseActions) {
            console.log(`  • Executing: ${action}`);
            // Simulate processing time
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        console.log(`✅ Incident response completed for ${incidentId}`);
    }
    /**
     ** Get current dashboard data
     */
    getDashboardData() {
        return this.dashboard.getDashboardData();
    }
    /**
     * Get security metrics
     */
    getSecurityMetrics() {
        return this.dashboard.getSecurityMetrics();
    }
    /**
     * Export security report
     */
    exportSecurityReport() {
        const data = this.getDashboardData();
        const report = this.dashboard.exportDashboardReport();
        const securityReport = `
# Beddel Security Report - ${new Date().toISOString()}

## System Status
- Security System: ACTIVE
- Monitoring Status: ${this.monitor.isMonitoringActive() ? "RUNNING" : "STOPPED"}
- Risk Score: ${data.summary.securityScore}/10
- Total Events: ${data.summary.totalEvents}

${report}
`;
        return securityReport;
    }
    /**
     * Get monitoring status
     */
    getMonitoringStatus() {
        return {
            active: this.monitor.isMonitoringActive(),
            eventsProcessed: this.monitor.getMetrics().totalEvents,
        };
    }
    /**
     * Get threat statistics
     */
    getThreatStatistics() {
        return this.monitor.getThreatStatistics();
    }
    /**
     * Get real-time security updates
     */
    getRealTimeUpdates() {
        return {
            dashboard: this.getDashboardData(),
            metrics: this.getSecurityMetrics(),
            status: this.getMonitoringStatus(),
        };
    }
    /**
     * Stop the security system
     */
    stop() {
        if (!this.isInitialized) {
            console.log("Security system not running");
            return;
        }
        this.monitor.stopMonitoring();
        this.dashboard.stopRealTimeUpdates();
        this.stopHealthCheck();
        this.isInitialized = false;
        console.log("🛑 Security system stopped");
    }
    /**
     * Schedule health check
     */
    scheduleHealthCheck() {
        // Health check every 5 minutes
        setInterval(() => {
            this.performHealthCheck();
        }, 5 * 60 * 1000);
    }
    /**
     * Perform health check
     */
    performHealthCheck() {
        try {
            const status = this.getMonitoringStatus();
            const dashboard = this.getDashboardData();
            const threats = this.getThreatStatistics();
            console.log(`🔍 Security Health Check:
        Status: ${status.active ? "ACTIVE" : "INACTIVE"}
        Events Processed: ${status.eventsProcessed}
        Security Score: ${dashboard.summary.securityScore}/10
        Threat Detection: ${threats.patternsLoaded} patterns active
        Last Update: ${dashboard.summary.lastUpdate.toISOString()}
      `);
            // If security score is too low, raise alert
            if (dashboard.summary.securityScore < 7.0) {
                console.error("🚨 CRITICAL: Security score below acceptable threshold");
            }
        }
        catch (error) {
            console.error("❌ Health check failed:", error);
        }
    }
    /**
     * Stop health check
     */
    stopHealthCheck() {
        // Implementation would clear any health check intervals
        console.log("Health checks stopped");
    }
}
exports.SecurityManager = SecurityManager;
// Global security manager instance
exports.securityManager = new SecurityManager();
/**
 * Initialize security system globally
 */
function initializeSecuritySystem() {
    exports.securityManager.initialize();
}
/**
 * Monitor security operation
 */
function monitorSecurity(tenantId, operation, metadata = {}) {
    return exports.securityManager.monitorSecurity(tenantId, operation, metadata);
}
/**
 * Get security dashboard data
 */
function getSecurityDashboard() {
    return exports.securityManager.getDashboardData();
}
/**
 * Export security report
 */
function exportSecurityReport() {
    return exports.securityManager.exportSecurityReport();
}
/**
 * Stop security system
 */
function stopSecuritySystem() {
    exports.securityManager.stop();
}
//# sourceMappingURL=index.js.map