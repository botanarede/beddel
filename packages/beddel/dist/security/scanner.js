"use strict";
/**
 * Security scanner for YAML parsing
 * Comprehensive vulnerability detection and security analysis
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.SecurityScanner = void 0;
exports.quickSecurityScan = quickSecurityScan;
exports.validateSecurityBasic = validateSecurityBasic;
const score_1 = require("./score");
const validation_1 = require("./validation");
const hardening_1 = require("./hardening");
class SecurityScanner {
    constructor() {
        this.scanHistory = [];
        this.validator = new validation_1.SecurityValidator();
        this.hardening = (0, hardening_1.createSecurityHardening)();
    }
    /**
     * Executa scanning completo de segurança
     */
    async scan(obj) {
        const startTime = Date.now();
        // Validação de segurança básica
        const validationResult = this.validator.validateObject(obj);
        // Cálculo de score de segurança
        const securityScore = (0, score_1.calculateSecurityScore)(obj);
        // Aplica hardening e detecção
        const hardeningResult = this.hardening.harden(obj);
        // Verifica se é seguro
        const isSecure = validationResult.valid && hardeningResult.secure && securityScore.score >= 60;
        // Monta resultado final
        const result = {
            secure: isSecure,
            score: securityScore.score,
            grade: securityScore.grade,
            vulnerabilities: securityScore.vulnerabilities,
            warnings: this.extractWarnings(validationResult, securityScore),
            recommendations: securityScore.recommendations,
            details: {
                timestamp: Date.now(),
                objectId: this.generateObjectId(obj),
                size: this.estimateObjectSize(obj),
                depth: this.calculateMaxDepth(obj),
                complexity: this.estimateComplexity(obj),
                riskLevel: securityScore.riskLevel,
                scanDuration: Date.now() - startTime
            }
        };
        // Adiciona ao histórico
        this.scanHistory.push(result);
        // Mantém apenas os últimos 50 scans
        if (this.scanHistory.length > 50) {
            this.scanHistory = this.scanHistory.slice(-50);
        }
        return result;
    }
    /**
     * Rápida validação de segurança
     */
    quickValidate(obj) {
        const result = this.validator.validateObject(obj);
        return {
            isValid: result.valid,
            warnings: result.warnings.length,
            errors: result.errors.length
        };
    }
    /**
     * Análise aprofundada de risco
     */
    analyzeRisk(obj) {
        const securityScore = (0, score_1.calculateSecurityScore)(obj);
        const riskFactors = [];
        if (securityScore.score < 70) {
            riskFactors.push('Low security score');
        }
        if (securityScore.vulnerabilities.length > 0) {
            riskFactors.push('Active vulnerabilities detected');
        }
        if (securityScore.vulnerabilities.some(v => v.severity === 'high' || v.severity === 'critical')) {
            riskFactors.push('High/critical severity vulnerabilities');
        }
        const validation = this.validator.validateObject(obj);
        if (!validation.valid) {
            riskFactors.push('Security validation failures');
        }
        if (validation.stats.maxDepth > 500) {
            riskFactors.push('Deep object nesting detected');
        }
        if (validation.stats.totalKeys > 10000) {
            riskFactors.push('Large object size');
        }
        return {
            riskLevel: securityScore.riskLevel,
            factors: riskFactors,
            score: securityScore.score
        };
    }
    /**
     * Gera relatório de segurança
     */
    generateReport(obj) {
        const securityScore = (0, score_1.calculateSecurityScore)(obj);
        let report = '=== SECURITY SCAN REPORT ===\n\n';
        report += `✅ Status: ${securityScore.score >= 60 ? 'SECURE' : 'INSECURE'}\n`;
        report += `📊 Score: ${securityScore.score}/100 (${securityScore.grade})\n`;
        report += `🎯 Risk Level: ${securityScore.riskLevel}\n`;
        report += `📦 Object Size: ${this.formatBytes(this.estimateObjectSize(obj))}\n`;
        report += `📐 Max Depth: ${this.calculateMaxDepth(obj)}\n\n`;
        if (securityScore.vulnerabilities.length > 0) {
            report += '🔴 VULNERABILITIES DETECTED:\n';
            securityScore.vulnerabilities.forEach(vuln => {
                report += `  • [${vuln.severity.toUpperCase()}] ${vuln.type}: ${vuln.description}\n`;
                report += `    Path: ${vuln.path}\n`;
                report += `    CWE: ${vuln.cweId}\n`;
                report += `    Fix: ${vuln.remediation}\n\n`;
            });
        }
        if (securityScore.recommendations.length > 0) {
            report += '💡 RECOMMENDATIONS:\n';
            securityScore.recommendations.forEach(rec => {
                report += `  • ${rec}\n`;
            });
            report += '\n';
        }
        const stats = this.validator.validateObject(obj).stats;
        report += '📈 STATISTICS:\n';
        report += `  • Total Keys: ${stats.totalKeys}\n`;
        report += `  • Max Value Length: ${stats.maxValueLength} bytes\n`;
        report += `  • Data Types: ${Object.entries(stats.dataTypes)
            .map(([type, count]) => `${type}: ${count}`)
            .join(', ')}\n`;
        report += `\n🎯 Confidence: ${securityScore.confidence}%\n`;
        return report;
    }
    /**
     * Estatísticas do histórico de scans
     */
    getScanHistory() {
        if (this.scanHistory.length === 0) {
            return {
                totalScans: 0,
                averageScore: 0,
                secureScans: 0,
                insecureScans: 0,
                averageRiskLevel: 'UNKNOWN'
            };
        }
        const totalScans = this.scanHistory.length;
        const secureScans = this.scanHistory.filter(s => s.secure).length;
        const averageScore = this.scanHistory.reduce((sum, s) => sum + s.score, 0) / totalScans;
        // Calcula risco médio
        const riskOrder = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
        const riskScores = this.scanHistory.map(s => riskOrder.indexOf(s.details.riskLevel));
        const avgRiskIndex = Math.round(riskScores.reduce((a, b) => a + b) / totalScans);
        const averageRiskLevel = riskOrder[Math.min(avgRiskIndex, riskOrder.length - 1)];
        return {
            totalScans,
            averageScore: Math.round(averageScore),
            secureScans,
            insecureScans: totalScans - secureScans,
            averageRiskLevel
        };
    }
    /**
     * Extrai warnings dos resultados
     */
    extractWarnings(validationResult, securityScore) {
        const warnings = [];
        // Warnings da validação
        validationResult.warnings?.forEach((warning) => {
            warnings.push(`${warning.path}: ${warning.message}`);
        });
        // Warnings do score de segurança
        if (securityScore.score < 80) {
            warnings.push(`Low security score: ${securityScore.score}/100`);
        }
        if (securityScore.vulnerabilities.length > 0) {
            warnings.push(`${securityScore.vulnerabilities.length} vulnerabilities detected`);
        }
        return warnings;
    }
    /**
     * Estima tamanho do objeto
     */
    estimateObjectSize(obj) {
        try {
            return JSON.stringify(obj).length * 2; // UTF-16 chars
        }
        catch {
            return 0;
        }
    }
    /**
     * Calcula profundidade máxima
     */
    calculateMaxDepth(obj) {
        const calculateDepth = (current, depth = 0) => {
            if (typeof current !== 'object' || current === null) {
                return depth;
            }
            let maxDepth = depth;
            for (const value of Object.values(current)) {
                maxDepth = Math.max(maxDepth, calculateDepth(value, depth + 1));
            }
            return maxDepth;
        };
        return calculateDepth(obj);
    }
    /**
     * Estima complexidade do objeto
     */
    estimateComplexity(obj) {
        const depth = this.calculateMaxDepth(obj);
        const keys = this.countTotalKeys(obj);
        if (depth > 500 || keys > 5000)
            return 'very_high';
        if (depth > 200 || keys > 1000)
            return 'high';
        if (depth > 100 || keys > 500)
            return 'medium';
        return 'low';
    }
    /**
     * Conta chaves totais
     */
    countTotalKeys(obj) {
        const countKeys = (current) => {
            if (typeof current !== 'object' || current === null) {
                return 0;
            }
            if (Array.isArray(current)) {
                return current.reduce((sum, item) => sum + countKeys(item), 0);
            }
            let total = Object.keys(current).length;
            for (const value of Object.values(current)) {
                total += countKeys(value);
            }
            return total;
        };
        return countKeys(obj);
    }
    /**
     * Gera ID único do objeto
     */
    generateObjectId(obj) {
        try {
            const str = JSON.stringify(obj);
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                const char = str.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash; // Converte para inteiro de 32 bits
            }
            return Math.abs(hash).toString(36);
        }
        catch {
            return 'unknown';
        }
    }
    /**
     * Formata bytes
     */
    formatBytes(bytes) {
        if (bytes < 1024)
            return `${bytes}B`;
        if (bytes < 1024 * 1024)
            return `${(bytes / 1024).toFixed(2)}KB`;
        return `${(bytes / (1024 * 1024)).toFixed(2)}MB`;
    }
    /**
     * Reinicializa o scanner
     */
    reset() {
        this.scanHistory = [];
        this.validator = new validation_1.SecurityValidator();
        this.hardening = (0, hardening_1.createSecurityHardening)();
    }
}
exports.SecurityScanner = SecurityScanner;
/**
 * Função auxiliar para realizar scan rápido
 */
async function quickSecurityScan(obj) {
    const scanner = new SecurityScanner();
    return await scanner.scan(obj);
}
/**
 * Função auxiliar para validar segurança básica
 */
function validateSecurityBasic(obj) {
    const scanner = new SecurityScanner();
    const validator = new validation_1.SecurityValidator();
    const result = validator.validateObject(obj);
    return result.valid;
}
//# sourceMappingURL=scanner.js.map