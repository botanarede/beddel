/**
 * Project-agnostic execution context contract for declarative runtimes.
 * Mirrors the shape used inside the Opal Support App but stays self-contained
 * so the npm package does not depend on repository-local files.
 */
export interface ExecutionContext {
    logs: string[];
    status: "running" | "success" | "error";
    output: unknown;
    error?: string;
    log: (message: string) => void;
    setOutput: (output: unknown) => void;
    setError: (error: string) => void;
}
export default ExecutionContext;
//# sourceMappingURL=executionContext.d.ts.map