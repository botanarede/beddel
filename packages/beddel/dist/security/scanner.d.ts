/**
 * Security scanner for YAML parsing
 * Comprehensive vulnerability detection and security analysis
 */
export interface ScanResult {
    secure: boolean;
    score: number;
    grade: string;
    vulnerabilities: any[];
    warnings: string[];
    recommendations: string[];
    details: SecurityDetails;
}
export interface SecurityDetails {
    timestamp: number;
    objectId: string;
    size: number;
    depth: number;
    complexity: string;
    riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    scanDuration: number;
}
declare class SecurityScanner {
    private validator;
    private hardening;
    private scanHistory;
    constructor();
    /**
     * Executa scanning completo de segurança
     */
    scan(obj: any): Promise<ScanResult>;
    /**
     * Rápida validação de segurança
     */
    quickValidate(obj: any): {
        isValid: boolean;
        warnings: number;
        errors: number;
    };
    /**
     * Análise aprofundada de risco
     */
    analyzeRisk(obj: any): {
        riskLevel: string;
        factors: string[];
        score: number;
    };
    /**
     * Gera relatório de segurança
     */
    generateReport(obj: any): string;
    /**
     * Estatísticas do histórico de scans
     */
    getScanHistory(): {
        totalScans: number;
        averageScore: number;
        secureScans: number;
        insecureScans: number;
        averageRiskLevel: string;
    };
    /**
     * Extrai warnings dos resultados
     */
    private extractWarnings;
    /**
     * Estima tamanho do objeto
     */
    private estimateObjectSize;
    /**
     * Calcula profundidade máxima
     */
    private calculateMaxDepth;
    /**
     * Estima complexidade do objeto
     */
    private estimateComplexity;
    /**
     * Conta chaves totais
     */
    private countTotalKeys;
    /**
     * Gera ID único do objeto
     */
    private generateObjectId;
    /**
     * Formata bytes
     */
    private formatBytes;
    /**
     * Reinicializa o scanner
     */
    reset(): void;
}
/**
 * Função auxiliar para realizar scan rápido
 */
export declare function quickSecurityScan(obj: any): Promise<ScanResult>;
/**
 * Função auxiliar para validar segurança básica
 */
export declare function validateSecurityBasic(obj: any): boolean;
export { SecurityScanner as SecurityScanner };
//# sourceMappingURL=scanner.d.ts.map