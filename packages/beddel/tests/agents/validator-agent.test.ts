import { z } from "zod";
import {
  ValidatorAgent,
  ValidationError,
  ValidationOptions,
} from "../../src/agents/translator-agents";

describe("ValidatorAgent - Enhanced Validation Tests", () => {
  // Test schema for different validation scenarios
  const userSchema = z.object({
    name: z.string().min(2).max(50),
    email: z.string().email(),
    age: z.number().min(18).max(120),
    active: z.boolean().optional(),
  });

  const complexSchema = z.object({
    users: z.array(userSchema).min(1),
    metadata: z.object({
      version: z.string().regex(/^\d+\.\d+\.\d+$/),
      timestamp: z.string().datetime(),
    }),
  });

  beforeEach(() => {
    // Clear schema cache before each test
    ValidatorAgent["schemaCache"].clear();
  });

  describe("validateInput - Basic Functionality", () => {
    it("should successfully validate valid data", () => {
      const validData = {
        name: "John Doe",
        email: "john@example.com",
        age: 25,
        active: true,
      };

      const result = ValidatorAgent.validateInput(userSchema, validData);
      expect(result).toEqual(validData);
    });

    it("should throw ValidationError for invalid data", () => {
      const invalidData = {
        name: "J",
        email: "invalid-email",
        age: 16,
      };

      expect(() =>
        ValidatorAgent.validateInput(userSchema, invalidData)
      ).toThrow(ValidationError);
    });

    it("should provide detailed error information", () => {
      const invalidData = {
        name: "",
        email: "not-an-email",
        age: 15,
      };

      try {
        ValidatorAgent.validateInput(userSchema, invalidData);
        fail("Should have thrown ValidationError");
      } catch (error) {
        expect(error).toBeInstanceOf(ValidationError);
        const validationError = error as ValidationError;
        expect(validationError.campo).toBe("name");
        expect(validationError.codigo).toBe("VALIDATION_ERROR");
        expect(validationError.issues).toBeDefined();
        expect(validationError.issues?.length).toBeGreaterThan(0);
      }
    });
  });

  describe("safeValidate - Non-throwing variant", () => {
    it("should return success result for valid data", () => {
      const validData = { name: "Jane", email: "jane@example.com", age: 30 };

      const result = ValidatorAgent.safeValidate(userSchema, validData);
      expect(result.success).toBe(true);
      expect(result.data).toEqual(validData);
      expect(result.error).toBeUndefined();
    });

    it("should return error result for invalid data", () => {
      const invalidData = { name: "", email: "invalid", age: 16 };

      const result = ValidatorAgent.safeValidate(userSchema, invalidData);
      expect(result.success).toBe(false);
      expect(result.data).toBeUndefined();
      expect(result.error).toBeDefined();
      expect(result.error?.codigo).toBe("VALIDATION_ERROR");
      expect(result.error?.issues?.length).toBeGreaterThan(0);
    });

    it("should handle unknown errors gracefully", () => {
      const result = ValidatorAgent.safeValidate(userSchema, {
        notAProperty: true,
      });
      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
    });
  });

  describe("Schema Caching", () => {
    it("should cache schemas for better performance", () => {
      const schemaId = "user-schema";
      const validData = { name: "Test", email: "test@example.com", age: 20 };

      // Create cached validator
      const cachedValidator = ValidatorAgent.createCachedValidator(
        userSchema,
        schemaId
      );

      // Use cached validator multiple times
      const result1 = cachedValidator(validData);
      const result2 = cachedValidator({ ...validData, name: "Test2" });

      expect(result1).toEqual(validData);
      expect(result2.name).toBe("Test2");

      // Check cache was used
      const cache = ValidatorAgent["schemaCache"];
      expect(cache.has(schemaId)).toBe(true);
      expect(cache.size).toBe(1);
    });

    it("should handle cache misses correctly", () => {
      const cache = ValidatorAgent["schemaCache"];
      expect(cache.size).toBe(0);
    });
  });

  describe("createValidator - Pre-configured validators", () => {
    it("should create validator with pre-configured schema", () => {
      const validator = ValidatorAgent.createValidator(userSchema);
      const validData = {
        name: "Config",
        email: "config@example.com",
        age: 22,
      };

      const result = validator(validData);
      expect(result).toEqual(validData);
    });
  });

  describe("Complex Validation Scenarios", () => {
    it("should handle nested object validation", () => {
      const validComplexData = {
        users: [
          { name: "User1", email: "user1@example.com", age: 25 },
          { name: "User2", email: "user2@example.com", age: 30, active: false },
        ],
        metadata: {
          version: "1.0.0",
          timestamp: "2023-01-01T00:00:00Z",
        },
      };

      const result = ValidatorAgent.validateInput(
        complexSchema,
        validComplexData
      );
      expect(result.users).toHaveLength(2);
      expect(result.metadata.version).toBe("1.0.0");
    });

    it("should handle array validation errors", () => {
      const invalidData = {
        users: [
          { name: "", email: "invalid", age: 10 }, // Multiple errors
        ],
        metadata: {
          version: "invalid-version",
          timestamp: "not-a-datetime",
        },
      };

      try {
        ValidatorAgent.validateInput(complexSchema, invalidData);
        fail("Should have thrown ValidationError");
      } catch (error) {
        const validationError = error as ValidationError;
        expect(validationError.issues?.length).toBeGreaterThan(0);

        // Should have multiple validation issues
        const fieldErrors = validationError.issues?.map((issue) =>
          issue.path.join(".")
        );
        expect(fieldErrors).toContain("users.0.name");
        expect(fieldErrors).toContain("users.0.age");
      }
    });
  });

  describe("Validation Options", () => {
    it("should respect abortEarly option", () => {
      const options: ValidationOptions = { abortEarly: true };
      const invalidData = { name: "", email: "", age: 0 };

      try {
        ValidatorAgent.validateInput(userSchema, invalidData, options);
        fail("Should have thrown ValidationError");
      } catch (error) {
        const validationError = error as ValidationError;
        // With abortEarly, should get fewer errors
        expect(validationError.issues?.length).toBeGreaterThanOrEqual(1);
      }
    });

    it("should handle stripUnknown option", () => {
      const dataWithExtra = {
        name: "Test",
        email: "test@example.com",
        age: 25,
        extraField: "should-be-stripped",
        anotherExtra: 123,
      };

      const options: ValidationOptions = { stripUnknown: true };
      const result = ValidatorAgent.validateInput(
        userSchema,
        dataWithExtra,
        options
      );

      expect(result).toHaveProperty("name");
      expect(result).toHaveProperty("email");
      expect(result).toHaveProperty("age");
      expect(result).not.toHaveProperty("extraField");
      expect(result).not.toHaveProperty("anotherExtra");
    });
  });

  describe("Schema Validation", () => {
    it("should validate valid schema", () => {
      expect(ValidatorAgent.validateSchema(userSchema)).toBe(true);
    });

    it("should throw error for invalid schema", () => {
      // Create an object that looks like a schema but isn't
      const fakeSchema = { parse: () => {}, _def: {} } as any;
      expect(() => ValidatorAgent.validateSchema(fakeSchema)).toThrow(
        "Invalid Zod schema provided"
      );
    });
  });

  describe("Error Handling", () => {
    it("should handle non-Zod errors gracefully", () => {
      const invalidSchema = {
        parse: jest.fn(() => {
          throw new Error("Custom error");
        }),
      } as any;

      expect(() => ValidatorAgent.validateInput(invalidSchema, {})).toThrow(
        "Unexpected error during validation: Custom error"
      );
    });

    it("should provide meaningful error messages", () => {
      const emptyData = {};
      try {
        ValidatorAgent.validateInput(userSchema, emptyData);
      } catch (error) {
        const validationError = error as ValidationError;
        expect(validationError.mensagem).toContain("validation error(s) found");
        expect(validationError.campo).toBeDefined();
      }
    });
  });

  describe("Performance and Edge Cases", () => {
    it("should handle large datasets efficiently", () => {
      const schema = z.array(
        z.object({
          id: z.number(),
          data: z.string(),
        })
      );

      const largeArray = Array.from({ length: 1000 }, (_, i) => ({
        id: i,
        data: `item-${i}`,
      }));

      const startTime = Date.now();
      const result = ValidatorAgent.validateInput(schema, largeArray);
      const endTime = Date.now();

      expect(result).toHaveLength(1000);
      expect(endTime - startTime).toBeLessThan(100); // Should process in less than 100ms
    });

    it("should handle circular references gracefully", () => {
      const circularSchema = z.object({
        id: z.number(),
        parent: z.any().optional(),
      });

      const obj: any = { id: 1 };
      obj.parent = obj; // Create circular reference

      // Should validate without infinite loop
      const result = ValidatorAgent.validateInput(circularSchema, obj);
      expect(result.id).toBe(1);
      expect(result.parent).toBeDefined();
    });
  });

  describe("TypeScript Type Safety", () => {
    it("should maintain type safety for returned data", () => {
      const result = ValidatorAgent.validateInput(userSchema, {
        name: "TypeSafe",
        email: "safe@example.com",
        age: 25,
        active: true,
      });

      // TypeScript should recognize these properties
      const name: string = result.name;
      const age: number = result.age;
      const email: string = result.email;
      const active: boolean | undefined = result.active;

      expect(name).toBe("TypeSafe");
      expect(email).toBe("safe@example.com");
      expect(age).toBe(25);
      expect(active).toBe(true);
    });
  });
});

describe("ValidatorAgent Integration with Existing Components", () => {
  it("should integrate with existing translator schema", async () => {
    const { translatorSchema } = await import(
      "../../src/agents/translator-agents"
    );

    const validTranslationRequest = {
      texto: "Hello World",
      idioma_origem: "en",
      idioma_destino: "pt",
    };

    const result = ValidatorAgent.validateInput(
      translatorSchema,
      validTranslationRequest
    );
    expect(result).toEqual(validTranslationRequest);
  });

  it("should validate invalid translator requests", async () => {
    const { translatorSchema } = await import(
      "../../src/agents/translator-agents"
    );

    const invalidRequest = {
      texto: "", // Too short
      idioma_origem: "eng", // Too long
      idioma_destino: "pt",
    };

    try {
      ValidatorAgent.validateInput(translatorSchema, invalidRequest);
      fail("Should have thrown ValidationError");
    } catch (error) {
      const validationError = error as ValidationError;
      expect(validationError.codigo).toBe("VALIDATION_ERROR");
      expect(validationError.issues).toBeDefined();
    }
  });
});

describe("Benchmark Testing", () => {
  const simpleSchema = z.object({
    name: z.string().min(1),
    value: z.number(),
  });

  const complexSchema = z.array(
    z.object({
      id: z.number(),
      name: z.string().min(1),
      tags: z.array(z.string()),
      metadata: z.object({
        created: z.string().datetime(),
        updated: z.string().datetime(),
        version: z.string().regex(/^\d+\.\d+\.\d+$/),
      }),
    })
  );

  it("should validate simple schemas efficiently", () => {
    const testData = { name: "Test", value: 42 };
    const iterations = 1000;

    const startTime = Date.now();
    for (let i = 0; i < iterations; i++) {
      ValidatorAgent.validateInput(simpleSchema, testData);
    }
    const endTime = Date.now();

    const avgTime = (endTime - startTime) / iterations;
    expect(avgTime).toBeLessThan(5); // Average < 5ms per validation
  });

  it("should handle cached validators efficiently", () => {
    const cachedValidator = ValidatorAgent.createCachedValidator(
      simpleSchema,
      "benchmark-schema"
    );

    const testData = { name: "Cached", value: 123 };
    const iterations = 1000;

    const startTime = Date.now();
    for (let i = 0; i < iterations; i++) {
      cachedValidator(testData);
    }
    const endTime = Date.now();

    const avgTime = (endTime - startTime) / iterations;
    expect(avgTime).toBeLessThan(3); // Cached validation should be faster
  });
});
