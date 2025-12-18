import { type ZodIssue, type ZodTypeAny } from "zod";
export type DeclarativeSchemaDefinition = {
    type?: string;
    properties?: Record<string, DeclarativeSchemaDefinition>;
    items?: DeclarativeSchemaDefinition;
    required?: string[];
    enum?: Array<string | number | boolean>;
    minLength?: number;
    maxLength?: number;
    minItems?: number;
    maxItems?: number;
    additionalProperties?: boolean;
};
export type DeclarativeSchemaPhase = "input" | "output";
export declare class SchemaCompilationError extends Error {
    constructor(message: string);
}
export declare class DeclarativeSchemaValidationError extends Error {
    readonly phase: DeclarativeSchemaPhase;
    readonly issues: ZodIssue[];
    constructor(message: string, phase: DeclarativeSchemaPhase, issues: ZodIssue[]);
}
export declare class DeclarativeSchemaCompiler {
    private readonly cache;
    compile(definition: unknown, path: string): ZodTypeAny;
    clear(): void;
    get size(): number;
    private createCacheKey;
    private buildSchema;
    private buildObjectSchema;
    private buildArraySchema;
    private buildStringSchema;
    private buildEnumSchema;
}
//# sourceMappingURL=schemaCompiler.d.ts.map