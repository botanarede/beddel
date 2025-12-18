"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ThreatMLModel = exports.AnomalyDetector = exports.ThreatDetectionEngine = void 0;
class ThreatDetectionEngine {
    constructor() {
        this.patterns = new Map();
        this.initializePatterns();
        this.anomalyDetector = new AnomalyDetector();
        this.mlModel = new ThreatMLModel();
    }
    initializePatterns() {
        this.patterns.set("brute_force", /multiple_failed_attempts|rapid_login_sequence|authentication_failure|login_fail/i);
        this.patterns.set("sql_injection", /union.*select|drop.*table|exec.*\(.*\)|';.*--|xp_cmdshell|information_schema/i);
        this.patterns.set("data_exfiltration", /bulk.*export|mass.*download|unusual.*access|data.*leak|unauthorized.*download/i);
        this.patterns.set("cross_tenant", /cross.*tenant|tenant.*injection|unauthorized.*access|tenant.*spoofing|bypass.*isolation/i);
        this.patterns.set("lgpd_violation", /unauthorized.*data|consent.*violation|retention.*breach|right.*to.*be.*forgotten|data.*portability/i);
        this.patterns.set("ddos_attack", /flood.*attack|denial.*of.*service|rate.*limit.*bypass|connection.*flood/i);
        this.patterns.set("privilege_escalation", /privilege.*escalation|permission.*bypass|role.*elevation|admin.*bypass/i);
        this.patterns.set("malware_detection", /malware|virus|trojan|ransomware|backdoor|rootkit/i);
    }
    async analyze(tenantId, operation, metadata) {
        let riskScore = 0.1; // Base risk score
        let threatType = "low_risk";
        let confidence = 0.9;
        // Pattern matching detection
        for (const [patternName, pattern] of this.patterns) {
            if (pattern.test(operation) || pattern.test(JSON.stringify(metadata))) {
                switch (patternName) {
                    case "brute_force":
                        riskScore += 0.4;
                        break;
                    case "sql_injection":
                        riskScore += 0.6;
                        break;
                    case "data_exfiltration":
                        riskScore += 0.8;
                        break;
                    case "cross_tenant":
                        riskScore += 0.9;
                        break;
                    case "lgpd_violation":
                        riskScore += 0.7;
                        break;
                    case "ddos_attack":
                        riskScore += 0.5;
                        break;
                    case "privilege_escalation":
                        riskScore += 0.7;
                        break;
                    case "malware_detection":
                        riskScore += 0.8;
                        break;
                    default:
                        riskScore += 0.3;
                }
                threatType = patternName;
                break;
            }
        }
        // Machine learning based anomaly detection
        const mlScore = await this.mlModel.predict(tenantId, operation, metadata);
        riskScore += mlScore;
        // Time-based anomaly detection
        const anomalyScore = await this.anomalyDetector.detectAnomaly(tenantId, operation, metadata);
        riskScore += anomalyScore * 0.3;
        // Apply additional risk factors
        riskScore = this.applyRiskFactors(riskScore, tenantId, metadata);
        // Cap risk score at maximum of 1.0
        riskScore = Math.min(riskScore, 1.0);
        const recommendations = this.generateRecommendations(riskScore, threatType, tenantId);
        return {
            riskScore,
            threatType,
            confidence,
            recommendations,
        };
    }
    applyRiskFactors(riskScore, tenantId, metadata) {
        // Increase risk for operations during unusual hours
        const hour = new Date().getHours();
        if (hour < 6 || hour > 22) {
            riskScore += 0.15; // Night operations increase risk
        }
        // Increase risk for bulk operations
        if (metadata && metadata.count && metadata.count > 1000) {
            riskScore += 0.2;
        }
        // Increase risk for unauthorized access attempts
        if (metadata && metadata.isUnauthorized) {
            riskScore += 0.25;
        }
        // Increase risk for cross-tenant operations
        if (metadata &&
            metadata.targetTenant &&
            metadata.targetTenant !== tenantId) {
            riskScore += 0.3;
        }
        // Increase risk for operations without proper consent
        if (metadata && metadata.consentStatus === "missing") {
            riskScore += 0.4;
        }
        return Math.min(riskScore, 1.0);
    }
    generateRecommendations(riskScore, threatType, tenantId) {
        const recommendations = [];
        // Critical threats (>0.8)
        if (riskScore > 0.8) {
            recommendations.push("🚨 EMERGENCY: Immediate action required");
            recommendations.push(`Isolate tenant ${tenantId} immediately`);
            recommendations.push("Contact security team NOW");
            recommendations.push("Preserve audit logs");
            recommendations.push(`Potential ${threatType} attack detected`);
        }
        // High threats (>0.6)
        else if (riskScore > 0.6) {
            recommendations.push("⚠️  CRITICAL: Investigate immediately");
            recommendations.push(`Block suspicious activities from tenant ${tenantId}`);
            recommendations.push("Monitor all operations from this tenant");
            recommendations.push("Notify security team within 5 minutes");
            recommendations.push(`Check for ${threatType} indicators`);
        }
        // Medium threats (>0.4)
        else if (riskScore > 0.4) {
            recommendations.push("⚠️  WARNING: Monitor closely");
            recommendations.push(`Increase monitoring for tenant ${tenantId}`);
            recommendations.push("Check access patterns");
            recommendations.push("Review permissions");
            recommendations.push(`Investigate ${threatType} patterns`);
        }
        // Low threats (>0.2)
        else if (riskScore > 0.2) {
            recommendations.push("ℹ️  INFO: Routine observation");
            recommendations.push("Document the pattern");
            recommendations.push("Check if pattern repeats");
            recommendations.push(`Normal monitoring for ${threatType}`);
        }
        // Very low threats
        else {
            recommendations.push("✅ Normal activity");
            recommendations.push("Continue regular monitoring");
            recommendations.push("No special actions required");
        }
        return recommendations;
    }
    getStatistics() {
        return {
            patternsLoaded: this.patterns.size,
            lastUpdate: new Date().toISOString(),
            mlModelVersion: "2025.1.0",
            detectorVersion: "v3.0",
            threatTypes: Array.from(this.patterns.keys()),
        };
    }
}
exports.ThreatDetectionEngine = ThreatDetectionEngine;
class AnomalyDetector {
    constructor() {
        this.normalPatterns = new Map();
        this.anomalyThreshold = 2.5;
        this.historicalData = new Map();
        this.initializeHistoricalData();
    }
    initializeHistoricalData() {
        // Initialize with some baseline patterns
        const baselineTenants = ["tenant-alpha", "tenant-beta", "tenant-gamma"];
        baselineTenants.forEach((tenantId) => {
            this.historicalData.set(tenantId, {
                timestamps: [],
                operations: [],
            });
        });
    }
    async detectAnomaly(tenantId, operation, metadata) {
        const key = `${tenantId}:${operation}`;
        const currentTime = new Date().getTime();
        // Initialize if not exists
        if (!this.normalPatterns.has(key)) {
            this.normalPatterns.set(key, []);
        }
        const patterns = this.normalPatterns.get(key);
        // Advanced anomaly detection
        let anomalyScore = 0.0;
        // 1. Velocity-based anomaly detection
        if (patterns.length > 5) {
            const recentTimestamps = patterns.slice(-5).map((p) => p.timestamp);
            const avgTimeInterval = this.calculateAverageInterval(recentTimestamps);
            if (avgTimeInterval > 0) {
                const currentTimeInterval = currentTime - recentTimestamps[recentTimestamps.length - 1];
                const deviation = Math.abs(currentTimeInterval - avgTimeInterval) / avgTimeInterval;
                if (deviation > 3.0) {
                    anomalyScore += 0.4; // High velocity anomaly
                }
                else if (deviation > 1.5) {
                    anomalyScore += 0.2; // Medium velocity anomaly
                }
            }
        }
        // 2. Pattern-based anomaly detection
        if (metadata && metadata.size) {
            const historicalData = this.historicalData.get(tenantId);
            if (historicalData) {
                const avgSize = this.getAverageSize(historicalData.operations);
                const currentSize = metadata.size;
                if (currentSize > avgSize * 100) {
                    anomalyScore += 0.3; // Unusual data size
                }
            }
        }
        // 3. Time-based anomaly detection
        const hour = new Date().getHours();
        if (hour < 6 || hour > 22) {
            anomalyScore += 0.15; // Night operations are more suspicious
        }
        // 4. Cross-tenant anomaly detection
        if (metadata &&
            metadata.targetTenant &&
            metadata.targetTenant !== tenantId) {
            anomalyScore += 0.25; // Cross-tenant operations are high risk
        }
        // Store current pattern for future comparison
        patterns.push({
            timestamp: currentTime,
            operation,
            metadata,
        });
        // Keep only recent patterns (last 24 hours)
        const cutoff = currentTime - 24 * 60 * 60 * 1000;
        this.normalPatterns.set(key, patterns.filter((p) => p.timestamp > cutoff));
        return Math.min(anomalyScore, 0.8);
    }
    calculateAverageInterval(timestamps) {
        if (timestamps.length < 2)
            return 0;
        let totalInterval = 0;
        for (let i = 1; i < timestamps.length; i++) {
            totalInterval += timestamps[i] - timestamps[i - 1];
        }
        return totalInterval / (timestamps.length - 1);
    }
    getAverageSize(operations) {
        if (operations.length === 0)
            return 0;
        return 1000; // Default average size
    }
}
exports.AnomalyDetector = AnomalyDetector;
class ThreatMLModel {
    constructor() {
        this.modelWeights = new Map();
        this.trainingData = new Map();
        this.modelVersion = "2025.1.0";
        this.initializeModel();
        this.loadTrainingData();
    }
    initializeModel() {
        // Advanced ML model weights based on tenant behavior patterns
        this.modelWeights.set("tenant_historical_risk", 0.35);
        this.modelWeights.set("operation_frequency_anomaly", 0.25);
        this.modelWeights.set("metadata_complexity_risk", 0.2);
        this.modelWeights.set("time_deviation_risk", 0.15);
        this.modelWeights.set("cross_tenant_detection", 0.4);
        this.modelWeights.set("lgpd_compliance_checker", 0.3);
    }
    loadTrainingData() {
        // Load historical training data
        const sampleTrainingData = [
            {
                tenantId: "tenant-alpha",
                operation: "normal_access",
                metadata: { size: 100 },
                riskScore: 0.1,
            },
            {
                tenantId: "tenant-beta",
                operation: "bulk_export",
                metadata: { size: 10000 },
                riskScore: 0.8,
            },
            {
                tenantId: "tenant-gamma",
                operation: "cross_tenant_access",
                metadata: { targetTenant: "other" },
                riskScore: 0.9,
            },
        ];
        sampleTrainingData.forEach((data) => {
            const key = `${data.tenantId}:${data.operation}`;
            this.trainingData.set(key, [data]);
        });
    }
    async predict(tenantId, operation, metadata) {
        let riskScore = 0.0;
        // 1. Historical tenant behavior analysis
        const historicalKey = `${tenantId}:${operation}`;
        if (this.trainingData.has(historicalKey)) {
            const historicalData = this.trainingData.get(historicalKey);
            const avgRisk = historicalData.reduce((sum, data) => sum + data.riskScore, 0) /
                historicalData.length;
            riskScore += avgRisk * this.modelWeights.get("tenant_historical_risk");
        }
        // 2. Operation frequency analysis
        const hour = new Date().getHours();
        if (hour < 6 || hour > 22) {
            riskScore += 0.3 * this.modelWeights.get("time_deviation_risk");
        }
        // 3. Metadata complexity analysis
        if (metadata && JSON.stringify(metadata).length > 2000) {
            riskScore += 0.2 * this.modelWeights.get("metadata_complexity_risk");
        }
        // 4. Cross-tenant operation detection
        if (metadata &&
            metadata.targetTenant &&
            metadata.targetTenant !== tenantId) {
            riskScore += 0.8 * this.modelWeights.get("cross_tenant_detection");
        }
        // 5. LGPD compliance violation detection
        if (metadata && metadata.consentStatus === "missing") {
            riskScore += 0.6 * this.modelWeights.get("lgpd_compliance_checker");
        }
        // 6. High-frequency operation detection
        if (metadata && metadata.operationCount && metadata.operationCount > 1000) {
            riskScore += 0.3 * this.modelWeights.get("operation_frequency_anomaly");
        }
        return Math.min(riskScore, 1.0);
    }
    getModelInfo() {
        return {
            version: this.modelVersion,
            weights: Object.fromEntries(this.modelWeights),
            trainingDataSize: this.trainingData.size,
            features: [
                "tenant_historical_risk",
                "operation_frequency_anomaly",
                "metadata_complexity_risk",
                "time_deviation_risk",
                "cross_tenant_detection",
                "lgpd_compliance_checker",
            ],
        };
    }
    retrainModel(newData) {
        // Simplified retraining logic
        newData.forEach((data) => {
            const key = `${data.tenantId}:${data.operation}`;
            if (!this.trainingData.has(key)) {
                this.trainingData.set(key, []);
            }
            this.trainingData.get(key).push(data);
        });
        this.modelVersion = `2025.${new Date().getMonth()}.${new Date().getDate()}`;
    }
}
exports.ThreatMLModel = ThreatMLModel;
//# sourceMappingURL=threatDetector.js.map