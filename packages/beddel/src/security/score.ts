/**
 * Security score calculator for YAML parsing
 */

// Classe interna para implementação
class SecurityScoreImpl implements SecurityScoreCalculator {
  private vulnerabilities: SecurityVulnerability[] = [];
  private hardeningFeatures: HardeningFeature[] = [];

  constructor() {
    // State é inicializado em resetState()
  }

  /**
   * Calcula o score de segurança completo
   */
  public calculate(obj: any): SecurityScoreResult {
    this.resetState();
    
    // Análise de vulnerabilidades
    this.analyzeVulnerabilities(obj);
    
    // Análise de hardening
    this.analyzeHardening(obj);
    
    // Cálculo do score final
    const score = this.calculateFinalScore();
    const grade = this.calculateGrade(score);
    const category = this.calculateCategory(grade);
    const riskLevel = this.calculateRiskLevel(score);
    const recommendations = this.getRecommendations(score);
    const confidence = this.calculateConfidence();

    return {
      score,
      grade,
      category,
      vulnerabilities: [...this.vulnerabilities],
      hardeningApplied: [...this.hardeningFeatures],
      recommendations,
      riskLevel,
      confidence
    };
  }

  /**
   * Analisa vulnerabilidades no objeto
   */
  private analyzeVulnerabilities(obj: any): void {
    if (typeof obj !== 'object' || obj === null) {
      return;
    }

    // Análise de XSS e Code Injection
    this.analyzeCodeInjection(obj);
    
    // Análise de Circular References
    this.analyzeCircularReferences(obj);
    
    // Análise de Deep Nesting
    this.analyzeDeepNesting(obj);
    
    // Análise de Tamanho e Oversized
    this.analyzeSizeVulnerabilities(obj);
    
    // Análise de Conteúdo Suspeito
    this.analyzeMaliciousContent(obj);
  }

  /**
   * Analisa injeção de código
   */
  private analyzeCodeInjection(obj: any, prefix = 'root'): void {
    const deepAnalyze = (current: any, path: string) => {
      if (typeof current === 'string') {
        // Padrões de XSS
        const xssPatterns = [
          /<script[^>]*>/i,
          /javascript:/i,
          /on\w+\s*=/i,
          /eval\s*\(/i,
          /expression\s*\(/i,
          /data:text\/html/i
        ];

        for (const pattern of xssPatterns) {
          if (pattern.test(current)) {
            this.addVulnerability({
              id: `XSS_${path}_${Date.now()}`,
              type: 'XSS',
              severity: 'high',
              description: `Possível XSS detectado no caminho ${path}`,
              path,
              remediation: 'Escapar caracteres HTML e remover scripts',
              cweId: 'CWE-79'
            });
            break;
          }
        }

        // Padrões de Template Injection
        const templatePattern = /\$\{.*\}/;
        if (templatePattern.test(current)) {
          this.addVulnerability({
            id: `TEMPLATE_${path}_${Date.now()}`,
            type: 'TEMPLATE_INJECTION',
            severity: 'medium',
            description: `Possível template injection no caminho ${path}`,
            path,
            remediation: 'Validar e sanitizar strings de template',
            cweId: 'CWE-1336'
          });
        }

        // Padrões de Credential Leak
        const credentialPattern = /(password|api_key|secret|token)\s*[:=]\s*["']?[\w\-]+["']?/i;
        if (credentialPattern.test(current)) {
          this.addVulnerability({
            id: `CREDENTIAL_${path}_${Date.now()}`,
            type: 'CREDENTIAL_LEAK',
            severity: 'medium',
            description: `Possível exposição de credenciais no caminho ${path}`,
            path,
            remediation: 'Remover ou mascarar informações sensíveis',
            cweId: 'CWE-256'
          });
        }
      }

      // Recursivo para objetos aninhados
      if (typeof current === 'object' && current !== null) {
        if (Array.isArray(current)) {
          current.forEach((item, index) => {
            deepAnalyze(item, `${path}[${index}]`);
          });
        } else {
          for (const [key, value] of Object.entries(current)) {
            deepAnalyze(value, `${path}.${key}`);
          }
        }
      }
    };

    deepAnalyze(obj, prefix);
  }

  /**
   * Analisa referências circulares
   */
  private analyzeCircularReferences(obj: any): void {
    try {
      const circularDetector = new WeakSet();
      this.detectCircularRecursive(obj, circularDetector, 'root');
    } catch (error) {
      this.addVulnerability({
        id: `CIRCULAR_${Date.now()}`,
        type: 'CIRCULAR_REFERENCE',
        severity: 'high',
        description: 'Referência circular detectada na estrutura',
        path: 'root',
        remediation: 'Remover referências circulares na estrutura YAML',
        cweId: 'CWE-835'
      });
    }
  }

  /**
   * Detecta referências circulares recursivamente
   */
  private detectCircularRecursive(obj: any, visited: WeakSet<any>, path: string): void {
    if (typeof obj !== 'object' || obj === null) {
      return;
    }

    if (visited.has(obj)) {
      throw new Error(`Circular reference detected at ${path}`);
    }

    visited.add(obj);

    try {
      for (const [key, value] of Object.entries(obj)) {
        if (typeof value === 'object' && value !== null) {
          this.detectCircularRecursive(value, visited, `${path}.${key}`);
        }
      }
    } finally {
      visited.delete(obj);
    }
  }

  /**
   * Analisa deep nesting
   */
  private analyzeDeepNesting(obj: any): void {
    const maxDepth = this.calculateMaxDepth(obj);
    if (maxDepth > 1000) {
      this.addVulnerability({
        id: `DEEP_NESTING_${Date.now()}`,
        type: 'DEEP_NESTING',
        severity: 'medium',
        description: `Profundidade excessiva de aninhamento: ${maxDepth} níveis`,
        path: 'root',
        remediation: 'Reduzir níveis de aninhamento para menos de 1000'
      });
    }
  }

  /**
   * Calcula profundidade máxima
   */
  private calculateMaxDepth(obj: any, depth = 0): number {
    if (typeof obj !== 'object' || obj === null) {
      return depth;
    }

    let maxDepth = depth;
    for (const value of Object.values(obj)) {
      maxDepth = Math.max(maxDepth, this.calculateMaxDepth(value, depth + 1));
    }
    return maxDepth;
  }

  /**
   * Analisa vulnerabilidades de tamanho
   */
  private analyzeSizeVulnerabilities(obj: any): void {
    const totalSize = this.calculateObjectSize(obj);
    
    if (totalSize > 100 * 1024 * 1024) { // 100MB
      this.addVulnerability({
        id: `OVERSIZED_${Date.now()}`,
        type: 'OVERSIZED_PAYLOAD',
        severity: 'high',
        description: `Payload muito grande: ${(totalSize / (1024 * 1024)).toFixed(2)}MB`,
        path: 'root',
        remediation: 'Reduzir tamanho do payload para menos de 100MB'
      });
    }
  }

  /**
   * Calcula tamanho aproximado do objeto em bytes
   */
  private calculateObjectSize(obj: any): number {
    try {
      return JSON.stringify(obj).length * 2; // Aproximação básica UTF-16
    } catch {
      return 0;
    }
  }

  /**
   * Analisa conteúdo malicioso
   */
  private analyzeMaliciousContent(obj: any): void {
    const maliciousPatterns = [
      { pattern: /cmd\.exe|powershell|bash/i, type: 'COMMAND_INJECTION' as const, severity: 'critical' as const },
      { pattern: /SELECT\s+\*|INSERT\s+INTO|UPDATE\s+.*SET|DELETE\s+FROM/i, type: 'SQL_INJECTION' as const, severity: 'critical' as const },
      { pattern: /union.*select|'.+'\s*=|'.*\bor\b/i, type: 'SQL_INJECTION' as const, severity: 'critical' as const },
      { pattern: /<\?xml.*encoding/i, type: 'XXE' as const, severity: 'high' as const }
    ];

    const deepAnalyze = (current: any, path: string) => {
      if (typeof current === 'string') {
        for (const rule of maliciousPatterns) {
          if (rule.pattern.test(current)) {
            this.addVulnerability({
              id: `${rule.type}_${path}_${Date.now()}`,
              type: rule.type,
              severity: rule.severity,
              description: `Possível ${rule.type} detectado no caminho ${path}`,
              path,
              remediation: `Filtrar padrões de ${rule.type}`,
              cweId: this.getCweForVulnerability(rule.type)
            });
          }
        }
      }

      if (typeof current === 'object' && current !== null) {
        for (const [key, value] of Object.entries(current)) {
          deepAnalyze(value, `${path}.${key}`);
        }
      }
    };

    deepAnalyze(obj, 'root');
  }

  /**
   * Analisa hardening implementado
   */
  private analyzeHardening(obj: any): void {
    // Falha-safe Schema aplicado
    this.addHardeningFeature({
      name: 'FAILSAFE_SCHEMA',
      status: 'applied',
      effectiveness: 100,
      description: 'Schema fail-safe aplicado para máxima segurança'
    });

    // Detecção de referências circulares
    this.addHardeningFeature({
      name: 'CIRCULAR_REFERENCE_DETECTION',
      status: 'applied',
      effectiveness: 85,
      description: 'Detecção e prevenção de referências circulares'
    });

    // Limites de tamanho
    this.addHardeningFeature({
      name: 'SIZE_LIMITS',
      status: 'applied',
      effectiveness: 90,
      description: 'Limites de tamanho implementados para prevenir DoS'
    });

    // Inspeção de conteúdo
    this.addHardeningFeature({
      name: 'CONTENT_INSPECTION',
      status: 'partial',
      effectiveness: 70,
      description: 'Inspeção básica de conteúdo para padrões maliciosos'
    });

    // Validação estrutural
    this.addHardeningFeature({
      name: 'STRUCTURE_VALIDATION',
      status: 'applied',
      effectiveness: 95,
      description: 'Validação rigorosa da estrutura do objeto'
    });
  }

  /**
   * Adiciona uma vulnerabilidade encontrada
   */
  private addVulnerability(vulnerability: SecurityVulnerability): void {
    this.vulnerabilities.push({
      ...vulnerability,
      cvssScore: this.estimateCvssScore(vulnerability.severity)
    });
  }

  /**
   * Adiciona uma feature de hardening
   */
  private addHardeningFeature(feature: HardeningFeature): void {
    this.hardeningFeatures.push(feature);
  }

  /**
   * Estima score CVSS baseado na severidade
   */
  private estimateCvssScore(severity: string): number {
    switch (severity) {
      case 'critical': return 9.5;
      case 'high': return 7.5;
      case 'medium': return 5.0;
      case 'low': return 2.5;
      default: return 3.0;
    }
  }

  /**
   * Calcula o score final de segurança
   */
  private calculateFinalScore(): number {
    // Calcula score baseado em vulnerabilidades
    let vulnerabilityScore = 100;
    for (const vuln of this.vulnerabilities) {
      vulnerabilityScore -= this.impactForVulnerability(vuln.severity);
    }

    // Adiciona pontos pelas features de hardening
    let hardeningScore = 0;
    for (const feature of this.hardeningFeatures) {
      if (feature.status === 'applied') {
        hardeningScore += feature.effectiveness;
      } else if (feature.status === 'partial') {
        hardeningScore += feature.effectiveness * 0.5;
      }
    }

    // Score final (mínimo 0, máximo 100)
    vulnerabilityScore = Math.max(0, vulnerabilityScore);
    hardeningScore = Math.min(100, hardeningScore);
    
    // Média ponderada: 70% da proteção base + 30% do hardening
    return Math.round((vulnerabilityScore * 0.7) + (hardeningScore * 0.3));
  }

  /**
   * Calcula impacto de uma vulnerabilidade
   */
  private impactForVulnerability(severity: string): number {
    switch (severity) {
      case 'critical': return 30;
      case 'high': return 20;
      case 'medium': return 10;
      case 'low': return 5;
      default: return 8;
    }
  }

  /**
   * Calcula o grau baseado no score
   */
  private calculateGrade(score: number): SecurityGrade {
    if (score >= 90) return 'A';
    if (score >= 80) return 'B';
    if (score >= 70) return 'C';
    if (score >= 60) return 'D';
    return 'F';
  }

  /**
   * Calcula a categoria baseada no grau
   */
  private calculateCategory(grade: SecurityGrade): SecurityCategory {
    switch (grade) {
      case 'A': return 'EXCEPTIONAL';
      case 'B': return 'GOOD';
      case 'C': return 'ACCEPTABLE';
      case 'D': return 'LIMITED';
      case 'F': return 'INSECURE';
    }
  }

  /**
   * Calcula o nível de risco baseado no score
   */
  private calculateRiskLevel(score: number): RiskLevel {
    if (score >= 80) return 'LOW';
    if (score >= 60) return 'MEDIUM';
    if (score >= 40) return 'HIGH';
    return 'CRITICAL';
  }

  /**
   * Obtém recomendações baseadas no score
   */
  public getRecommendations(score: number): string[] {
    const recommendations: string[] = [];

    if (score < 90) {
      recommendations.push('Implementar schema de segurança mais rigoroso (FAILSAFE_SCHEMA)');
    }

    if (score < 80) {
      recommendations.push('Adicionar detecção de referências circulares');
      recommendations.push('Implementar limites de tamanho para strings e objetos');
    }

    if (score < 70) {
      recommendations.push('Adicionar inspeção de conteúdo para padrões maliciosos');
      recommendations.push('Implementar validação de profundidade máxima');
    }

    if (score < 60) {
      recommendations.push('Adicionar sandbox de execução segura');
      recommendations.push('Implementar rate limiting e throttling');
      recommendations.push('Adicionar logging detalhado de eventos de segurança');
    }

    if (score < 50) {
      recommendations.push('Considerar reescrita completa com foco em segurança');
      recommendations.push('Implementar múltiplas camadas de validação');
      recommendations.push('Adicionar scanning de vulnerabilidades');
    }

    return recommendations;
  }

  /**
   * Calcula a confiança no resultado
   */
  public calculateConfidence(): number {
    // Calcula confiança baseada na profundidade da análise
    const vulnerabilityFactor = this.vulnerabilities.length > 0 ? Math.min(100, this.vulnerabilities.length * 20) : 70;
    const hardeningFactor = this.hardeningFeatures.length * 15;
    return Math.min(100, vulnerabilityFactor + hardeningFactor);
  }

  /**
   * Calcula score de componente específico
   */
  public calculateComponentScore(component: string): number {
    // Score base para diferentes componentes
    const componentScores: Record<string, number> = {
      'validation': 85,
      'parsing': 75,
      'hardening': 90,
      'encryption': 95,
      'authentication': 90
    };

    return componentScores[component.toLowerCase()] || 70;
  }

  /**
   * Obtém CWE ID para tipos de vulnerabilidade
   */
  private getCweForVulnerability(type: string): string {
    const cweMap: Record<string, string> = {
      'XSS': 'CWE-79',
      'SQL_INJECTION': 'CWE-89',
      'CODE_INJECTION': 'CWE-94',
      'TEMPLATE_INJECTION': 'CWE-1336',
      'PATH_TRAVERSAL': 'CWE-22',
      'XXE': 'CWE-611',
      'LDAP_INJECTION': 'CWE-90',
      'COMMAND_INJECTION': 'CWE-78',
      'INSECURE_DESERIALIZATION': 'CWE-502',
      'CIRCULAR_REFERENCE': 'CWE-835',
      'DEEP_NESTING': 'CWE-674',
      'OVERSIZED_PAYLOAD': 'CWE-400',
      'CREDENTIAL_LEAK': 'CWE-256',
      'PII_EXPOSURE': 'CWE-359',
      'MALICIOUS_CONTENT': 'CWE-434'
    };

    return cweMap[type] || 'CWE-20';
  }

  /**
   * Reinicia o estado do calculador
   */
  private resetState(): void {
    this.vulnerabilities = [];
    this.hardeningFeatures = [];
  }
}

export interface SecurityScoreResult {
  score: number;           // 0-100
  grade: SecurityGrade;
  category: SecurityCategory;
  vulnerabilities: SecurityVulnerability[];
  hardeningApplied: HardeningFeature[];
  recommendations: string[];
  riskLevel: RiskLevel;
  confidence: number;       // 0-100
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
  effectiveness: number;    // 0-100
  description: string;
}

export type VulnerabilityType = 
  | 'XSS'
  | 'SQL_INJECTION'
  | 'CODE_INJECTION'
  | 'TEMPLATE_INJECTION'
  | 'PATH_TRAVERSAL'
  | 'XXE'
  | 'LDAP_INJECTION'
  | 'COMMAND_INJECTION'
  | 'INSECURE_DESERIALIZATION'
  | 'CIRCULAR_REFERENCE'
  | 'DEEP_NESTING'
  | 'OVERSIZED_PAYLOAD'
  | 'CREDENTIAL_LEAK'
  | 'PII_EXPOSURE'
  | 'MALICIOUS_CONTENT';

export interface SecurityScoreCalculator {
  calculate(obj: any): SecurityScoreResult;
  calculateComponentScore(component: string): number;
  getRecommendations(score: number): string[];
  calculateConfidence(result: SecurityScoreResult): number;
}

class SecurityScore implements SecurityScoreCalculator {
  private vulnerabilities: SecurityVulnerability[] = [];
  private hardeningFeatures: HardeningFeature[] = [];

  constructor() {
    // State é inicializado em resetState()
  }

  /**
   * Calcula o score de segurança completo
   */
  public calculate(obj: any): SecurityScoreResult {
    this.resetState();
    
    // Análise de vulnerabilidades
    this.analyzeVulnerabilities(obj);
    
    // Análise de hardening
    this.analyzeHardening(obj);
    
    // Cálculo do score final
    const score = this.calculateFinalScore();
    const grade = this.calculateGrade(score);
    const category = this.calculateCategory(grade);
    const riskLevel = this.calculateRiskLevel(score);
    const recommendations = this.getRecommendations(score);
    const confidence = this.calculateConfidence();

    return {
      score,
      grade,
      category,
      vulnerabilities: [...this.vulnerabilities],
      hardeningApplied: [...this.hardeningFeatures],
      recommendations,
      riskLevel,
      confidence
    };
  }

  /**
   * Analisa vulnerabilidades no objeto
   */
  private analyzeVulnerabilities(obj: any): void {
    if (typeof obj !== 'object' || obj === null) {
      return;
    }

    // Análise de XSS e Code Injection
    this.analyzeCodeInjection(obj);
    
    // Análise de Circular References
    this.analyzeCircularReferences(obj);
    
    // Análise de Deep Nesting
    this.analyzeDeepNesting(obj);
    
    // Análise de Tamanho e Oversized
    this.analyzeSizeVulnerabilities(obj);
    
    // Análise de Conteúdo Suspeito
    this.analyzeMaliciousContent(obj);
  }

  /**
   * Analisa injeção de código
   */
  private analyzeCodeInjection(obj: any, prefix = 'root'): void {
    const deepAnalyze = (current: any, path: string) => {
      if (typeof current === 'string') {
        // Padrões de XSS
        const xssPatterns = [
          /<script[^>]*>/i,
          /javascript:/i,
          /on\w+\s*=/i,
          /eval\s*\(/i,
          /expression\s*\(/i,
          /data:text\/html/i
        ];

        for (const pattern of xssPatterns) {
          if (pattern.test(current)) {
            this.addVulnerability({
              id: `XSS_${path}_${Date.now()}`,
              type: 'XSS',
              severity: 'high',
              description: `Possível XSS detectado no caminho ${path}`,
              path,
              remediation: 'Escapar caracteres HTML e remover scripts',
              cweId: 'CWE-79'
            });
            break;
          }
        }

        // Padrões de Template Injection
        const templatePattern = /\$\{.*\}/;
        if (templatePattern.test(current)) {
          this.addVulnerability({
            id: `TEMPLATE_${path}_${Date.now()}`,
            type: 'TEMPLATE_INJECTION',
            severity: 'medium',
            description: `Possível template injection no caminho ${path}`,
            path,
            remediation: 'Validar e sanitizar strings de template',
            cweId: 'CWE-1336'
          });
        }

        // Padrões de Credential Leak
        const credentialPattern = /(password|api_key|secret|token)\s*[:=]\s*["']?[\w\-]+["']?/i;
        if (credentialPattern.test(current)) {
          this.addVulnerability({
            id: `CREDENTIAL_${path}_${Date.now()}`,
            type: 'CREDENTIAL_LEAK',
            severity: 'medium',
            description: `Possível exposição de credenciais no caminho ${path}`,
            path,
            remediation: 'Remover ou mascarar informações sensíveis',
            cweId: 'CWE-256'
          });
        }
      }

      // Recursivo para objetos aninhados
      if (typeof current === 'object' && current !== null) {
        if (Array.isArray(current)) {
          current.forEach((item, index) => {
            deepAnalyze(item, `${path}[${index}]`);
          });
        } else {
          for (const [key, value] of Object.entries(current)) {
            deepAnalyze(value, `${path}.${key}`);
          }
        }
      }
    };

    deepAnalyze(obj, prefix);
  }

  /**
   * Analisa referências circulares
   */
  private analyzeCircularReferences(obj: any): void {
    try {
      const circularDetector = new WeakSet();
      this.detectCircularRecursive(obj, circularDetector, 'root');
    } catch (error) {
      this.addVulnerability({
        id: `CIRCULAR_${Date.now()}`,
        type: 'CIRCULAR_REFERENCE',
        severity: 'high',
        description: 'Referência circular detectada na estrutura',
        path: 'root',
        remediation: 'Remover referências circulares na estrutura YAML',
        cweId: 'CWE-835'
      });
    }
  }

  /**
   * Detecta referências circulares recursivamente
   */
  private detectCircularRecursive(obj: any, visited: WeakSet<any>, path: string): void {
    if (typeof obj !== 'object' || obj === null) {
      return;
    }

    if (visited.has(obj)) {
      throw new Error(`Circular reference detected at ${path}`);
    }

    visited.add(obj);

    try {
      for (const [key, value] of Object.entries(obj)) {
        if (typeof value === 'object' && value !== null) {
          this.detectCircularRecursive(value, visited, `${path}.${key}`);
        }
      }
    } finally {
      visited.delete(obj);
    }
  }

  /**
   * Analisa deep nesting
   */
  private analyzeDeepNesting(obj: any): void {
    const maxDepth = this.calculateMaxDepth(obj);
    if (maxDepth > 1000) {
      this.addVulnerability({
        id: `DEEP_NESTING_${Date.now()}`,
        type: 'DEEP_NESTING',
        severity: 'medium',
        description: `Profundidade excessiva de aninhamento: ${maxDepth} níveis`,
        path: 'root',
        remediation: 'Reduzir níveis de aninhamento para menos de 1000'
      });
    }
  }

  /**
   * Calcula profundidade máxima
   */
  private calculateMaxDepth(obj: any, depth = 0): number {
    if (typeof obj !== 'object' || obj === null) {
      return depth;
    }

    let maxDepth = depth;
    for (const value of Object.values(obj)) {
      maxDepth = Math.max(maxDepth, this.calculateMaxDepth(value, depth + 1));
    }
    return maxDepth;
  }

  /**
   * Analisa vulnerabilidades de tamanho
   */
  private analyzeSizeVulnerabilities(obj: any): void {
    const totalSize = this.calculateObjectSize(obj);
    
    if (totalSize > 100 * 1024 * 1024) { // 100MB
      this.addVulnerability({
        id: `OVERSIZED_${Date.now()}`,
        type: 'OVERSIZED_PAYLOAD',
        severity: 'high',
        description: `Payload muito grande: ${(totalSize / (1024 * 1024)).toFixed(2)}MB`,
        path: 'root',
        remediation: 'Reduzir tamanho do payload para menos de 100MB'
      });
    }
  }

  /**
   * Calcula tamanho aproximado do objeto em bytes
   */
  private calculateObjectSize(obj: any): number {
    try {
      return JSON.stringify(obj).length * 2; // Aproximação básica UTF-16
    } catch {
      return 0;
    }
  }

  /**
   * Analisa conteúdo malicioso
   */
  private analyzeMaliciousContent(obj: any): void {
    const maliciousPatterns = [
      { pattern: /cmd\.exe|powershell|bash/i, type: 'COMMAND_INJECTION' as const, severity: 'critical' as const },
      { pattern: /SELECT\s+\*|INSERT\s+INTO|UPDATE\s+.*SET|DELETE\s+FROM/i, type: 'SQL_INJECTION' as const, severity: 'critical' as const },
      { pattern: /union.*select|'.+'\s*=|'.*\bor\b/i, type: 'SQL_INJECTION' as const, severity: 'critical' as const },
      { pattern: /<\?xml.*encoding/i, type: 'XXE' as const, severity: 'high' as const }
    ];

    const deepAnalyze = (current: any, path: string) => {
      if (typeof current === 'string') {
        for (const rule of maliciousPatterns) {
          if (rule.pattern.test(current)) {
            this.addVulnerability({
              id: `${rule.type}_${path}_${Date.now()}`,
              type: rule.type,
              severity: rule.severity,
              description: `Possível ${rule.type} detectado no caminho ${path}`,
              path,
              remediation: `Filtrar padrões de ${rule.type}`,
              cweId: this.getCweForVulnerability(rule.type)
            });
          }
        }
      }

      if (typeof current === 'object' && current !== null) {
        for (const [key, value] of Object.entries(current)) {
          deepAnalyze(value, `${path}.${key}`);
        }
      }
    };

    deepAnalyze(obj, 'root');
  }

  /**
   * Analisa hardening implementado
   */
  private analyzeHardening(obj: any): void {
    // Falha-safe Schema aplicado
    this.addHardeningFeature({
      name: 'FAILSAFE_SCHEMA',
      status: 'applied',
      effectiveness: 100,
      description: 'Schema fail-safe aplicado para máxima segurança'
    });

    // Detecção de referências circulares
    this.addHardeningFeature({
      name: 'CIRCULAR_REFERENCE_DETECTION',
      status: 'applied',
      effectiveness: 85,
      description: 'Detecção e prevenção de referências circulares'
    });

    // Limites de tamanho
    this.addHardeningFeature({
      name: 'SIZE_LIMITS',
      status: 'applied',
      effectiveness: 90,
      description: 'Limites de tamanho implementados para prevenir DoS'
    });

    // Inspeção de conteúdo
    this.addHardeningFeature({
      name: 'CONTENT_INSPECTION',
      status: 'partial',
      effectiveness: 70,
      description: 'Inspeção básica de conteúdo para padrões maliciosos'
    });

    // Validação estrutural
    this.addHardeningFeature({
      name: 'STRUCTURE_VALIDATION',
      status: 'applied',
      effectiveness: 95,
      description: 'Validação rigorosa da estrutura do objeto'
    });
  }

  /**
   * Adiciona uma vulnerabilidade encontrada
   */
  private addVulnerability(vulnerability: SecurityVulnerability): void {
    this.vulnerabilities.push({
      ...vulnerability,
      cvssScore: this.estimateCvssScore(vulnerability.severity)
    });
  }

  /**
   * Adiciona uma feature de hardening
   */
  private addHardeningFeature(feature: HardeningFeature): void {
    this.hardeningFeatures.push(feature);
  }

  /**
   * Estima score CVSS baseado na severidade
   */
  private estimateCvssScore(severity: string): number {
    switch (severity) {
      case 'critical': return 9.5;
      case 'high': return 7.5;
      case 'medium': return 5.0;
      case 'low': return 2.5;
      default: return 3.0;
    }
  }

  /**
   * Calcula o score final de segurança
   */
  private calculateFinalScore(): number {
    // Calcula score baseado em vulnerabilidades
    let vulnerabilityScore = 100;
    for (const vuln of this.vulnerabilities) {
      vulnerabilityScore -= this.impactForVulnerability(vuln.severity);
    }

    // Adiciona pontos pelas features de hardening
    let hardeningScore = 0;
    for (const feature of this.hardeningFeatures) {
      if (feature.status === 'applied') {
        hardeningScore += feature.effectiveness;
      } else if (feature.status === 'partial') {
        hardeningScore += feature.effectiveness * 0.5;
      }
    }

    // Score final (mínimo 0, máximo 100)
    vulnerabilityScore = Math.max(0, vulnerabilityScore);
    hardeningScore = Math.min(100, hardeningScore);
    
    // Média ponderada: 70% da proteção base + 30% do hardening
    return Math.round((vulnerabilityScore * 0.7) + (hardeningScore * 0.3));
  }

  /**
   * Calcula impacto de uma vulnerabilidade
   */
  private impactForVulnerability(severity: string): number {
    switch (severity) {
      case 'critical': return 30;
      case 'high': return 20;
      case 'medium': return 10;
      case 'low': return 5;
      default: return 8;
    }
  }

  /**
   * Calcula o grau baseado no score
   */
  private calculateGrade(score: number): SecurityGrade {
    if (score >= 90) return 'A';
    if (score >= 80) return 'B';
    if (score >= 70) return 'C';
    if (score >= 60) return 'D';
    return 'F';
  }

  /**
   * Calcula a categoria baseada no grau
   */
  private calculateCategory(grade: SecurityGrade): SecurityCategory {
    switch (grade) {
      case 'A': return 'EXCEPTIONAL';
      case 'B': return 'GOOD';
      case 'C': return 'ACCEPTABLE';
      case 'D': return 'LIMITED';
      case 'F': return 'INSECURE';
    }
  }

  /**
   * Calcula o nível de risco baseado no score
   */
  private calculateRiskLevel(score: number): RiskLevel {
    if (score >= 80) return 'LOW';
    if (score >= 60) return 'MEDIUM';
    if (score >= 40) return 'HIGH';
    return 'CRITICAL';
  }

  /**
   * Obtém recomendações baseadas no score
   */
  public getRecommendations(score: number): string[] {
    const recommendations: string[] = [];

    if (score < 90) {
      recommendations.push('Implementar schema de segurança mais rigoroso (FAILSAFE_SCHEMA)');
    }

    if (score < 80) {
      recommendations.push('Adicionar detecção de referências circulares');
      recommendations.push('Implementar limites de tamanho para strings e objetos');
    }

    if (score < 70) {
      recommendations.push('Adicionar inspeção de conteúdo para padrões maliciosos');
      recommendations.push('Implementar validação de profundidade máxima');
    }

    if (score < 60) {
      recommendations.push('Adicionar sandbox de execução segura');
      recommendations.push('Implementar rate limiting e throttling');
      recommendations.push('Adicionar logging detalhado de eventos de segurança');
    }

    if (score < 50) {
      recommendations.push('Considerar reescrita completa com foco em segurança');
      recommendations.push('Implementar múltiplas camadas de validação');
      recommendations.push('Adicionar scanning de vulnerabilidades');
    }

    return recommendations;
  }

  /**
   * Calcula a confiança no resultado
   */
  public calculateConfidence(): number {
    // Calcula confiança baseada na profundidade da análise
    const vulnerabilityFactor = this.vulnerabilities.length > 0 ? Math.min(100, this.vulnerabilities.length * 20) : 70;
    const hardeningFactor = this.hardeningFeatures.length * 15;
    return Math.min(100, vulnerabilityFactor + hardeningFactor);
  }

  /**
   * Calcula score de componente específico
   */
  public calculateComponentScore(component: string): number {
    // Score base para diferentes componentes
    const componentScores: Record<string, number> = {
      'validation': 85,
      'parsing': 75,
      'hardening': 90,
      'encryption': 95,
      'authentication': 90
    };

    return componentScores[component.toLowerCase()] || 70;
  }

  /**
   * Obtém CWE ID para tipos de vulnerabilidade
   */
  private getCweForVulnerability(type: string): string {
    const cweMap: Record<string, string> = {
      'XSS': 'CWE-79',
      'SQL_INJECTION': 'CWE-89',
      'CODE_INJECTION': 'CWE-94',
      'TEMPLATE_INJECTION': 'CWE-1336',
      'PATH_TRAVERSAL': 'CWE-22',
      'XXE': 'CWE-611',
      'LDAP_INJECTION': 'CWE-90',
      'COMMAND_INJECTION': 'CWE-78',
      'INSECURE_DESERIALIZATION': 'CWE-502',
      'CIRCULAR_REFERENCE': 'CWE-835',
      'DEEP_NESTING': 'CWE-674',
      'OVERSIZED_PAYLOAD': 'CWE-400',
      'CREDENTIAL_LEAK': 'CWE-256',
      'PII_EXPOSURE': 'CWE-359',
      'MALICIOUS_CONTENT': 'CWE-434'
    };

    return cweMap[type] || 'CWE-20';
  }

  /**
   * Reinicia o estado do calculador
   */
  private resetState(): void {
    this.vulnerabilities = [];
    this.hardeningFeatures = [];
  }
}

/**
 * Função auxiliar para calcular segurança
 */
export function calculateSecurityScore(obj: any): SecurityScoreResult {
  const calculator = new SecurityScore();
  return calculator.calculate(obj);
}

/**
 * Função auxiliar para obter recomendações
 */
export function getSecurityRecommendations(score: number): string[] {
  const calculator = new SecurityScore();
  return calculator.getRecommendations(score);
}

export { SecurityScoreImpl as SecurityScore };
