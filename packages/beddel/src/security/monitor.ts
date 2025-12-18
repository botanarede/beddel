import { EventEmitter } from "events";
import { AuditTrail } from "../audit/auditTrail";
import { runtimeConfig } from "../config";

export interface SecurityEvent {
  id: string;
  tenantId: string;
  operation: string;
  metadata: any;
  timestamp: Date;
  riskScore: number;
  alertLevel: AlertLevel;
}

export enum AlertLevel {
  INFO = "info",
  WARNING = "warning",
  CRITICAL = "critical",
  EMERGENCY = "emergency",
}

export interface ThreatAnalysis {
  riskScore: number;
  threatType: string;
  confidence: number;
  recommendations: string[];
}

export class SecurityMonitor extends EventEmitter {
  private static instance: SecurityMonitor;
  private threatDetector: ThreatDetectionEngine;
  private alertManager: AlertManager;
  private metricsCollector: MetricsCollector;
  private isMonitoring: boolean = false;
  private auditTrail: AuditTrail;
  private securityConfig: any;

  constructor() {
    super();
    this.threatDetector = new ThreatDetectionEngine();
    this.alertManager = new AlertManager();
    this.metricsCollector = new MetricsCollector();
    this.auditTrail = new AuditTrail();
    this.securityConfig = {
      alertThreshold: runtimeConfig.securityScore >= 9.5 ? 0.7 : 0.6,
    };
  }

  static getInstance(): SecurityMonitor {
    if (!SecurityMonitor.instance) {
      SecurityMonitor.instance = new SecurityMonitor();
    }
    return SecurityMonitor.instance;
  }

  public startMonitoring(): void {
    if (this.isMonitoring) {
      return;
    }

    this.isMonitoring = true;
    this.emit("monitoringStarted", { timestamp: new Date() });
    this.logEvent("system", "monitoring_started", { version: "2025.1.0" });
  }

  public stopMonitoring(): void {
    if (!this.isMonitoring) {
      return;
    }

    this.isMonitoring = false;
    this.emit("monitoringStopped", { timestamp: new Date() });
    this.logEvent("system", "monitoring_stopped", { reason: "manual" });
  }

  public isMonitoringActive(): boolean {
    return this.isMonitoring;
  }

  public async monitorActivity(
    tenantId: string,
    operation: string,
    metadata: any
  ): Promise<SecurityEvent> {
    if (!this.isMonitoring) {
      throw new Error("Security monitoring is not active");
    }

    const eventId = this.generateEventId();
    const timestamp = new Date();

    // Perform threat analysis
    const threatAnalysis = await this.threatDetector.analyze(
      tenantId,
      operation,
      metadata
    );

    const securityEvent: SecurityEvent = {
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

  private generateEventId(): string {
    return `sec-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  private determineAlertLevel(riskScore: number): AlertLevel {
    if (riskScore >= 0.9) return AlertLevel.EMERGENCY;
    if (riskScore >= 0.7) return AlertLevel.CRITICAL;
    if (riskScore >= 0.4) return AlertLevel.WARNING;
    return AlertLevel.INFO;
  }

  private async logSecurityEvent(event: SecurityEvent): Promise<void> {
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

  private async triggerSecurityAlert(event: SecurityEvent): Promise<void> {
    await this.alertManager.sendAlert(event);
    this.emit("securityAlert", event);
  }

  public async logEvent(
    tenantId: string,
    operation: string,
    metadata: any,
    riskScore: number = 0.1
  ): Promise<SecurityEvent> {
    return this.monitorActivity(tenantId, operation, metadata);
  }

  public getMetrics() {
    return this.metricsCollector.getMetrics();
  }

  public getThreatStatistics() {
    return this.threatDetector.getStatistics();
  }
}

// Supporting Classes

export class ThreatDetectionEngine {
  private patterns: Map<string, RegExp> = new Map();
  private anomalyDetector: AnomalyDetector;
  private mlModel: ThreatMLModel;

  constructor() {
    this.initializePatterns();
    this.anomalyDetector = new AnomalyDetector();
    this.mlModel = new ThreatMLModel();
  }

  private initializePatterns(): void {
    this.patterns.set(
      "brute_force",
      /multiple_failed_attempts|rapid_login_sequence/i
    );
    this.patterns.set(
      "sql_injection",
      /union.*select|drop.*table|exec.*\(.*\)/i
    );
    this.patterns.set(
      "data_exfiltration",
      /bulk.*export|mass.*download|unusual.*access/i
    );
    this.patterns.set(
      "cross_tenant",
      /cross.*tenant|tenant.*injection|unauthorized.*access/i
    );
    this.patterns.set(
      "lgpd_violation",
      /unauthorized.*data|consent.*violation|retention.*breach/i
    );
  }

  public async analyze(
    tenantId: string,
    operation: string,
    metadata: any
  ): Promise<ThreatAnalysis> {
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
    const anomalyScore = await this.anomalyDetector.detectAnomaly(
      tenantId,
      operation,
      metadata
    );
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

  private generateRecommendations(
    riskScore: number,
    threatType: string
  ): string[] {
    const recommendations: string[] = [];

    if (riskScore > 0.7) {
      recommendations.push("Immediate investigation required");
      recommendations.push("Consider tenant isolation");
      recommendations.push("Notify security team");
    } else if (riskScore > 0.4) {
      recommendations.push("Monitor closely");
      recommendations.push("Check access logs");
      recommendations.push("Review permissions");
    } else {
      recommendations.push("Routine monitoring");
      recommendations.push("Document pattern");
    }

    return recommendations;
  }

  public getStatistics() {
    return {
      patternsLoaded: this.patterns.size,
      lastUpdate: new Date().toISOString(),
      mlModelVersion: "2025.1.0",
    };
  }
}

export class AnomalyDetector {
  private normalPatterns: Map<string, any[]> = new Map();
  private anomalyThreshold: number = 2.5;

  public async detectAnomaly(
    tenantId: string,
    operation: string,
    metadata: any
  ): Promise<number> {
    const key = `${tenantId}:${operation}`;
    const currentTime = new Date().getTime();

    if (!this.normalPatterns.has(key)) {
      this.normalPatterns.set(key, []);
    }

    const patterns = this.normalPatterns.get(key)!;

    // Simple time-based anomaly detection
    if (patterns.length > 10) {
      const timeInterval =
        currentTime - patterns[patterns.length - 1].timestamp;

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

      const avgInterval =
        intervals.reduce((a, b) => a + b, 0) / intervals.length;
      const currentDeviation =
        Math.abs(timeInterval - avgInterval) / avgInterval;

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
    this.normalPatterns.set(
      key,
      patterns.filter((p) => p.timestamp > cutoff)
    );

    return 0.0; // Normal behavior
  }
}

export class ThreatMLModel {
  private modelWeights: Map<string, number> = new Map();

  constructor() {
    this.initializeModel();
  }

  private initializeModel(): void {
    // Simplified ML model weights
    this.modelWeights.set("tenant_historical_access", 0.3);
    this.modelWeights.set("operation_frequency", 0.4);
    this.modelWeights.set("metadata_complexity", 0.2);
    this.modelWeights.set("time_based_anomaly", 0.1);
  }

  public async predict(
    tenantId: string,
    operation: string,
    metadata: any
  ): Promise<number> {
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

export class AlertManager {
  private alertHistory: Map<string, SecurityEvent[]> = new Map();
  private readonly MAX_ALERTS_PER_TENANT = 100;

  public async sendAlert(event: SecurityEvent): Promise<void> {
    const key = event.tenantId;

    if (!this.alertHistory.has(key)) {
      this.alertHistory.set(key, []);
    }

    const alerts = this.alertHistory.get(key)!;
    alerts.push(event);

    // Keep only recent alerts
    if (alerts.length > this.MAX_ALERTS_PER_TENANT) {
      alerts.shift();
    }

    // Log the alert
    console.warn(
      `[SECURITY_ALERT] Tenant: ${event.tenantId}, Risk: ${event.riskScore}, Operation: ${event.operation}`
    );
  }

  public getAlertHistory(tenantId: string): SecurityEvent[] {
    return this.alertHistory.get(tenantId) || [];
  }

  public getAlertSummary(): Record<string, any> {
    const summary: Record<string, any> = {};
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

export class MetricsCollector {
  private metrics: any = {
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

  public recordEvent(event: SecurityEvent): void {
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

  public getMetrics(): any {
    return {
      ...this.metrics,
      alertRate:
        this.metrics.totalEvents > 0
          ? this.metrics.totalAlerts / this.metrics.totalEvents
          : 0,
    };
  }

  public resetMetrics(): void {
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

// Export singleton instance
export const securityMonitor = SecurityMonitor.getInstance();
