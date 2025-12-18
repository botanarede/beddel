import { SecurityEvent } from "./monitor";
import { ThreatAnalysis } from "./threatDetector";
export interface DashboardConfig {
    refreshInterval: number;
    maxDisplayEvents: number;
    highlightThreshold: number;
    enableRealTimeUpdates: boolean;
}
export interface SecurityMetric {
    timestamp: Date;
    tenantId: string;
    metricType: string;
    value: number;
    riskLevel: "low" | "medium" | "high" | "critical";
    description: string;
}
export interface SecurityDashboardData {
    summary: SecuritySummary;
    activeAlerts: SecurityEvent[];
    recentThreats: ThreatAnalysis[];
    tenantMetrics: TenantMetrics;
    complianceStatus: ComplianceStatus;
    realTimeChart: RealTimeChartData;
}
export interface SecuritySummary {
    totalEvents: number;
    totalAlerts: number;
    threatEvents: number;
    blockedOperations: number;
    securityScore: number;
    lastUpdate: Date;
}
export interface TenantMetrics {
    [tenantId: string]: {
        totalOperations: number;
        threatCount: number;
        riskScore: number;
        lastActivity: Date;
        alerts: SecurityEvent[];
    };
}
export interface ComplianceStatus {
    lgpd: ComplianceMetric;
    gdpr: ComplianceMetric;
    audit: ComplianceMetric;
}
export interface ComplianceMetric {
    status: "compliant" | "warning" | "violation";
    events: number;
    lastCheck: Date;
    score: number;
}
export interface RealTimeChartData {
    labels: string[];
    datasets: {
        label: string;
        data: number[];
        borderColor: string;
        backgroundColor: string;
    }[];
}
export declare class SecurityDashboard {
    private config;
    private events;
    private metrics;
    private startTime;
    private updateInterval;
    constructor(config?: Partial<DashboardConfig>);
    initialize(): void;
    private startRealTimeUpdates;
    stopRealTimeUpdates(): void;
    addEvent(event: SecurityEvent): void;
    addMetric(metric: SecurityMetric): void;
    generateMetrics(): void;
    private calculateSecurityScore;
    private generateTenantMetrics;
    private calculateTenantRiskScore;
    private generateComplianceStatus;
    private generateRealTimeChart;
    private getActiveAlerts;
    private getRecentThreats;
    private logDashboardUpdate;
    getDashboardData(): SecurityDashboardData;
    getSecurityMetrics(): SecurityMetric[];
    getEventHistory(limit?: number): SecurityEvent[];
    exportDashboardReport(): string;
}
export declare const securityDashboard: SecurityDashboard;
//# sourceMappingURL=dashboard.d.ts.map