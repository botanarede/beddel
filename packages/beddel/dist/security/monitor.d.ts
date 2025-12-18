import { EventEmitter } from "events";
export interface SecurityEvent {
    id: string;
    tenantId: string;
    operation: string;
    metadata: any;
    timestamp: Date;
    riskScore: number;
    alertLevel: AlertLevel;
}
export declare enum AlertLevel {
    INFO = "info",
    WARNING = "warning",
    CRITICAL = "critical",
    EMERGENCY = "emergency"
}
export interface ThreatAnalysis {
    riskScore: number;
    threatType: string;
    confidence: number;
    recommendations: string[];
}
export declare class SecurityMonitor extends EventEmitter {
    private static instance;
    private threatDetector;
    private alertManager;
    private metricsCollector;
    private isMonitoring;
    private auditTrail;
    private securityConfig;
    constructor();
    static getInstance(): SecurityMonitor;
    startMonitoring(): void;
    stopMonitoring(): void;
    isMonitoringActive(): boolean;
    monitorActivity(tenantId: string, operation: string, metadata: any): Promise<SecurityEvent>;
    private generateEventId;
    private determineAlertLevel;
    private logSecurityEvent;
    private triggerSecurityAlert;
    logEvent(tenantId: string, operation: string, metadata: any, riskScore?: number): Promise<SecurityEvent>;
    getMetrics(): any;
    getThreatStatistics(): {
        patternsLoaded: number;
        lastUpdate: string;
        mlModelVersion: string;
    };
}
export declare class ThreatDetectionEngine {
    private patterns;
    private anomalyDetector;
    private mlModel;
    constructor();
    private initializePatterns;
    analyze(tenantId: string, operation: string, metadata: any): Promise<ThreatAnalysis>;
    private generateRecommendations;
    getStatistics(): {
        patternsLoaded: number;
        lastUpdate: string;
        mlModelVersion: string;
    };
}
export declare class AnomalyDetector {
    private normalPatterns;
    private anomalyThreshold;
    detectAnomaly(tenantId: string, operation: string, metadata: any): Promise<number>;
}
export declare class ThreatMLModel {
    private modelWeights;
    constructor();
    private initializeModel;
    predict(tenantId: string, operation: string, metadata: any): Promise<number>;
}
export declare class AlertManager {
    private alertHistory;
    private readonly MAX_ALERTS_PER_TENANT;
    sendAlert(event: SecurityEvent): Promise<void>;
    getAlertHistory(tenantId: string): SecurityEvent[];
    getAlertSummary(): Record<string, any>;
}
export declare class MetricsCollector {
    private metrics;
    recordEvent(event: SecurityEvent): void;
    getMetrics(): any;
    resetMetrics(): void;
}
export declare const securityMonitor: SecurityMonitor;
//# sourceMappingURL=monitor.d.ts.map