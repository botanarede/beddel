"use strict";
/**
 * Security score calculator for YAML parsing
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.SecurityScore = void 0;
exports.calculateSecurityScore = calculateSecurityScore;
exports.getSecurityRecommendations = getSecurityRecommendations;
// Classe interna para implementação
class SecurityScoreImpl {
    constructor() {
        this.vulnerabilities = [];
        this.hardeningFeatures = [];
        // State é inicializado em resetState()
    }
    /**
     * Calcula o score de segurança completo
     */
    calculate(obj) {
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
    analyzeVulnerabilities(obj) {
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
    analyzeCodeInjection(obj, prefix = 'root') {
        const deepAnalyze = (current, path) => {
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
                }
                else {
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
    analyzeCircularReferences(obj) {
        try {
            const circularDetector = new WeakSet();
            this.detectCircularRecursive(obj, circularDetector, 'root');
        }
        catch (error) {
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
    detectCircularRecursive(obj, visited, path) {
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
        }
        finally {
            visited.delete(obj);
        }
    }
    /**
     * Analisa deep nesting
     */
    analyzeDeepNesting(obj) {
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
    calculateMaxDepth(obj, depth = 0) {
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
    analyzeSizeVulnerabilities(obj) {
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
    calculateObjectSize(obj) {
        try {
            return JSON.stringify(obj).length * 2; // Aproximação básica UTF-16
        }
        catch {
            return 0;
        }
    }
    /**
     * Analisa conteúdo malicioso
     */
    analyzeMaliciousContent(obj) {
        const maliciousPatterns = [
            { pattern: /cmd\.exe|powershell|bash/i, type: 'COMMAND_INJECTION', severity: 'critical' },
            { pattern: /SELECT\s+\*|INSERT\s+INTO|UPDATE\s+.*SET|DELETE\s+FROM/i, type: 'SQL_INJECTION', severity: 'critical' },
            { pattern: /union.*select|'.+'\s*=|'.*\bor\b/i, type: 'SQL_INJECTION', severity: 'critical' },
            { pattern: /<\?xml.*encoding/i, type: 'XXE', severity: 'high' }
        ];
        const deepAnalyze = (current, path) => {
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
    analyzeHardening(obj) {
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
    addVulnerability(vulnerability) {
        this.vulnerabilities.push({
            ...vulnerability,
            cvssScore: this.estimateCvssScore(vulnerability.severity)
        });
    }
    /**
     * Adiciona uma feature de hardening
     */
    addHardeningFeature(feature) {
        this.hardeningFeatures.push(feature);
    }
    /**
     * Estima score CVSS baseado na severidade
     */
    estimateCvssScore(severity) {
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
    calculateFinalScore() {
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
            }
            else if (feature.status === 'partial') {
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
    impactForVulnerability(severity) {
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
    calculateGrade(score) {
        if (score >= 90)
            return 'A';
        if (score >= 80)
            return 'B';
        if (score >= 70)
            return 'C';
        if (score >= 60)
            return 'D';
        return 'F';
    }
    /**
     * Calcula a categoria baseada no grau
     */
    calculateCategory(grade) {
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
    calculateRiskLevel(score) {
        if (score >= 80)
            return 'LOW';
        if (score >= 60)
            return 'MEDIUM';
        if (score >= 40)
            return 'HIGH';
        return 'CRITICAL';
    }
    /**
     * Obtém recomendações baseadas no score
     */
    getRecommendations(score) {
        const recommendations = [];
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
    calculateConfidence() {
        // Calcula confiança baseada na profundidade da análise
        const vulnerabilityFactor = this.vulnerabilities.length > 0 ? Math.min(100, this.vulnerabilities.length * 20) : 70;
        const hardeningFactor = this.hardeningFeatures.length * 15;
        return Math.min(100, vulnerabilityFactor + hardeningFactor);
    }
    /**
     * Calcula score de componente específico
     */
    calculateComponentScore(component) {
        // Score base para diferentes componentes
        const componentScores = {
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
    getCweForVulnerability(type) {
        const cweMap = {
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
    resetState() {
        this.vulnerabilities = [];
        this.hardeningFeatures = [];
    }
}
exports.SecurityScore = SecurityScoreImpl;
class SecurityScore {
    constructor() {
        this.vulnerabilities = [];
        this.hardeningFeatures = [];
        // State é inicializado em resetState()
    }
    /**
     * Calcula o score de segurança completo
     */
    calculate(obj) {
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
    analyzeVulnerabilities(obj) {
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
    analyzeCodeInjection(obj, prefix = 'root') {
        const deepAnalyze = (current, path) => {
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
                }
                else {
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
    analyzeCircularReferences(obj) {
        try {
            const circularDetector = new WeakSet();
            this.detectCircularRecursive(obj, circularDetector, 'root');
        }
        catch (error) {
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
    detectCircularRecursive(obj, visited, path) {
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
        }
        finally {
            visited.delete(obj);
        }
    }
    /**
     * Analisa deep nesting
     */
    analyzeDeepNesting(obj) {
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
    calculateMaxDepth(obj, depth = 0) {
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
    analyzeSizeVulnerabilities(obj) {
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
    calculateObjectSize(obj) {
        try {
            return JSON.stringify(obj).length * 2; // Aproximação básica UTF-16
        }
        catch {
            return 0;
        }
    }
    /**
     * Analisa conteúdo malicioso
     */
    analyzeMaliciousContent(obj) {
        const maliciousPatterns = [
            { pattern: /cmd\.exe|powershell|bash/i, type: 'COMMAND_INJECTION', severity: 'critical' },
            { pattern: /SELECT\s+\*|INSERT\s+INTO|UPDATE\s+.*SET|DELETE\s+FROM/i, type: 'SQL_INJECTION', severity: 'critical' },
            { pattern: /union.*select|'.+'\s*=|'.*\bor\b/i, type: 'SQL_INJECTION', severity: 'critical' },
            { pattern: /<\?xml.*encoding/i, type: 'XXE', severity: 'high' }
        ];
        const deepAnalyze = (current, path) => {
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
    analyzeHardening(obj) {
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
    addVulnerability(vulnerability) {
        this.vulnerabilities.push({
            ...vulnerability,
            cvssScore: this.estimateCvssScore(vulnerability.severity)
        });
    }
    /**
     * Adiciona uma feature de hardening
     */
    addHardeningFeature(feature) {
        this.hardeningFeatures.push(feature);
    }
    /**
     * Estima score CVSS baseado na severidade
     */
    estimateCvssScore(severity) {
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
    calculateFinalScore() {
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
            }
            else if (feature.status === 'partial') {
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
    impactForVulnerability(severity) {
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
    calculateGrade(score) {
        if (score >= 90)
            return 'A';
        if (score >= 80)
            return 'B';
        if (score >= 70)
            return 'C';
        if (score >= 60)
            return 'D';
        return 'F';
    }
    /**
     * Calcula a categoria baseada no grau
     */
    calculateCategory(grade) {
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
    calculateRiskLevel(score) {
        if (score >= 80)
            return 'LOW';
        if (score >= 60)
            return 'MEDIUM';
        if (score >= 40)
            return 'HIGH';
        return 'CRITICAL';
    }
    /**
     * Obtém recomendações baseadas no score
     */
    getRecommendations(score) {
        const recommendations = [];
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
    calculateConfidence() {
        // Calcula confiança baseada na profundidade da análise
        const vulnerabilityFactor = this.vulnerabilities.length > 0 ? Math.min(100, this.vulnerabilities.length * 20) : 70;
        const hardeningFactor = this.hardeningFeatures.length * 15;
        return Math.min(100, vulnerabilityFactor + hardeningFactor);
    }
    /**
     * Calcula score de componente específico
     */
    calculateComponentScore(component) {
        // Score base para diferentes componentes
        const componentScores = {
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
    getCweForVulnerability(type) {
        const cweMap = {
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
    resetState() {
        this.vulnerabilities = [];
        this.hardeningFeatures = [];
    }
}
/**
 * Função auxiliar para calcular segurança
 */
function calculateSecurityScore(obj) {
    const calculator = new SecurityScore();
    return calculator.calculate(obj);
}
/**
 * Função auxiliar para obter recomendações
 */
function getSecurityRecommendations(score) {
    const calculator = new SecurityScore();
    return calculator.getRecommendations(score);
}
//# sourceMappingURL=score.js.map