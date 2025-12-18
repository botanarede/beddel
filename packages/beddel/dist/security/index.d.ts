/**
 * Beddel Security Module - Advanced Security Monitoring System v2025
 *
 * Complete security monitoring solution with real-time threat detection,
 * ML-based anomaly analysis, and automated incident response.
 */
export type { AlertLevel, SecurityEvent, ThreatAnalysis } from "./monitor";
export { SecurityMonitor, securityMonitor } from "./monitor";
export { ThreatDetectionEngine, AnomalyDetector, ThreatMLModel, } from "./threatDetector";
export type { DashboardConfig, SecurityMetric } from "./dashboard";
export { SecurityDashboard, securityDashboard } from "./dashboard";
/**
 * Security Manager - Main security system coordinator
 */
export declare class SecurityManager {
    private monitor;
    private dashboard;
    private isInitialized;
    constructor();
    /**
     * Initialize the complete security system
     */
    initialize(): void;
    /**
     * Set up event listeners for security events
     */
    private setupEventListeners;
    /**
     * Monitor security operations
     */
    monitorSecurity(tenantId: string, operation: string, metadata?: any): Promise<any>;
    /**
     * Auto-respond to threats
     */
    private autoRespondToThreat;
    /**
     * Handle security alerts
     */
    private handleSecurityAlert;
    /**
     * Assess risk level
     */
    private assessRiskLevel;
    /**
     * Generate incident response
     */
    private generateIncidentResponse;
    /**
     ** Get current dashboard data
     */
    getDashboardData(): any;
    /**
     * Get security metrics
     */
    getSecurityMetrics(): any[];
    /**
     * Export security report
     */
    exportSecurityReport(): string;
    /**
     * Get monitoring status
     */
    getMonitoringStatus(): {
        active: boolean;
        eventsProcessed: number;
    };
    /**
     * Get threat statistics
     */
    getThreatStatistics(): any;
    /**
     * Get real-time security updates
     */
    getRealTimeUpdates(): any;
    /**
     * Stop the security system
     */
    stop(): void;
    /**
     * Schedule health check
     */
    private scheduleHealthCheck;
    /**
     * Perform health check
     */
    private performHealthCheck;
    /**
     * Stop health check
     */
    private stopHealthCheck;
}
export declare const securityManager: SecurityManager;
/**
 * Initialize security system globally
 */
export declare function initializeSecuritySystem(): void;
/**
 * Monitor security operation
 */
export declare function monitorSecurity(tenantId: string, operation: string, metadata?: any): Promise<any>;
/**
 * Get security dashboard data
 */
export declare function getSecurityDashboard(): any;
/**
 * Export security report
 */
export declare function exportSecurityReport(): string;
/**
 * Stop security system
 */
export declare function stopSecuritySystem(): void;
export interface SecuritySystemStatus {
    active: boolean;
    securityScore: number;
    eventsProcessed: number;
    threatDetectionRate: number;
    lastUpdate: Date;
}
export interface SecurityIncident {
    id: string;
    tenantId: string;
    riskScore: number;
    alertLevel: string;
    timestamp: Date;
    status: "new" | "in_progress" | "resolved" | "escalated";
}
//# sourceMappingURL=index.d.ts.map