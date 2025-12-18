import { PerformanceMonitor } from "./monitor";
export interface BenchmarkResult {
    name: string;
    executionTime: number;
    memoryUsed: number;
    successCount: number;
    failureCount: number;
    securityScore: number;
    timestamp: Date;
}
export interface BenchmarkSuite {
    name: string;
    description: string;
    testCases: TestCase[];
}
export interface TestCase {
    name: string;
    code: string;
    expectedResult?: any;
    context?: Record<string, any>;
    securityProfile?: string;
    timeout?: number;
    memoryLimit?: number;
}
export declare class BenchmarkSystem {
    private performanceMonitor;
    private readonly sampleSize;
    private baselineResults;
    private isolateResults;
    private currentSuite?;
    constructor(performanceMonitor: PerformanceMonitor, sampleSize?: number);
    /**
     * Create standard benchmark test cases
     */
    private createStandardTestSuite;
    /**
     * Create security-focused test cases
     */
    private createSecurityTestSuite;
    /**
     * Create memory-intensive test cases
     */
    private createMemoryIntensiveSuite;
    /**
     * Create performance targets test suite
     */
    private createTargetedSuite;
    /**
     * Run comprehensive benchmark suite
     */
    runComprehensiveBenchmark(): Promise<{
        baseline: BenchmarkResult[];
        isolated: BenchmarkResult[];
        comparison: {
            executionTimeRatio: number;
            memoryRatio: number;
            successRateRatio: number;
            summary: string;
        };
    }>;
    /**
     * Run baseline execution (standard runtime)
     */
    private runSuiteBaseline;
    /**
     * Run single baseline test case
     */
    private runTestCaseBaseline;
    /**
     * Execute baseline code safely
     */
    private executeBaselineCode;
    /**
     * Run isolated execution benchmark
     */
    private runSuiteIsolated;
    /**
     * Run single isolated test case
     */
    private runTestCaseIsolated;
    /**
     * Generate comparison analysis
     */
    private generateComparison;
    /**
     * Generate performance report
     */
    generateReport(baseline: BenchmarkResult[], isolated: BenchmarkResult[]): string;
    /**
     * Quick performance check against targets
     */
    quickHealthCheck(): {
        isHealthy: boolean;
        issues: string[];
        metrics: {
            avgExecutionTime: number;
            avgMemoryUsage: number;
            successRate: number;
        };
    };
}
export declare let benchmarkSystem: BenchmarkSystem | null;
export declare function initializeBenchmarks(performanceMonitor: PerformanceMonitor): BenchmarkSystem;
//# sourceMappingURL=benchmark.d.ts.map