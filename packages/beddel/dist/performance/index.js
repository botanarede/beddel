"use strict";
/**
 * Performance Module - Index
 * Exports all performance monitoring capabilities for the Beddel runtime
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
var __exportStar = (this && this.__exportStar) || function(m, exports) {
    for (var p in m) if (p !== "default" && !Object.prototype.hasOwnProperty.call(exports, p)) __createBinding(exports, m, p);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getAutoscalingConfig = exports.initializeAutoscaling = exports.autoscaleSystem = exports.initializeBenchmarks = exports.benchmarkSystem = exports.performanceMonitor = void 0;
__exportStar(require("./monitor"), exports);
__exportStar(require("./benchmark"), exports);
__exportStar(require("./autoscaling"), exports);
// Export individual instances
var monitor_1 = require("./monitor");
Object.defineProperty(exports, "performanceMonitor", { enumerable: true, get: function () { return monitor_1.performanceMonitor; } });
var benchmark_1 = require("./benchmark");
Object.defineProperty(exports, "benchmarkSystem", { enumerable: true, get: function () { return benchmark_1.benchmarkSystem; } });
Object.defineProperty(exports, "initializeBenchmarks", { enumerable: true, get: function () { return benchmark_1.initializeBenchmarks; } });
var autoscaling_1 = require("./autoscaling");
Object.defineProperty(exports, "autoscaleSystem", { enumerable: true, get: function () { return autoscaling_1.autoscaleSystem; } });
Object.defineProperty(exports, "initializeAutoscaling", { enumerable: true, get: function () { return autoscaling_1.initializeAutoscaling; } });
Object.defineProperty(exports, "getAutoscalingConfig", { enumerable: true, get: function () { return autoscaling_1.getAutoscalingConfig; } });
//# sourceMappingURL=index.js.map