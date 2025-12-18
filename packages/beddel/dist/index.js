"use strict";
/**
 * Beddel - Parser YAML seguro com FAILSAFE_SCHEMA e Runtime Isolado
 *
 * Open source package para parsing YAML com foco máximo em segurança
 * Implementa FAILSAFE_SCHEMA, validações rigorosas, runtime isolado e multi-tenant isolation
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.Server = exports.SecureYamlRuntime = exports.LGPDCompliance = exports.GDPRCompliance = exports.MultiTenantFirebaseManager = exports.AutoScaler = exports.PerformanceMonitor = exports.AuditService = exports.ThreatMLModel = exports.AnomalyDetector = exports.ThreatDetectionEngine = exports.securityDashboard = exports.SecurityDashboard = exports.securityMonitor = exports.SecurityMonitor = exports.SecurityManager = exports.SecurityScore = exports.SecurityScanner = exports.YAMLPerformanceError = exports.YAMLSecurityError = exports.YAMLParseError = exports.YAMLBaseError = exports.auditConfig = exports.performanceTargets = exports.securityProfiles = exports.runtimeConfig = exports.agentRegistry = exports.AgentRegistry = exports.SchemaCompilationError = exports.DeclarativeSchemaValidationError = exports.DeclarativeSchemaCompiler = exports.declarativeInterpreter = exports.DeclarativeAgentInterpreter = exports.SimpleRuntimeError = exports.simpleRuntimeManager = exports.SimpleIsolatedRuntimeManager = exports.runtimeManager = exports.IsolatedRuntimeManager = exports.parseSecureYaml = exports.createSecureYamlParser = exports.SecureYamlParser = void 0;
// YAML Parser exports
var secure_yaml_parser_1 = require("./parser/secure-yaml-parser");
Object.defineProperty(exports, "SecureYamlParser", { enumerable: true, get: function () { return secure_yaml_parser_1.SecureYamlParser; } });
Object.defineProperty(exports, "createSecureYamlParser", { enumerable: true, get: function () { return secure_yaml_parser_1.createSecureYamlParser; } });
Object.defineProperty(exports, "parseSecureYaml", { enumerable: true, get: function () { return secure_yaml_parser_1.parseSecureYaml; } });
// Runtime Isolado exports
var isolatedRuntime_1 = require("./runtime/isolatedRuntime");
Object.defineProperty(exports, "IsolatedRuntimeManager", { enumerable: true, get: function () { return isolatedRuntime_1.IsolatedRuntimeManager; } });
Object.defineProperty(exports, "runtimeManager", { enumerable: true, get: function () { return isolatedRuntime_1.runtimeManager; } });
// Simple Runtime exports
var simpleRuntime_1 = require("./runtime/simpleRuntime");
Object.defineProperty(exports, "SimpleIsolatedRuntimeManager", { enumerable: true, get: function () { return simpleRuntime_1.SimpleIsolatedRuntimeManager; } });
Object.defineProperty(exports, "simpleRuntimeManager", { enumerable: true, get: function () { return simpleRuntime_1.runtimeManager; } });
Object.defineProperty(exports, "SimpleRuntimeError", { enumerable: true, get: function () { return simpleRuntime_1.IsolatedRuntimeError; } });
// Declarative runtime exports
var declarativeAgentRuntime_1 = require("./runtime/declarativeAgentRuntime");
Object.defineProperty(exports, "DeclarativeAgentInterpreter", { enumerable: true, get: function () { return declarativeAgentRuntime_1.DeclarativeAgentInterpreter; } });
Object.defineProperty(exports, "declarativeInterpreter", { enumerable: true, get: function () { return declarativeAgentRuntime_1.declarativeInterpreter; } });
var schemaCompiler_1 = require("./runtime/schemaCompiler");
Object.defineProperty(exports, "DeclarativeSchemaCompiler", { enumerable: true, get: function () { return schemaCompiler_1.DeclarativeSchemaCompiler; } });
Object.defineProperty(exports, "DeclarativeSchemaValidationError", { enumerable: true, get: function () { return schemaCompiler_1.DeclarativeSchemaValidationError; } });
Object.defineProperty(exports, "SchemaCompilationError", { enumerable: true, get: function () { return schemaCompiler_1.SchemaCompilationError; } });
// Agent registry exports
var agentRegistry_1 = require("./agents/agentRegistry");
Object.defineProperty(exports, "AgentRegistry", { enumerable: true, get: function () { return agentRegistry_1.AgentRegistry; } });
Object.defineProperty(exports, "agentRegistry", { enumerable: true, get: function () { return agentRegistry_1.agentRegistry; } });
// Configuration exports
var config_1 = require("./config");
Object.defineProperty(exports, "runtimeConfig", { enumerable: true, get: function () { return config_1.runtimeConfig; } });
Object.defineProperty(exports, "securityProfiles", { enumerable: true, get: function () { return config_1.securityProfiles; } });
Object.defineProperty(exports, "performanceTargets", { enumerable: true, get: function () { return config_1.performanceTargets; } });
Object.defineProperty(exports, "auditConfig", { enumerable: true, get: function () { return config_1.auditConfig; } });
// Error exports
var errors_1 = require("./errors");
Object.defineProperty(exports, "YAMLBaseError", { enumerable: true, get: function () { return errors_1.YAMLBaseError; } });
Object.defineProperty(exports, "YAMLParseError", { enumerable: true, get: function () { return errors_1.YAMLParseError; } });
Object.defineProperty(exports, "YAMLSecurityError", { enumerable: true, get: function () { return errors_1.YAMLSecurityError; } });
Object.defineProperty(exports, "YAMLPerformanceError", { enumerable: true, get: function () { return errors_1.YAMLPerformanceError; } });
// Security exports
var scanner_1 = require("./security/scanner");
Object.defineProperty(exports, "SecurityScanner", { enumerable: true, get: function () { return scanner_1.SecurityScanner; } });
var score_1 = require("./security/score");
Object.defineProperty(exports, "SecurityScore", { enumerable: true, get: function () { return score_1.SecurityScore; } });
var security_1 = require("./security");
Object.defineProperty(exports, "SecurityManager", { enumerable: true, get: function () { return security_1.SecurityManager; } });
Object.defineProperty(exports, "SecurityMonitor", { enumerable: true, get: function () { return security_1.SecurityMonitor; } });
Object.defineProperty(exports, "securityMonitor", { enumerable: true, get: function () { return security_1.securityMonitor; } });
Object.defineProperty(exports, "SecurityDashboard", { enumerable: true, get: function () { return security_1.SecurityDashboard; } });
Object.defineProperty(exports, "securityDashboard", { enumerable: true, get: function () { return security_1.securityDashboard; } });
Object.defineProperty(exports, "ThreatDetectionEngine", { enumerable: true, get: function () { return security_1.ThreatDetectionEngine; } });
Object.defineProperty(exports, "AnomalyDetector", { enumerable: true, get: function () { return security_1.AnomalyDetector; } });
Object.defineProperty(exports, "ThreatMLModel", { enumerable: true, get: function () { return security_1.ThreatMLModel; } });
var audit_1 = require("./runtime/audit");
Object.defineProperty(exports, "AuditService", { enumerable: true, get: function () { return audit_1.AuditService; } });
// Performance exports
var monitor_1 = require("./performance/monitor");
Object.defineProperty(exports, "PerformanceMonitor", { enumerable: true, get: function () { return monitor_1.PerformanceMonitor; } });
var autoscaling_1 = require("./performance/autoscaling");
Object.defineProperty(exports, "AutoScaler", { enumerable: true, get: function () { return __importDefault(autoscaling_1).default; } });
// Multi-Tenant Firebase exports
var tenantManager_1 = require("./firebase/tenantManager");
Object.defineProperty(exports, "MultiTenantFirebaseManager", { enumerable: true, get: function () { return tenantManager_1.MultiTenantFirebaseManager; } });
// Compliance exports
var gdprEngine_1 = require("./compliance/gdprEngine");
Object.defineProperty(exports, "GDPRCompliance", { enumerable: true, get: function () { return gdprEngine_1.GDPRCompliance; } });
var lgpdEngine_1 = require("./compliance/lgpdEngine");
Object.defineProperty(exports, "LGPDCompliance", { enumerable: true, get: function () { return lgpdEngine_1.LGPDCompliance; } });
// Integration: Secure YAML Parser with Isolated Runtime
var secure_yaml_runtime_1 = require("./integration/secure-yaml-runtime");
Object.defineProperty(exports, "SecureYamlRuntime", { enumerable: true, get: function () { return secure_yaml_runtime_1.SecureYamlRuntime; } });
// Server/runtime exports
exports.Server = __importStar(require("./server"));
//# sourceMappingURL=index.js.map