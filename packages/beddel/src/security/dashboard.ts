import { SecurityEvent, AlertLevel } from "./monitor";
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

export class SecurityDashboard {
  private config: DashboardConfig;
  private events: SecurityEvent[] = [];
  private metrics: SecurityMetric[] = [];
  private startTime: Date;
  private updateInterval: NodeJS.Timeout | null = null;

  constructor(config: Partial<DashboardConfig> = {}) {
    this.config = {
      refreshInterval: 5000,
      maxDisplayEvents: 50,
      highlightThreshold: 0.7,
      enableRealTimeUpdates: true,
      ...config,
    };
    this.startTime = new Date();
  }

  public initialize(): void {
    console.log("🛡️ Security Dashboard initialized");
    if (this.config.enableRealTimeUpdates) {
      this.startRealTimeUpdates();
    }
  }

  private startRealTimeUpdates(): void {
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
    }

    this.updateInterval = setInterval(() => {
      this.generateMetrics();
    }, this.config.refreshInterval);
  }

  public stopRealTimeUpdates(): void {
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
      this.updateInterval = null;
    }
  }

  public addEvent(event: SecurityEvent): void {
    this.events.push(event);

    // Keep only recent events
    if (this.events.length > this.config.maxDisplayEvents * 2) {
      this.events = this.events.slice(-this.config.maxDisplayEvents * 2);
    }
  }

  public addMetric(metric: SecurityMetric): void {
    this.metrics.push(metric);

    // Keep metrics for last 24 hours only
    const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000);
    this.metrics = this.metrics.filter((m) => m.timestamp > cutoff);
  }

  public generateMetrics(): void {
    const now = new Date();

    // Generate security summary
    const summary: SecuritySummary = {
      totalEvents: this.events.length,
      totalAlerts: this.events.filter((e) => e.riskScore > 0.7).length,
      threatEvents: this.events.filter((e) => e.riskScore > 0.8).length,
      blockedOperations: this.events.filter(
        (e) => e.alertLevel === AlertLevel.EMERGENCY
      ).length,
      securityScore: this.calculateSecurityScore(),
      lastUpdate: now,
    };

    // Generate tenant metrics
    const tenantMetrics = this.generateTenantMetrics();

    // Generate compliance status
    const complianceStatus = this.generateComplianceStatus();

    // Generate real-time chart data
    const realTimeChart = this.generateRealTimeChart();

    // Create dashboard data
    const dashboardData: SecurityDashboardData = {
      summary,
      activeAlerts: this.getActiveAlerts(),
      recentThreats: this.getRecentThreats(),
      tenantMetrics,
      complianceStatus,
      realTimeChart,
    };

    // Log dashboard update
    this.logDashboardUpdate(dashboardData);
  }

  private calculateSecurityScore(): number {
    if (this.events.length === 0) return 10.0;

    const recentEvents = this.events.filter(
      (e) => new Date(e.timestamp).getTime() > Date.now() - 24 * 60 * 60 * 1000
    );

    if (recentEvents.length === 0) return 9.5;

    // Calculate based on threat ratios
    const totalEvents = recentEvents.length;
    const highRiskEvents = recentEvents.filter((e) => e.riskScore > 0.7).length;
    const mediumRiskEvents = recentEvents.filter(
      (e) => e.riskScore > 0.4 && e.riskScore <= 0.7
    ).length;

    const highRiskRatio = highRiskEvents / totalEvents;
    const mediumRiskRatio = mediumRiskEvents / totalEvents;

    // Start with perfect score
    let score = 10.0;

    // Penalties based on risk ratios
    score -= highRiskRatio * 3.0; // High risk events cost 3 points
    score -= mediumRiskRatio * 1.5; // Medium risk events cost 1.5 points

    return Math.max(score, 5.0); // Minimum score of 5.0
  }

  private generateTenantMetrics(): TenantMetrics {
    const metrics: TenantMetrics = {};
    const tenantIds = Array.from(new Set(this.events.map((e) => e.tenantId)));

    tenantIds.forEach((tenantId) => {
      const tenantEvents = this.events.filter((e) => e.tenantId === tenantId);

      metrics[tenantId] = {
        totalOperations: tenantEvents.length,
        threatCount: tenantEvents.filter((e) => e.riskScore > 0.6).length,
        riskScore: this.calculateTenantRiskScore(tenantEvents),
        lastActivity:
          tenantEvents.length > 0
            ? new Date(
                Math.max(
                  ...tenantEvents.map((e) => new Date(e.timestamp).getTime())
                )
              )
            : new Date(),
        alerts: tenantEvents.slice(-5), // Last 5 events
      };
    });

    return metrics;
  }

  private calculateTenantRiskScore(events: SecurityEvent[]): number {
    if (events.length === 0) return 0.0;

    const recentEvents = events.filter(
      (e) => new Date(e.timestamp).getTime() > Date.now() - 6 * 60 * 60 * 1000 // Last 6 hours
    );

    if (recentEvents.length === 0) return 0.1;

    const avgRiskScore =
      recentEvents.reduce((sum, e) => sum + e.riskScore, 0) /
      recentEvents.length;
    const maxRiskScore = Math.max(...recentEvents.map((e) => e.riskScore));

    // Weighted average with emphasis on maximum risk
    return avgRiskScore * 0.7 + maxRiskScore * 0.3;
  }

  private generateComplianceStatus(): ComplianceStatus {
    const now = new Date();

    // LGPD compliance check
    const lgpdEvents = this.events.filter(
      (e) => e.metadata && e.metadata.lgpdRelevant && e.riskScore > 0.5
    );

    // GDPR compliance check
    const gdprEvents = this.events.filter(
      (e) => e.metadata && e.metadata.gdprRelevant && e.riskScore > 0.5
    );

    // Audit compliance check
    const auditEvents = this.events.filter(
      (e) => e.operation.includes("audit") || e.operation.includes("log")
    );

    return {
      lgpd: {
        status:
          lgpdEvents.length > 0
            ? lgpdEvents.some((e: SecurityEvent) => e.riskScore > 0.8)
              ? "violation"
              : "warning"
            : "compliant",
        events: lgpdEvents.length,
        lastCheck: now,
        score:
          lgpdEvents.length > 0
            ? lgpdEvents.some((e) => e.riskScore > 0.8)
              ? 3.0
              : 6.0
            : 9.0,
      },
      gdpr: {
        status:
          gdprEvents.length > 0
            ? gdprEvents.some((e) => e.riskScore > 0.8)
              ? "violation"
              : "warning"
            : "compliant",
        events: gdprEvents.length,
        lastCheck: now,
        score:
          gdprEvents.length > 0
            ? gdprEvents.some((e) => e.riskScore > 0.8)
              ? 3.0
              : 6.0
            : 9.0,
      },
      audit: {
        status: auditEvents.length > 0 ? "compliant" : "warning",
        events: auditEvents.length,
        lastCheck: now,
        score: 8.5,
      },
    };
  }

  private generateRealTimeChart(): RealTimeChartData {
    const now = Date.now();
    const timeLabels: string[] = [];
    const riskData: number[] = [];
    const eventData: number[] = [];

    // Generate data for last 30 minutes (5-minute intervals)
    for (let i = 5; i >= 0; i--) {
      const time = new Date(now - i * 5 * 60 * 1000);
      timeLabels.push(time.toLocaleTimeString("pt-BR"));

      const intervalStart = new Date(time.getTime() - 5 * 60 * 1000);
      const intervalEvents = this.events.filter((e) => {
        const eventTime = new Date(e.timestamp).getTime();
        return (
          eventTime >= intervalStart.getTime() && eventTime <= time.getTime()
        );
      });

      const avgRiskScore =
        intervalEvents.length > 0
          ? intervalEvents.reduce((sum, e) => sum + e.riskScore, 0) /
            intervalEvents.length
          : 0;

      riskData.push(Math.round(avgRiskScore * 100) / 100);
      eventData.push(intervalEvents.length);
    }

    return {
      labels: timeLabels,
      datasets: [
        {
          label: "Average Risk Score",
          data: riskData,
          borderColor: "#8884d8",
          backgroundColor: "#8884d840",
        },
        {
          label: "Event Count",
          data: eventData,
          borderColor: "#82ca9d",
          backgroundColor: "#82ca9d40",
        },
      ],
    };
  }

  private getActiveAlerts(): SecurityEvent[] {
    return this.events
      .filter((e) => e.riskScore >= this.config.highlightThreshold)
      .slice(-10); // Last 10 high-risk events
  }

  private getRecentThreats(): ThreatAnalysis[] {
    // Return mock threat analysis for recent events
    return this.events.slice(-5).map((event) => ({
      riskScore: event.riskScore,
      threatType: `potential_${event.operation}`,
      confidence: 0.8,
      recommendations: [
        `Monitor tenant ${event.tenantId}`,
        "Check access logs",
      ],
    }));
  }

  private logDashboardUpdate(data: SecurityDashboardData): void {
    const { summary } = data;

    console.log(
      `\n🛡️  Security Dashboard Update - ${new Date().toISOString()}`
    );
    console.log(`   📊 Total Events: ${summary.totalEvents}`);
    console.log(`   🚨 Total Alerts: ${summary.totalAlerts}`);
    console.log(`   🎯 Security Score: ${summary.securityScore}/10`);
    console.log(`   🔒 Threat Events: ${summary.threatEvents}`);
    console.log(`   🚫 Blocked Operations: ${summary.blockedOperations}`);

    // Log tenant summaries
    const tenantEntries = Object.entries(data.tenantMetrics);
    tenantEntries.forEach(([tenantId, metrics]) => {
      console.log(
        `   🏢 ${tenantId}: ${metrics.riskScore.toFixed(1)} risk score, ${
          metrics.threatCount
        } threats`
      );
    });
  }

  public getDashboardData(): SecurityDashboardData {
    this.generateMetrics();

    return {
      summary: {
        totalEvents: this.events.length,
        totalAlerts: this.events.filter((e) => e.riskScore > 0.7).length,
        threatEvents: this.events.filter((e) => e.riskScore > 0.8).length,
        blockedOperations: this.events.filter(
          (e) => e.alertLevel === AlertLevel.EMERGENCY
        ).length,
        securityScore: this.calculateSecurityScore(),
        lastUpdate: new Date(),
      },
      activeAlerts: this.getActiveAlerts(),
      recentThreats: this.getRecentThreats(),
      tenantMetrics: this.generateTenantMetrics(),
      complianceStatus: this.generateComplianceStatus(),
      realTimeChart: this.generateRealTimeChart(),
    };
  }

  public getSecurityMetrics(): SecurityMetric[] {
    return this.metrics.slice(-20); // Last 20 metrics
  }

  public getEventHistory(limit: number = 100): SecurityEvent[] {
    return this.events.slice(-limit);
  }

  public exportDashboardReport(): string {
    const data = this.getDashboardData();
    const report = [
      "# Security Dashboard Report",
      `Generated: ${new Date().toISOString()}`,
      "",
      "## Executive Summary",
      `- Security Score: ${data.summary.securityScore}/10`,
      `- Total Events: ${data.summary.totalEvents}`,
      `- Active Alerts: ${data.summary.totalAlerts}`,
      `- Threat Events: ${data.summary.threatEvents}`,
      ``,
      "## Tenant Status",
      ...Object.entries(data.tenantMetrics).map(
        ([tenant, metrics]) =>
          `- ${tenant}: ${metrics.riskScore.toFixed(1)} risk, ${
            metrics.threatCount
          } threats`
      ),
      ``,
      "## Compliance Status",
      `- LGPD: ${data.complianceStatus.lgpd.status} (${data.complianceStatus.lgpd.score}/10)`,
      `- GDPR: ${data.complianceStatus.gdpr.status} (${data.complianceStatus.gdpr.score}/10)`,
      `- Audit: ${data.complianceStatus.audit.status} (${data.complianceStatus.audit.score}/10)`,
      ``,
      "## Recent High-Risk Events",
      ...data.activeAlerts
        .slice(-5)
        .map(
          (alert, index) =>
            `${index + 1}. ${alert.tenantId} - ${
              alert.operation
            } (Risk: ${alert.riskScore.toFixed(1)})`
        ),
    ];

    return report.join("\n");
  }
}

// Singleton instance
export const securityDashboard = new SecurityDashboard();
