/**
 * Security scanner for YAML parsing
 * Comprehensive vulnerability detection and security analysis
 */

import { SecurityScoreResult, calculateSecurityScore } from './score';
import { SecurityValidator } from './validation';
import { SecurityHardening, createSecurityHardening } from './hardening';

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

class SecurityScanner {
  private validator: SecurityValidator;
  private hardening: SecurityHardening;
  private scanHistory: ScanResult[] = [];

  constructor() {
    this.validator = new SecurityValidator();
    this.hardening = createSecurityHardening();
  }

  /**
   * Executa scanning completo de segurança
   */
  public async scan(obj: any): Promise<ScanResult> {
    const startTime = Date.now();
    
    // Validação de segurança básica
    const validationResult = this.validator.validateObject(obj);
    
    // Cálculo de score de segurança
    const securityScore = calculateSecurityScore(obj);
    
    // Aplica hardening e detecção
    const hardeningResult = this.hardening.harden(obj);
    
    // Verifica se é seguro
    const isSecure = validationResult.valid && hardeningResult.secure && securityScore.score >= 60;
    
    // Monta resultado final
    const result: ScanResult = {
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
  public quickValidate(obj: any): { isValid: boolean; warnings: number; errors: number } {
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
  public analyzeRisk(obj: any): { riskLevel: string; factors: string[]; score: number } {
    const securityScore = calculateSecurityScore(obj);
    
    const riskFactors: string[] = [];
    
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
  public generateReport(obj: any): string {
    const securityScore = calculateSecurityScore(obj);
    
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
  public getScanHistory(): { 
    totalScans: number; 
    averageScore: number; 
    secureScans: number; 
    insecureScans: number;
    averageRiskLevel: string;
  } {
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
  private extractWarnings(validationResult: any, securityScore: SecurityScoreResult): string[] {
    const warnings: string[] = [];
    
    // Warnings da validação
    validationResult.warnings?.forEach((warning: any) => {
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
  private estimateObjectSize(obj: any): number {
    try {
      return JSON.stringify(obj).length * 2; // UTF-16 chars
    } catch {
      return 0;
    }
  }

  /**
   * Calcula profundidade máxima
   */
  private calculateMaxDepth(obj: any): number {
    const calculateDepth = (current: any, depth = 0): number => {
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
  private estimateComplexity(obj: any): string {
    const depth = this.calculateMaxDepth(obj);
    const keys = this.countTotalKeys(obj);
    
    if (depth > 500 || keys > 5000) return 'very_high';
    if (depth > 200 || keys > 1000) return 'high';
    if (depth > 100 || keys > 500) return 'medium';
    return 'low';
  }

  /**
   * Conta chaves totais
   */
  private countTotalKeys(obj: any): number {
    const countKeys = (current: any): number => {
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
  private generateObjectId(obj: any): string {
    try {
      const str = JSON.stringify(obj);
      let hash = 0;
      for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Converte para inteiro de 32 bits
      }
      return Math.abs(hash).toString(36);
    } catch {
      return 'unknown';
    }
  }

  /**
   * Formata bytes
   */
  private formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)}MB`;
  }

  /**
   * Reinicializa o scanner
   */
  public reset(): void {
    this.scanHistory = [];
    this.validator = new SecurityValidator();
    this.hardening = createSecurityHardening();
  }
}

/**
 * Função auxiliar para realizar scan rápido
 */
export async function quickSecurityScan(obj: any): Promise<ScanResult> {
  const scanner = new SecurityScanner();
  return await scanner.scan(obj);
}

/**
 * Função auxiliar para validar segurança básica
 */
export function validateSecurityBasic(obj: any): boolean {
  const scanner = new SecurityScanner();
  const validator = new SecurityValidator();
  const result = validator.validateObject(obj);
  return result.valid;
}

export { SecurityScanner as SecurityScanner };
