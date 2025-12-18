/**
 * Security score calculator for YAML parsing
 */
declare class SecurityScoreImpl implements SecurityScoreCalculator {
    private vulnerabilities;
    private hardeningFeatures;
    constructor();
    /**
     * Calcula o score de segurança completo
     */
    calculate(obj: any): SecurityScoreResult;
    /**
     * Analisa vulnerabilidades no objeto
     */
    private analyzeVulnerabilities;
    /**
     * Analisa injeção de código
     */
    private analyzeCodeInjection;
    /**
     * Analisa referências circulares
     */
    private analyzeCircularReferences;
    /**
     * Detecta referências circulares recursivamente
     */
    private detectCircularRecursive;
    /**
     * Analisa deep nesting
     */
    private analyzeDeepNesting;
    /**
     * Calcula profundidade máxima
     */
    private calculateMaxDepth;
    /**
     * Analisa vulnerabilidades de tamanho
     */
    private analyzeSizeVulnerabilities;
    /**
     * Calcula tamanho aproximado do objeto em bytes
     */
    private calculateObjectSize;
    /**
     * Analisa conteúdo malicioso
     */
    private analyzeMaliciousContent;
    /**
     * Analisa hardening implementado
     */
    private analyzeHardening;
    /**
     * Adiciona uma vulnerabilidade encontrada
     */
    private addVulnerability;
    /**
     * Adiciona uma feature de hardening
     */
    private addHardeningFeature;
    /**
     * Estima score CVSS baseado na severidade
     */
    private estimateCvssScore;
    /**
     * Calcula o score final de segurança
     */
    private calculateFinalScore;
    /**
     * Calcula impacto de uma vulnerabilidade
     */
    private impactForVulnerability;
    /**
     * Calcula o grau baseado no score
     */
    private calculateGrade;
    /**
     * Calcula a categoria baseada no grau
     */
    private calculateCategory;
    /**
     * Calcula o nível de risco baseado no score
     */
    private calculateRiskLevel;
    /**
     * Obtém recomendações baseadas no score
     */
    getRecommendations(score: number): string[];
    /**
     * Calcula a confiança no resultado
     */
    calculateConfidence(): number;
    /**
     * Calcula score de componente específico
     */
    calculateComponentScore(component: string): number;
    /**
     * Obtém CWE ID para tipos de vulnerabilidade
     */
    private getCweForVulnerability;
    /**
     * Reinicia o estado do calculador
     */
    private resetState;
}
export interface SecurityScoreResult {
    score: number;
    grade: SecurityGrade;
    category: SecurityCategory;
    vulnerabilities: SecurityVulnerability[];
    hardeningApplied: HardeningFeature[];
    recommendations: string[];
    riskLevel: RiskLevel;
    confidence: number;
}
export type SecurityGrade = 'A' | 'B' | 'C' | 'D' | 'F';
export type SecurityCategory = 'EXCEPTIONAL' | 'GOOD' | 'ACCEPTABLE' | 'LIMITED' | 'INSECURE';
export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export interface SecurityVulnerability {
    id: string;
    type: VulnerabilityType;
    severity: 'low' | 'medium' | 'high' | 'critical';
    description: string;
    path: string;
    remediation: string;
    cweId?: string;
    cvssScore?: number;
}
export interface HardeningFeature {
    name: string;
    status: 'applied' | 'partial' | 'not_applied';
    effectiveness: number;
    description: string;
}
export type VulnerabilityType = 'XSS' | 'SQL_INJECTION' | 'CODE_INJECTION' | 'TEMPLATE_INJECTION' | 'PATH_TRAVERSAL' | 'XXE' | 'LDAP_INJECTION' | 'COMMAND_INJECTION' | 'INSECURE_DESERIALIZATION' | 'CIRCULAR_REFERENCE' | 'DEEP_NESTING' | 'OVERSIZED_PAYLOAD' | 'CREDENTIAL_LEAK' | 'PII_EXPOSURE' | 'MALICIOUS_CONTENT';
export interface SecurityScoreCalculator {
    calculate(obj: any): SecurityScoreResult;
    calculateComponentScore(component: string): number;
    getRecommendations(score: number): string[];
    calculateConfidence(result: SecurityScoreResult): number;
}
/**
 * Função auxiliar para calcular segurança
 */
export declare function calculateSecurityScore(obj: any): SecurityScoreResult;
/**
 * Função auxiliar para obter recomendações
 */
export declare function getSecurityRecommendations(score: number): string[];
export { SecurityScoreImpl as SecurityScore };
//# sourceMappingURL=score.d.ts.map