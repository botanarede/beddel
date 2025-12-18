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
exports.runtimeManager = exports.IsolatedRuntimeManager = exports.IsolatedRuntimeError = void 0;
/**
 * Isolated Runtime Manager - Isolated VM v5 Implementation
 * Provides ultra-secure isolated execution environment with zero-trust architecture
 */
const ivm = __importStar(require("isolated-vm"));
const config_1 = require("../config");
const events_1 = require("events");
const scanner_1 = require("../security/scanner");
class IsolatedRuntimeError extends Error {
    constructor(message, code, context) {
        super(message);
        this.code = code;
        this.context = context;
        this.name = "IsolatedRuntimeError";
    }
}
exports.IsolatedRuntimeError = IsolatedRuntimeError;
class IsolatedRuntimeManager extends events_1.EventEmitter {
    constructor(config = config_1.runtimeConfig) {
        super();
        this.config = config;
        this.isolates = new Map();
        this.pool = [];
        this.activeExecutions = new Map();
        this.metrics = new Map();
        this.maxPoolSize = config.maxPoolSize;
        this.minPoolSize = config.minPoolSize;
        // Initialize pool with minimum isolates
        this.initializePool();
        // Setup periodic cleanup
        this.cleanupInterval = setInterval(() => this.cleanupPool(), config.metricsInterval);
    }
    /**
     * Initialize the isolate pool with minimum required isolates
     */
    async initializePool() {
        const profiles = Object.keys(config_1.securityProfiles);
        for (let i = 0; i < this.minPoolSize; i++) {
            const profileName = profiles[i % profiles.length];
            const securityProfile = config_1.securityProfiles[profileName];
            try {
                const runtimeContext = await this.createIsolate(securityProfile);
                this.pool.push(runtimeContext);
            }
            catch (error) {
                this.emit("error", new IsolatedRuntimeError(`Failed to create isolate for profile ${profileName}`, "POOL_INIT_ERROR", { error, profileName }));
            }
        }
        this.emit("pool-initialized", {
            poolSize: this.pool.length,
            profiles: profiles,
        });
    }
    /**
     * Create a new isolated context with specified security profile
     */
    async createIsolate(securityProfile) {
        const startTime = Date.now();
        try {
            // Create isolate with memory limit
            const isolate = new ivm.Isolate({
                memoryLimit: securityProfile.memoryLimit,
            });
            // Create context with security restrictions
            const context = await isolate.createContext();
            // Setup jail environment
            const jail = context.global;
            // Remove access to dangerous functions
            await jail.set("global", jail.derefInto());
            await jail.set("_globalThis", jail.derefInto());
            await jail.set("require", new ivm.Reference(undefined));
            await jail.set("eval", new ivm.Reference(undefined));
            await jail.set("Function", new ivm.Reference(undefined));
            await jail.set("process", new ivm.Reference(undefined));
            // Add safe globals
            await jail.set("console", {
                log: (message) => this.emit("log", { message, level: "info" }),
                error: (message) => this.emit("log", { message, level: "error" }),
                warn: (message) => this.emit("log", { message, level: "warn" }),
                info: (message) => this.emit("log", { message, level: "info" }),
            });
            // Add limited utility functions
            await jail.set("setTimeout", undefined); // Disable timers
            await jail.set("setInterval", undefined);
            await jail.set("clearTimeout", undefined);
            await jail.set("clearInterval", undefined);
            // Add allowed modules if any
            if (securityProfile.allowedModules.length > 0) {
                const allowedModules = {};
                for (const moduleName of securityProfile.allowedModules) {
                    try {
                        // Only allow specific safe modules
                        if (["lodash", "moment", "uuid"].includes(moduleName)) {
                            allowedModules[moduleName] = require(moduleName);
                        }
                    }
                    catch (error) {
                        // Module not available, continue
                    }
                }
                await jail.set("modules", allowedModules);
            }
            const creationTime = Date.now() - startTime;
            return {
                isolate,
                context,
                jail,
                executionCount: 0,
                createdAt: new Date(),
                lastUsedAt: new Date(),
                memoryUsage: 0,
                securityProfile,
            };
        }
        catch (error) {
            throw new IsolatedRuntimeError("Failed to create isolated context", "ISOLATE_CREATION_ERROR", { error, securityProfile, creationTime: Date.now() - startTime });
        }
    }
    /**
     * Execute code in isolated environment
     */
    async execute(options) {
        const startTime = Date.now();
        const executionId = this.generateExecutionId();
        try {
            // Validate input
            this.validateExecutionOptions(options);
            // Security scan if enabled
            if (options.scanForSecurity !== false) {
                const securityScanner = new scanner_1.SecurityScanner();
                // Scan the code for security issues
                const scanResult = await securityScanner.scan({
                    code: options.code,
                    executionId: executionId,
                });
                if (!scanResult.secure) {
                    throw new IsolatedRuntimeError(`Security scan failed: ${scanResult.warnings.join(", ")}`, "SECURITY_SCAN_FAILED", { scanResult });
                }
            }
            // Get security profile
            const securityProfile = config_1.securityProfiles[options.securityProfile || this.config.defaultSecurityProfile];
            // Get or create isolate
            const runtimeContext = await this.getOrCreateIsolate(securityProfile);
            // Execute in isolate
            const result = await this.executeInIsolate(runtimeContext, options, executionId);
            // Update metrics
            const executionTime = Date.now() - startTime;
            this.updateMetrics("executionTime", executionTime);
            this.updateMetrics("successRate", result.success ? 1 : 0);
            result.executionTime = executionTime;
            // Generate audit hash if audit enabled
            if (this.config.auditEnabled) {
                result.auditHash = this.generateAuditHash(options, result);
            }
            this.emit("execution-complete", { executionId, result, executionTime });
            return result;
        }
        catch (error) {
            const executionTime = Date.now() - startTime;
            const result = {
                success: false,
                error: error instanceof Error ? error : new Error(String(error)),
                executionTime,
                memoryUsed: 0,
                timestamp: new Date(),
            };
            this.updateMetrics("executionTime", executionTime);
            this.updateMetrics("successRate", 0);
            this.emit("execution-error", { executionId, error, executionTime });
            return result;
        }
    }
    /**
     * Execute code in specific isolate context
     */
    async executeInIsolate(runtimeContext, options, executionId) {
        const { isolate, context, jail } = runtimeContext;
        const startTime = Date.now();
        // Update usage stats
        runtimeContext.executionCount++;
        runtimeContext.lastUsedAt = new Date();
        try {
            // Create script with timeout and memory limit
            const script = await isolate.compileScript(options.code, {
                filename: `beddel-runtime-${executionId}.js`,
                produceCachedData: false, // Security: disable code caching
            });
            // Setup execution context
            const executionContext = new ivm.Reference({
                ...(options.context || {}),
                executionId,
                timestamp: new Date().toISOString(),
            });
            // Execute script
            const result = await script.run(context, {
                timeout: options.timeout || runtimeContext.securityProfile.timeout,
                release: true, // Release memory after execution
            });
            // Get memory usage
            const memoryUsed = this.getMemoryUsage(runtimeContext);
            const executionTime = Date.now() - startTime;
            return {
                success: true,
                result: result,
                executionTime,
                memoryUsed,
                timestamp: new Date(),
            };
        }
        catch (error) {
            const executionTime = Date.now() - startTime;
            return {
                success: false,
                error: error instanceof Error ? error : new Error(String(error)),
                executionTime,
                memoryUsed: this.getMemoryUsage(runtimeContext),
                timestamp: new Date(),
            };
        }
    }
    /**
     * Get or create isolate for execution
     */
    async getOrCreateIsolate(securityProfile) {
        // Check pool for available isolate
        const availableIsolate = this.pool.find((ctx) => ctx.securityProfile.name === securityProfile.name);
        if (availableIsolate) {
            // Remove from pool and return
            this.pool = this.pool.filter((ctx) => ctx !== availableIsolate);
            return availableIsolate;
        }
        // Check if we can create new isolate
        const totalIsolates = this.isolates.size + this.pool.length;
        if (totalIsolates >= this.maxPoolSize) {
            throw new IsolatedRuntimeError(`Maximum isolate pool size reached (${this.maxPoolSize})`, "POOL_LIMIT_EXCEEDED", { currentPoolSize: totalIsolates, maxPoolSize: this.maxPoolSize });
        }
        // Create new isolate
        return await this.createIsolate(securityProfile);
    }
    /**
     * Validate execution options
     */
    validateExecutionOptions(options) {
        if (!options.code || typeof options.code !== "string") {
            throw new IsolatedRuntimeError("Code must be a non-empty string", "INVALID_CODE", { codeType: typeof options.code, codeLength: options.code?.length });
        }
        if (options.code.length > 1024 * 1024) {
            // 1MB max code size
            throw new IsolatedRuntimeError("Code exceeds maximum size limit (1MB)", "CODE_TOO_LARGE", { codeSize: options.code.length });
        }
        const memoryLimit = options.memoryLimit || this.config.memoryLimit;
        if (memoryLimit > 8) {
            // 8MB max
            throw new IsolatedRuntimeError("Memory limit exceeds maximum allowed (8MB)", "MEMORY_LIMIT_EXCEEDED", { requestedMemory: memoryLimit, maxMemory: 8 });
        }
        const timeout = options.timeout || config_1.runtimeConfig.timeout;
        if (timeout > 30000) {
            // 30s max
            throw new IsolatedRuntimeError("Timeout exceeds maximum allowed (30s)", "TIMEOUT_EXCEEDED", { requestedTimeout: timeout, maxTimeout: 30000 });
        }
    }
    /**
     * Calculate memory usage for isolate
     */
    getMemoryUsage(runtimeContext) {
        try {
            const heapStatistics = runtimeContext.isolate.getHeapStatisticsSync();
            return (heapStatistics.used_heap_size || 0) / (1024 * 1024); // MB
        }
        catch (error) {
            this.emit("error", {
                message: "Failed to get memory usage",
                error,
                context: "getMemoryUsage",
            });
            return 0;
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
        // Keep only last 1000 values
        if (values.length > 1000) {
            values.shift();
        }
    }
    /**
     * Generate unique execution ID
     */
    generateExecutionId() {
        return `exec-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }
    /**
     * Generate audit hash for execution
     */
    generateAuditHash(options, result) {
        const crypto = require("node:crypto");
        const auditData = {
            code: options.code,
            context: options.context,
            result: result.result,
            success: result.success,
            executionTime: result.executionTime,
            memoryUsed: result.memoryUsed,
            timestamp: result.timestamp,
            tenantId: options.tenantId,
        };
        return crypto
            .createHash(this.config.auditHashAlgorithm)
            .update(JSON.stringify(auditData))
            .digest("hex");
    }
    /**
     * Cleanup idle isolates
     */
    cleanupPool() {
        const now = Date.now();
        const idleTimeout = this.config.poolIdleTimeout;
        // Cleanup pool isolates that have been idle too long
        this.pool = this.pool.filter((isolate) => {
            const idleTime = now - isolate.lastUsedAt.getTime();
            const shouldCleanup = idleTime > idleTimeout && this.pool.length > this.minPoolSize;
            if (shouldCleanup) {
                try {
                    isolate.isolate.dispose();
                    this.emit("isolate-disposed", {
                        isolateId: isolate.createdAt.getTime(),
                        idleTime,
                        reason: "idle-cleanup",
                    });
                }
                catch (error) {
                    this.emit("error", new IsolatedRuntimeError("Failed to dispose isolate during cleanup", "DISPOSE_ERROR", { error, idleTime }));
                }
            }
            return !shouldCleanup;
        });
    }
    /**
     * Get current metrics
     */
    getMetrics() {
        return Object.fromEntries(this.metrics);
    }
    /**
     * Get pool statistics
     */
    getPoolStats() {
        return {
            totalIsolates: this.isolates.size + this.pool.length,
            poolSize: this.pool.length,
            activeExecutions: this.activeExecutions.size,
            minPoolSize: this.minPoolSize,
            maxPoolSize: this.maxPoolSize,
        };
    }
    /**
     * Dispose of all isolates and cleanup resources
     */
    async dispose() {
        clearInterval(this.cleanupInterval);
        // Dispose all pool isolates
        for (const isolate of this.pool) {
            try {
                isolate.isolate.dispose();
            }
            catch (error) {
                this.emit("error", {
                    message: "Failed to dispose isolate during cleanup",
                    error,
                });
            }
        }
        this.pool = [];
        this.activeExecutions.clear();
        this.emit("disposed", { cleanupTime: Date.now() });
    }
}
exports.IsolatedRuntimeManager = IsolatedRuntimeManager;
// Singleton instance
exports.runtimeManager = new IsolatedRuntimeManager();
exports.default = IsolatedRuntimeManager;
//# sourceMappingURL=isolatedRuntime.js.map