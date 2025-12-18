import { createHash } from "node:crypto";
import { z, type ZodIssue, type ZodLiteral, type ZodTypeAny } from "zod";

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

export class SchemaCompilationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SchemaCompilationError";
  }
}

export class DeclarativeSchemaValidationError extends Error {
  constructor(
    message: string,
    public readonly phase: DeclarativeSchemaPhase,
    public readonly issues: ZodIssue[]
  ) {
    super(message);
    this.name = "DeclarativeSchemaValidationError";
  }
}

export class DeclarativeSchemaCompiler {
  private readonly cache = new Map<string, ZodTypeAny>();

  public compile(definition: unknown, path: string): ZodTypeAny {
    const cacheKey = this.createCacheKey(definition, path);
    const cached = this.cache.get(cacheKey);
    if (cached) {
      return cached;
    }

    const schema = this.buildSchema(definition, path);
    this.cache.set(cacheKey, schema);
    return schema;
  }

  public clear(): void {
    this.cache.clear();
  }

  public get size(): number {
    return this.cache.size;
  }

  private createCacheKey(definition: unknown, path: string): string {
    const serialized = JSON.stringify(definition) ?? "undefined";
    const signature = createHash("sha256").update(serialized).digest("hex");
    return `${path}:${signature}`;
  }

  private buildSchema(
    definition: unknown,
    path: string
  ): ZodTypeAny {
    if (
      !definition ||
      typeof definition !== "object" ||
      Array.isArray(definition)
    ) {
      throw new SchemaCompilationError(
        `Invalid schema at ${path}: expected object definition`
      );
    }

    const typedDefinition = definition as DeclarativeSchemaDefinition;
    if (!typedDefinition.type || typeof typedDefinition.type !== "string") {
      throw new SchemaCompilationError(
        `Schema at ${path} must declare a string 'type'`
      );
    }

    switch (typedDefinition.type) {
      case "object":
        return this.buildObjectSchema(typedDefinition, path);
      case "array":
        return this.buildArraySchema(typedDefinition, path);
      case "string":
        return this.buildStringSchema(typedDefinition, path);
      case "number":
        return z.number();
      case "integer":
        return z.number().int();
      case "boolean":
        return z.boolean();
      case "any":
        return z.any();
      case "unknown":
        return z.unknown();
      default:
        if (typedDefinition.enum) {
          return this.buildEnumSchema(typedDefinition.enum, path);
        }
        throw new SchemaCompilationError(
          `Unsupported schema type '${typedDefinition.type}' at ${path}`
        );
    }
  }

  private buildObjectSchema(
    definition: DeclarativeSchemaDefinition,
    path: string
  ): ZodTypeAny {
    const properties = definition.properties || {};
    if (typeof properties !== "object") {
      throw new SchemaCompilationError(
        `Object schema at ${path} must define 'properties' as an object`
      );
    }

    const requiredFields = new Set(definition.required || []);
    const shape: Record<string, ZodTypeAny> = {};

    for (const [key, childDefinition] of Object.entries(properties)) {
      const childPath = `${path}.properties.${key}`;
      const childSchema = this.buildSchema(childDefinition, childPath);
      shape[key] = requiredFields.has(key)
        ? childSchema
        : childSchema.optional();
    }

    const objectSchema = z.object(shape);
    if (definition.additionalProperties) {
      // Allow additional properties
      return objectSchema.passthrough() as ZodTypeAny;
    } else {
      // Reject additional properties (default behavior for strict validation)
      return objectSchema.strict() as ZodTypeAny;
    }
  }

  private buildArraySchema(
    definition: DeclarativeSchemaDefinition,
    path: string
  ): ZodTypeAny {
    if (!definition.items) {
      throw new SchemaCompilationError(
        `Array schema at ${path} must define 'items'`
      );
    }

    const itemSchema = this.buildSchema(definition.items, `${path}.items`);
    let arraySchema = z.array(itemSchema);

    if (typeof definition.minItems === "number") {
      arraySchema = arraySchema.min(definition.minItems);
    }

    if (typeof definition.maxItems === "number") {
      arraySchema = arraySchema.max(definition.maxItems);
    }

    return arraySchema;
  }

  private buildStringSchema(
    definition: DeclarativeSchemaDefinition,
    path: string
  ): ZodTypeAny {
    let stringSchema = z.string();

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

  private buildEnumSchema(
    values: Array<string | number | boolean>,
    path: string
  ): ZodTypeAny {
    if (!Array.isArray(values) || values.length === 0) {
      throw new SchemaCompilationError(
        `Enum at ${path} must be a non-empty array`
      );
    }

    const literals = values.map((value) => {
      if (
        typeof value === "string" ||
        typeof value === "number" ||
        typeof value === "boolean"
      ) {
        return z.literal(value);
      }

      throw new SchemaCompilationError(
        `Enum at ${path} only supports string, number, or boolean values`
      );
    });

    if (literals.length === 1) {
      return literals[0];
    }

    const [first, second, ...rest] = literals;
    return z.union(
      [first, second, ...rest] as [
        ZodLiteral<string | number | boolean>,
        ZodLiteral<string | number | boolean>,
        ...ZodLiteral<string | number | boolean>[]
      ]
    );
  }
}
