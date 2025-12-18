"use strict";
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.runtimeManager = exports.SimpleIsolatedRuntimeManager = exports.IsolatedRuntimeError = void 0;
/**
 * Simple Isolated Runtime - Isolated VM v5 Implementation
 * Provides ultra-secure isolated execution environment with zero-trust architecture
 * Simplified version with core functionality
 */
const ivm = __importStar(require("isolated-vm"));
const config_1 = require("../config");
class IsolatedRuntimeError extends Error {
    constructor(message, code) {
        super(message);
        this.code = code;
        this.name = "IsolatedRuntimeError";
    }
}
exports.IsolatedRuntimeError = IsolatedRuntimeError;
/**
 * Simple Isolated Runtime Manager
 * Provides basic isolated execution functionality
 */
class SimpleIsolatedRuntimeManager {
    constructor(config = config_1.runtimeConfig) {
        this.config = config;
        this.metrics = new Map();
    }
    /**
     * Execute code in isolated environment
     */
    async execute(options) {
        const startTime = Date.now();
        try {
            // Validate input
            this.validateExecutionOptions(options);
            // Get security profile
            const profileName = options.securityProfile || this.config.defaultSecurityProfile;
            const securityProfile = config_1.securityProfiles[profileName];
            // Create isolated environment
            const result = await this.executeInIsolate(options, securityProfile);
            const executionTime = Date.now() - startTime;
            result.executionTime = executionTime;
            this.updateMetrics("executionTime", executionTime);
            this.updateMetrics("successRate", result.success ? 1 : 0);
            return result;
        }
        catch (error) {
            const executionTime = Date.now() - startTime;
            return {
                success: false,
                error: error instanceof Error ? error.message : String(error),
                executionTime,
                memoryUsed: 0,
                timestamp: new Date(),
            };
        }
    }
    /**
     * Execute code in isolated context
     */
    async executeInIsolate(options, securityProfile) {
        const startTime = Date.now();
        try {
            // Create isolate with memory limit
            const isolate = new ivm.Isolate({
                memoryLimit: securityProfile.memoryLimit,
            });
            // Create context
            const context = await isolate.createContext();
            try {
                // Setup execution
                const script = await isolate.compileScript(options.code);
                // Execute script
                const result = await script.run(context, {
                    timeout: options.timeout || securityProfile.timeout,
                });
                // Get memory usage
                const memoryUsed = await this.getMemoryUsage(isolate);
                return {
                    success: true,
                    result: result,
                    executionTime: Date.now() - startTime,
                    memoryUsed,
                    timestamp: new Date(),
                };
            }
            finally {
                // Always dispose isolate
                isolate.dispose();
            }
        }
        catch (error) {
            return {
                success: false,
                error: error instanceof Error ? error.message : String(error),
                executionTime: Date.now() - startTime,
                memoryUsed: 0,
                timestamp: new Date(),
            };
        }
    }
    /**
     * Get memory usage for isolate
     */
    async getMemoryUsage(isolate) {
        try {
            const stats = await isolate.getHeapStatistics();
            return (stats.used_heap_size || 0) / (1024 * 1024); // MB
        }
        catch (error) {
            return 0;
        }
    }
    /**
     * Validate execution options
     */
    validateExecutionOptions(options) {
        if (!options.code || typeof options.code !== "string") {
            throw new IsolatedRuntimeError("Code must be a non-empty string", "INVALID_CODE");
        }
        if (options.code.length > 1024 * 1024) {
            throw new IsolatedRuntimeError("Code exceeds maximum size limit (1MB)", "CODE_TOO_LARGE");
        }
        const memoryLimit = options.memoryLimit || this.config.memoryLimit;
        if (memoryLimit > 8) {
            throw new IsolatedRuntimeError("Memory limit exceeds maximum allowed (8MB)", "MEMORY_LIMIT_EXCEEDED");
        }
    }
    /**
     * Update metrics tracking
     */
    updateMetrics(metric, value) {
        if (!this.metrics.has(metric)) {
            this.metrics.set(metric, []);
        }
        const values = this.metrics.get(metric);
        values.push(value);
        // Keep only last 100 values
        if (values.length > 100) {
            values.shift();
        }
    }
    /**
     * Get current metrics
     */
    getMetrics() {
        return Object.fromEntries(this.metrics);
    }
}
exports.SimpleIsolatedRuntimeManager = SimpleIsolatedRuntimeManager;
// Singleton instance
exports.runtimeManager = new SimpleIsolatedRuntimeManager();
exports.default = SimpleIsolatedRuntimeManager;
//# sourceMappingURL=simpleRuntime.js.map