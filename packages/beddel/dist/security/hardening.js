"use strict";
/**
 * Security hardening utilities for YAML parsing
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.SecurityHardening = void 0;
exports.createSecurityHardening = createSecurityHardening;
const DEFAULT_HARDENING_OPTIONS = {
    maxCircularReferences: 0,
    validateStructureIntegrity: true,
    enableContentInspection: true,
    logSecurityEvents: true,
    maxNestingDepth: 1000,
    enableCircularReferenceDetection: true,
    detectAndBlock: true,
    sanitizeOnFailure: true,
    validationPolicy: 'moderate'
};
class SecurityHardening {
    constructor(options = {}) {
        this.events = [];
        this.passes = 0;
        this.fails = 0;
        this.warnings = 0;
        this.options = { ...DEFAULT_HARDENING_OPTIONS, ...options };
    }
    /**
     * Executa hardening completo em um objeto
     */
    harden(obj) {
        this.resetStatistics();
        let result = obj;
        let secure = true;
        // 1. Detecção de referências circulares
        if (this.options.enableCircularReferenceDetection) {
            try {
                this.detectCircularReferences(result);
            }
            catch (error) {
                const errorMessage = error instanceof Error ? error.message : String(error);
                if (this.options.detectAndBlock) {
                    throw new Error(`Referência circular detectada: ${errorMessage}`);
                }
                this.fails++;
                secure = false;
                if (this.options.logSecurityEvents) {
                    this.addSecurityEvent('circular_reference', 'root', 'high', errorMessage);
                }
                if (this.options.sanitizeOnFailure) {
                    result = this.sanitizeObject(result);
                }
            }
        }
        // 2. Validação de integridade estrutural
        if (this.options.validateStructureIntegrity) {
            try {
                this.validateObjectStructure(result);
                this.passes++;
            }
            catch (error) {
                this.fails++;
                secure = false;
                if (this.options.logSecurityEvents) {
                    const errorMessage = error instanceof Error ? error.message : String(error);
                    this.addSecurityEvent('invalid_structure', 'root', 'medium', errorMessage);
                }
            }
        }
        // 3. Inspeção de conteúdo
        if (this.options.enableContentInspection) {
            const contentResult = this.inspectContent(result);
            if (contentResult.warnings > 0) {
                this.warnings += contentResult.warnings;
                if (this.options.logSecurityEvents) {
                    contentResult.issues.forEach((issue) => {
                        this.addSecurityEvent('content_inspection_warning', issue.path, this.mapSeverity(issue.severity), `${issue.type} detectado`);
                    });
                }
            }
        }
        return {
            result,
            secure,
            stats: this.getStatistics()
        };
    }
    /**
     * Detecta referências circulares no objeto
     */
    detectCircularReferences(obj, visited = new WeakSet(), path = 'root') {
        if (typeof obj !== 'object' || obj === null) {
            return;
        }
        if (visited.has(obj)) {
            throw new Error(`Referência circular detectada em ${path}`);
        }
        // Verifica limite de profundidade
        const depth = path.split('.').length;
        if (depth > this.options.maxNestingDepth) {
            this.addSecurityEvent('deep_nesting', path, 'medium', `Profundidade máxima de ${this.options.maxNestingDepth} excedida`);
        }
        visited.add(obj);
        try {
            for (const [key, value] of Object.entries(obj)) {
                if (typeof value === 'object' && value !== null) {
                    // Simplificar para evitar problemas com WeakSet
                    this.detectCircularReferences(value, new WeakSet(), `${path}.${key}`);
                }
            }
        }
        finally {
            visited.delete(obj);
        }
    }
    /**
     * Valida a integridade estrutural do objeto
     */
    validateObjectStructure(obj) {
        if (typeof obj !== 'object' || obj === null) {
            return true;
        }
        return this.isValidStructure(obj, '', 0);
    }
    isValidStructure(obj, path, depth) {
        // Verifica limite de profundidade
        if (depth > this.options.maxNestingDepth) {
            this.addSecurityEvent('deep_nesting', path, 'medium', `Profundidade máxima de ${this.options.maxNestingDepth} atingida`);
            return false;
        }
        // Verifica tipos válidos
        if (!this.isAllowedType(obj)) {
            this.addSecurityEvent('invalid_structure', path, 'medium', `Tipo inválido ${typeof obj} detectado no caminho ${path}`);
            return false;
        }
        // Valida objetos aninhados
        if (typeof obj === 'object' && obj !== null) {
            if (Array.isArray(obj)) {
                for (let i = 0; i < obj.length; i++) {
                    if (!this.isValidStructure(obj[i], `${path}[${i}]`, depth + 1)) {
                        return false;
                    }
                }
            }
            else {
                for (const [key, value] of Object.entries(obj)) {
                    const keyPath = path ? `${path}.${key}` : key;
                    if (!this.isValidStructure(value, keyPath, depth + 1)) {
                        return false;
                    }
                }
            }
        }
        return true;
    }
    /**
     * Verifica se um tipo é permitido
     */
    isAllowedType(obj) {
        const type = typeof obj;
        if (obj === null)
            return true;
        if (type === 'boolean')
            return true;
        if (type === 'number')
            return true;
        if (type === 'string')
            return true;
        if (Array.isArray(obj))
            return true;
        return false;
    }
    /**
     * Inspeciona o conteúdo para padrões perigosos
     */
    inspectContent(obj) {
        const issues = [];
        let warnings = 0;
        const deepInspect = (current, path = 'root') => {
            if (typeof current === 'string') {
                // Padrões de vulnerabilidade
                const vulnerabilityPatterns = [
                    {
                        pattern: /<script[^>]*>/i,
                        type: 'XSS',
                        severity: 'high',
                        description: 'Possível tentativa de XSS via script tag'
                    },
                    {
                        pattern: /javascript:/i,
                        type: 'URL_INJECTION',
                        severity: 'high',
                        description: 'Possível inject javascript: URL'
                    },
                    {
                        pattern: /\$\{.*\}/,
                        type: 'TEMPLATE_INJECTION',
                        severity: 'medium',
                        description: 'Possível template string injection'
                    },
                    {
                        pattern: /on\w+\s*=/i,
                        type: 'EVENT_HANDLER',
                        severity: 'medium',
                        description: 'Possível event handler injection'
                    },
                    {
                        pattern: /eval\s*\(/i,
                        type: 'CODE_EXECUTION',
                        severity: 'high',
                        description: 'Possível code execution via eval'
                    },
                    {
                        pattern: /(password|api_key|secret|token)\s*[:=]\s*["']?[\w\-]+["']?/i,
                        type: 'CREDENTIAL_LEAK',
                        severity: 'medium',
                        description: 'Possível exposição de credenciais'
                    }
                ];
                for (const rule of vulnerabilityPatterns) {
                    if (rule.pattern.test(current)) {
                        issues.push({
                            path,
                            type: rule.type,
                            severity: rule.severity,
                            description: rule.description,
                            pattern: rule.pattern.source
                        });
                        warnings++;
                    }
                }
            }
            // Recursivamente inspeciona objetos aninhados
            if (typeof current === 'object' && current !== null) {
                if (Array.isArray(current)) {
                    current.forEach((item, index) => {
                        deepInspect(item, `${path}[${index}]`);
                    });
                }
                else {
                    for (const [key, value] of Object.entries(current)) {
                        deepInspect(value, `${path}.${key}`);
                    }
                }
            }
        };
        deepInspect(obj);
        return { issues, warnings };
    }
    /**
     * Sanitiza um objeto remover conteúdo potencialmente perigoso
     */
    sanitizeObject(obj) {
        if (typeof obj !== 'object' || obj === null) {
            return obj;
        }
        const visited = new WeakSet();
        const sanitize = (current) => {
            if (typeof current !== 'object' || current === null) {
                return this.sanitizeString(typeof current === 'string' ? current : '');
            }
            if (visited.has(current)) {
                throw new Error('Referência circular detectada durante a sanitização');
            }
            visited.add(current);
            // Sanitização baseada em tipo
            if (Array.isArray(current)) {
                const sanitized = [];
                for (const item of current) {
                    const sanitizedItem = sanitize(item);
                    if (sanitizedItem !== undefined) {
                        sanitized.push(sanitizedItem);
                    }
                }
                visited.delete(current);
                return sanitized;
            }
            const sanitized = {};
            for (const [key, value] of Object.entries(current)) {
                const sanitizedKey = this.sanitizeString(key);
                const sanitizedValue = sanitize(value);
                if (sanitizedValue !== undefined) {
                    sanitized[sanitizedKey] = sanitizedValue;
                }
            }
            visited.delete(current);
            return sanitized;
        };
        return sanitize(obj);
    }
    /**
     * Sanitiza strings removendo conteúdo perigoso
     */
    sanitizeString(str) {
        if (!str || typeof str !== 'string') {
            return '';
        }
        // Remove scripts e conteúdo HTML/JavaScript
        let sanitized = str
            .replace(/<script[^>]*>.*?<\/script>/gi, '')
            .replace(/javascript:/gi, '')
            .replace(/on\w+\s*=/gi, '')
            .replace(/eval\s*\(/gi, '')
            .replace(/expression\s*\(/gi, '');
        // Limita tamanho da string
        return sanitized.length > 100000 ? sanitized.substring(0, 100000) + '[truncated]' : sanitized;
    }
    /**
     * Adiciona um evento de segurança
     */
    addSecurityEvent(type, path, severity, message, details) {
        this.events.push({
            timestamp: Date.now(),
            type,
            path,
            severity,
            message,
            details
        });
        // Limita número de eventos para evitar vazamento de memória
        if (this.events.length > 1000) {
            this.events = this.events.slice(-500);
        }
    }
    /**
     * Obtém estatísticas do hardening
     */
    getStatistics() {
        const now = Date.now();
        const recentEvents = this.events.filter(e => now - e.timestamp < 30000); // Últimos 30 segundos
        return {
            totalEvents: this.events.length,
            recentEvents: recentEvents.length,
            passes: this.passes,
            fails: this.fails,
            warnings: this.warnings,
            securityScore: this.calculateSecurityScore(),
            eventsByType: this.groupEventsByType(),
            recentAlerts: this.getRecentAlerts()
        };
    }
    /**
     * Calcula o score de segurança (0-100)
     */
    calculateSecurityScore() {
        if (this.events.length === 0) {
            return 100;
        }
        const total = this.passes + this.fails;
        if (total === 0) {
            return 50; // Nenhum teste executado
        }
        const successRate = this.passes / total;
        const penalty = this.warnings * 0.5; // Penaliza por warnings
        return Math.max(0, Math.min(100, (successRate * 100) - penalty));
    }
    /**
     * Agrupa eventos por tipo
     */
    groupEventsByType() {
        const counts = {};
        this.events.forEach(event => {
            counts[event.type] = (counts[event.type] || 0) + 1;
        });
        return counts;
    }
    /**
     * Obtém alertas recentes
     */
    getRecentAlerts() {
        const now = Date.now();
        return this.events
            .filter(e => now - e.timestamp < 60000 && // Último minuto
            (e.severity === 'high' || e.severity === 'critical'))
            .slice(-10); // Últimos 10 alertas
    }
    /**
     * Mapeia severidade para uso de eventos
     */
    mapSeverity(severity) {
        if (severity === 'high' || severity === 'critical')
            return 'high';
        if (severity === 'medium')
            return 'medium';
        return 'low';
    }
    /**
     * Reinicia as estatísticas
     */
    resetStatistics() {
        this.passes = 0;
        this.fails = 0;
        this.warnings = 0;
    }
    /**
     * Executa limpeza e validação final
     */
    cleanup() {
        // Remove eventos antigos (máx 24 horas)
        const cutoff = Date.now() - (24 * 60 * 60 * 1000);
        this.events = this.events.filter(e => e.timestamp > cutoff);
        // Limita número de eventos
        if (this.events.length > 10000) {
            this.events = this.events.slice(-5000);
        }
    }
}
exports.SecurityHardening = SecurityHardening;
/**
 * Função auxiliar para criar instância de hardening
 */
function createSecurityHardening(options = {}) {
    return new SecurityHardening(options);
}
//# sourceMappingURL=hardening.js.map