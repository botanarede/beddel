import { IsolatedRuntimeManager } from "../runtime/isolatedRuntime";
export interface RuntimeYAMLConfig {
    securityProfile?: string;
    tenantId?: string;
    timeout?: number;
    memoryLimit?: number;
    validateSecurity?: boolean;
    auditEnabled?: boolean;
}
export interface RuntimeYAMLResult {
    success: boolean;
    result?: any;
    error?: Error;
    executionTime: number;
    memoryUsed: number;
    securityScore?: number;
    auditHash?: string;
    tenantId?: string;
}
export declare class SecureYamlRuntime {
    private runtimeManagerInstance;
    private readonly runtimeManager;
    private readonly securityScanner;
    constructor(runtimeManagerInstance: IsolatedRuntimeManager);
    /**
     * Parse YAML in isolated runtime environment
     */
    parseYamlSecureRuntime(yamlContent: string, config?: RuntimeYAMLConfig): Promise<RuntimeYAMLResult>;
    /**
     * Multi-tenant YAML processing with isolation
     */
    parseYamlMultiTenant(yamlContent: string, tenantId: string, config?: RuntimeYAMLConfig): Promise<RuntimeYAMLResult>;
    /**
     * Batch process YAML for multiple tenants
     */
    parseYamlBatch(yamlContents: Array<{
        content: string;
        tenantId: string;
    }>, config?: RuntimeYAMLConfig): Promise<Map<string, RuntimeYAMLResult>>;
    /**
     * Test multi-tenant isolation
     */
    testTenantIsolation(tenantIds: string[]): Promise<{
        [tenantId: string]: boolean;
    }>;
    /**
     * Validate performance targets
     */
    private validatePerformanceTargets;
    /**
     * Calculate security score
     */
    private calculateSecurityScore;
    /**
     * Validate input
     */
    private validateInput;
    /**
     * Build execution code for YAML parsing
     */
    private buildYamlExecutionCode;
    /**
     * Generate audit hash
     */
    private generateAuditHash;
}
export default SecureYamlRuntime;
//# sourceMappingURL=secure-yaml-runtime.d.ts.map