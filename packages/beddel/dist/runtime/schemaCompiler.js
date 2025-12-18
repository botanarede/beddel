"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DeclarativeSchemaCompiler = exports.DeclarativeSchemaValidationError = exports.SchemaCompilationError = void 0;
const node_crypto_1 = require("node:crypto");
const zod_1 = require("zod");
class SchemaCompilationError extends Error {
    constructor(message) {
        super(message);
        this.name = "SchemaCompilationError";
    }
}
exports.SchemaCompilationError = SchemaCompilationError;
class DeclarativeSchemaValidationError extends Error {
    constructor(message, phase, issues) {
        super(message);
        this.phase = phase;
        this.issues = issues;
        this.name = "DeclarativeSchemaValidationError";
    }
}
exports.DeclarativeSchemaValidationError = DeclarativeSchemaValidationError;
class DeclarativeSchemaCompiler {
    constructor() {
        this.cache = new Map();
    }
    compile(definition, path) {
        const cacheKey = this.createCacheKey(definition, path);
        const cached = this.cache.get(cacheKey);
        if (cached) {
            return cached;
        }
        const schema = this.buildSchema(definition, path);
        this.cache.set(cacheKey, schema);
        return schema;
    }
    clear() {
        this.cache.clear();
    }
    get size() {
        return this.cache.size;
    }
    createCacheKey(definition, path) {
        const serialized = JSON.stringify(definition) ?? "undefined";
        const signature = (0, node_crypto_1.createHash)("sha256").update(serialized).digest("hex");
        return `${path}:${signature}`;
    }
    buildSchema(definition, path) {
        if (!definition ||
            typeof definition !== "object" ||
            Array.isArray(definition)) {
            throw new SchemaCompilationError(`Invalid schema at ${path}: expected object definition`);
        }
        const typedDefinition = definition;
        if (!typedDefinition.type || typeof typedDefinition.type !== "string") {
            throw new SchemaCompilationError(`Schema at ${path} must declare a string 'type'`);
        }
        switch (typedDefinition.type) {
            case "object":
                return this.buildObjectSchema(typedDefinition, path);
            case "array":
                return this.buildArraySchema(typedDefinition, path);
            case "string":
                return this.buildStringSchema(typedDefinition, path);
            case "number":
                return zod_1.z.number();
            case "integer":
                return zod_1.z.number().int();
            case "boolean":
                return zod_1.z.boolean();
            case "any":
                return zod_1.z.any();
            case "unknown":
                return zod_1.z.unknown();
            default:
                if (typedDefinition.enum) {
                    return this.buildEnumSchema(typedDefinition.enum, path);
                }
                throw new SchemaCompilationError(`Unsupported schema type '${typedDefinition.type}' at ${path}`);
        }
    }
    buildObjectSchema(definition, path) {
        const properties = definition.properties || {};
        if (typeof properties !== "object") {
            throw new SchemaCompilationError(`Object schema at ${path} must define 'properties' as an object`);
        }
        const requiredFields = new Set(definition.required || []);
        const shape = {};
        for (const [key, childDefinition] of Object.entries(properties)) {
            const childPath = `${path}.properties.${key}`;
            const childSchema = this.buildSchema(childDefinition, childPath);
            shape[key] = requiredFields.has(key)
                ? childSchema
                : childSchema.optional();
        }
        const objectSchema = zod_1.z.object(shape);
        if (definition.additionalProperties) {
            // Allow additional properties
            return objectSchema.passthrough();
        }
        else {
            // Reject additional properties (default behavior for strict validation)
            return objectSchema.strict();
        }
    }
    buildArraySchema(definition, path) {
        if (!definition.items) {
            throw new SchemaCompilationError(`Array schema at ${path} must define 'items'`);
        }
        const itemSchema = this.buildSchema(definition.items, `${path}.items`);
        let arraySchema = zod_1.z.array(itemSchema);
        if (typeof definition.minItems === "number") {
            arraySchema = arraySchema.min(definition.minItems);
        }
        if (typeof definition.maxItems === "number") {
            arraySchema = arraySchema.max(definition.maxItems);
        }
        return arraySchema;
    }
    buildStringSchema(definition, path) {
        let stringSchema = zod_1.z.string();
        if (typeof definition.minLength === "number") {
            stringSchema = stringSchema.min(definition.minLength);
        }
        if (typeof definition.maxLength === "number") {
            stringSchema = stringSchema.max(definition.maxLength);
        }
        if (definition.enum) {
            return this.buildEnumSchema(definition.enum, path);
        }
        return stringSchema;
    }
    buildEnumSchema(values, path) {
        if (!Array.isArray(values) || values.length === 0) {
            throw new SchemaCompilationError(`Enum at ${path} must be a non-empty array`);
        }
        const literals = values.map((value) => {
            if (typeof value === "string" ||
                typeof value === "number" ||
                typeof value === "boolean") {
                return zod_1.z.literal(value);
            }
            throw new SchemaCompilationError(`Enum at ${path} only supports string, number, or boolean values`);
        });
        if (literals.length === 1) {
            return literals[0];
        }
        const [first, second, ...rest] = literals;
        return zod_1.z.union([first, second, ...rest]);
    }
}
exports.DeclarativeSchemaCompiler = DeclarativeSchemaCompiler;
//# sourceMappingURL=schemaCompiler.js.map