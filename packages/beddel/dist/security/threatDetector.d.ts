export interface ThreatAnalysis {
    riskScore: number;
    threatType: string;
    confidence: number;
    recommendations: string[];
}
export declare class ThreatDetectionEngine {
    private patterns;
    private anomalyDetector;
    private mlModel;
    constructor();
    private initializePatterns;
    analyze(tenantId: string, operation: string, metadata: any): Promise<ThreatAnalysis>;
    private applyRiskFactors;
    private generateRecommendations;
    getStatistics(): any;
}
export declare class AnomalyDetector {
    private normalPatterns;
    private anomalyThreshold;
    private historicalData;
    constructor();
    private initializeHistoricalData;
    detectAnomaly(tenantId: string, operation: string, metadata: any): Promise<number>;
    private calculateAverageInterval;
    private getAverageSize;
}
export declare class ThreatMLModel {
    private modelWeights;
    private trainingData;
    private modelVersion;
    constructor();
    private initializeModel;
    private loadTrainingData;
    predict(tenantId: string, operation: string, metadata: any): Promise<number>;
    getModelInfo(): any;
    retrainModel(newData: any[]): void;
}
//# sourceMappingURL=threatDetector.d.ts.map