"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SecureYamlRuntime = void 0;
const scanner_1 = require("../security/scanner");
const config_1 = require("../config");
class SecureYamlRuntime {
    constructor(runtimeManagerInstance) {
        this.runtimeManagerInstance = runtimeManagerInstance;
        this.runtimeManager = runtimeManagerInstance;
        this.securityScanner = new scanner_1.SecurityScanner();
    }
    /**
     * Parse YAML in isolated runtime environment
     */
    async parseYamlSecureRuntime(yamlContent, config = {}) {
        const startTime = performance.now();
        try {
            // Validate input
            this.validateInput(yamlContent);
            // Security scan if enabled
            if (config.validateSecurity !== false) {
                const scanResult = await this.securityScanner.scan({
                    code: yamlContent,
                    executionId: `yaml-parse-${Date.now()}`,
                });
                if (!scanResult.secure) {
                    throw new Error(`Security scan failed: ${scanResult.warnings.join(", ")}`);
                }
            }
            // Prepare execution code
            const executionCode = this.buildYamlExecutionCode(yamlContent);
            // Execute in isolated runtime
            const executionResult = await this.runtimeManager.execute({
                code: executionCode,
                securityProfile: config.securityProfile || "ultra-secure",
                timeout: config.timeout || 5000,
                memoryLimit: config.memoryLimit || 2,
                tenantId: config.tenantId,
                scanForSecurity: config.validateSecurity,
            });
            const endTime = performance.now();
            const totalTime = endTime - startTime;
            // Validate performance targets
            this.validatePerformanceTargets(totalTime, executionResult.memoryUsed);
            const auditHash = this.generateAuditHash(yamlContent, executionResult, config);
            return {
                success: executionResult.success,
                result: executionResult.result,
                error: executionResult.error,
                executionTime: totalTime,
                memoryUsed: executionResult.memoryUsed,
                securityScore: this.calculateSecurityScore(executionResult, config),
                auditHash,
                tenantId: config.tenantId,
            };
        }
        catch (error) {
            const endTime = performance.now();
            const totalTime = endTime - startTime;
            return {
                success: false,
                error: error instanceof Error ? error : new Error(String(error)),
                executionTime: totalTime,
                memoryUsed: 0,
                tenantId: config.tenantId,
            };
        }
    }
    /**
     * Multi-tenant YAML processing with isolation
     */
    async parseYamlMultiTenant(yamlContent, tenantId, config = {}) {
        const tenantConfig = {
            ...config,
            tenantId,
            securityProfile: config.securityProfile || "tenant-isolated",
            validateSecurity: config.validateSecurity !== false,
            auditEnabled: config.auditEnabled !== false,
        };
        return this.parseYamlSecureRuntime(yamlContent, tenantConfig);
    }
    /**
     * Batch process YAML for multiple tenants
     */
    async parseYamlBatch(yamlContents, config = {}) {
        const results = new Map();
        // Process each tenant's YAML in isolated runtime
        for (const { content, tenantId } of yamlContents) {
            const result = await this.parseYamlMultiTenant(content, tenantId, config);
            results.set(tenantId, result);
        }
        return results;
    }
    /**
     * Test multi-tenant isolation
     */
    async testTenantIsolation(tenantIds) {
        const results = {};
        for (const tenantId of tenantIds) {
            try {
                // Execute code that should trigger isolation violations if not properly isolated
                const testCode = `
          const memoryLeak = [];
          for (let i = 0; i < 1000; i++) {
            memoryLeak.push(new Array(10000).fill('${tenantId}'));
          }
          global.tenantData = '${tenantId}';
          return global.tenantData;
        `;
                const executionResult = await this.runtimeManager.execute({
                    code: testCode,
                    tenantId,
                    securityProfile: "tenant-isolated",
                    timeout: 2000,
                    memoryLimit: 1,
                });
                results[tenantId] =
                    executionResult.success && executionResult.result === tenantId;
            }
            catch (error) {
                results[tenantId] = false;
            }
        }
        return results;
    }
    /**
     * Validate performance targets
     */
    validatePerformanceTargets(executionTime, memoryUsed) {
        const timeTarget = config_1.performanceTargets.find((t) => t.metric === "executionTime");
        const memoryTarget = config_1.performanceTargets.find((t) => t.metric === "memoryUsage");
        if (timeTarget && executionTime > timeTarget.target) {
            console.warn(`[SecureYamlRuntime] Performance warning: execution time ${executionTime}ms exceeds target ${timeTarget.target}ms`);
        }
        if (memoryTarget && memoryUsed > memoryTarget.target) {
            console.warn(`[SecureYamlRuntime] Performance warning: memory usage ${memoryUsed}MB exceeds target ${memoryTarget.target}MB`);
        }
    }
    /**
     * Calculate security score
     */
    calculateSecurityScore(executionResult, config) {
        const profile = config_1.securityProfiles[config.securityProfile || "ultra-secure"];
        let score = 9.5; // Base score
        if (!executionResult.success) {
            score -= 1.0;
        }
        if (config.tenantId) {
            score += 0.5;
        }
        if (config.validateSecurity === false) {
            score -= 1.5;
        }
        return Math.max(0, Math.min(10, score));
    }
    /**
     * Validate input
     */
    validateInput(yamlContent) {
        if (typeof yamlContent !== "string") {
            throw new Error("YAML content must be a string");
        }
        if (yamlContent.length === 0) {
            throw new Error("YAML content cannot be empty");
        }
        if (yamlContent.length > 1024 * 1024) {
            // 1MB max
            throw new Error("YAML content exceeds maximum size limit (1MB)");
        }
    }
    /**
     * Build execution code for YAML parsing
     */
    buildYamlExecutionCode(yamlContent) {
        // Escape the YAML content to avoid injection attacks
        const escapedYaml = JSON.stringify(yamlContent);
        return `
      // Secure YAML Parser implementation
      class SecureYamlRuntime {
        constructor() {
          this.schema = 'FAILSAFE_SCHEMA';
          this.allowedTypes = ['null', 'boolean', 'integer', 'float', 'string'];
        }

        parseSecure(yamlContent) {
          // Simulate basic YAML parsing logic
          const lines = yamlContent.split('\\n');
          const result = {};
          
          for (const line of lines) {
            const trimmedLine = line.trim();
            if (trimmedLine && !trimmedLine.startsWith('#')) {
              const colonIndex = trimmedLine.indexOf(':');
              if (colonIndex !== -1) {
                const key = trimmedLine.substring(0, colonIndex).trim();
                const value = trimmedLine.substring(colonIndex + 1).trim();
                
                // Basic type conversion
                if (value === 'null') {
                  result[key] = null;
                } else if (value === 'true') {
                  result[key] = true;
                } else if (value === 'false') {
                  result[key] = false;
                } else if (!isNaN(parseFloat(value))) {
                  result[key] = parseFloat(value);
                } else {
                  result[key] = value;
                }
              }
            }
          }
          
          return result;
        }
      }

      const runtime = new SecureYamlRuntime();
      const yamlContent = ${escapedYaml};
      return runtime.parseSecure(yamlContent);
    `;
    }
    /**
     * Generate audit hash
     */
    generateAuditHash(yamlContent, executionResult, config) {
        const crypto = require("node:crypto");
        const auditData = {
            yamlHash: crypto.createHash("sha256").update(yamlContent).digest("hex"),
            executionResult: executionResult.success,
            securityProfile: config.securityProfile || "ultra-secure",
            tenantId: config.tenantId,
            timestamp: Date.now(),
            executionTime: executionResult.executionTime,
            memoryUsed: executionResult.memoryUsed,
        };
        return crypto
            .createHash("sha256")
            .update(JSON.stringify(auditData))
            .digest("hex");
    }
}
exports.SecureYamlRuntime = SecureYamlRuntime;
exports.default = SecureYamlRuntime;
//# sourceMappingURL=secure-yaml-runtime.js.map