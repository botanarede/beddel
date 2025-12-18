import { DeclarativeAgentInterpreter } from "../../src/runtime/declarativeAgentRuntime";
import {
  DeclarativeSchemaCompiler,
  DeclarativeSchemaValidationError,
} from "../../src/runtime/schemaCompiler";
import type { ExecutionContext } from "../../src/types/executionContext";

const BASE_YAML = `
agent:
  id: schema-test
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0
metadata:
  name: Schema Test
  description: Ensures schema enforcement
  category: test
schema:
  input:
    type: "object"
    properties:
      message:
        type: "string"
    required: ["message"]
  output:
    type: "object"
    properties:
      response:
        type: "string"
    required: ["response"]
logic:
  variables:
    - name: "responseText"
      type: "string"
      init: '"pong"'
  workflow:
    - name: "emit"
      type: "output-generator"
      action:
        type: "generate"
        output:
          response: "$responseText"
`;

const OUTPUT_MISMATCH_YAML = `
agent:
  id: schema-test-output
  version: 1.0.0
  protocol: beddel-declarative-protocol/v2.0
metadata:
  name: Schema Test Output
  description: Ensures output validation
  category: test
schema:
  input:
    type: "object"
    properties: {}
    required: []
  output:
    type: "object"
    properties:
      response:
        type: "number"
    required: ["response"]
logic:
  variables:
    - name: "responseText"
      type: "string"
      init: '"pong"'
  workflow:
    - name: "emit"
      type: "output-generator"
      action:
        type: "generate"
        output:
          response: "$responseText"
`;

const createContext = (): ExecutionContext => {
  const context: ExecutionContext = {
    logs: [],
    status: "running",
    output: undefined,
    error: undefined,
    log: (message: string) => context.logs.push(message),
    setOutput: (output: unknown) => {
      context.output = output;
      context.status = "success";
    },
    setError: (error: string) => {
      context.error = error;
      context.status = "error";
    },
  };

  return context;
};

describe("DeclarativeAgentInterpreter schema enforcement", () => {
  it("executes workflow when payloads match the declared schemas", async () => {
    const interpreter = new DeclarativeAgentInterpreter();
    const context = createContext();

    const result = await interpreter.interpret({
      yamlContent: BASE_YAML,
      input: { message: "hello" },
      props: {},
      context,
    });

    expect(result).toEqual({ response: "pong" });
    expect(context.error).toBeUndefined();
  });

  it("throws DeclarativeSchemaValidationError and sets context error on invalid input", async () => {
    const interpreter = new DeclarativeAgentInterpreter();
    const context = createContext();

    await expect(
      interpreter.interpret({
        yamlContent: BASE_YAML,
        input: {},
        props: {},
        context,
      })
    ).rejects.toBeInstanceOf(DeclarativeSchemaValidationError);

    expect(context.error).toContain("Input validation failed");
  });

  it("rejects workflow output that violates the declared schema", async () => {
    const interpreter = new DeclarativeAgentInterpreter();
    const context = createContext();

    await expect(
      interpreter.interpret({
        yamlContent: OUTPUT_MISMATCH_YAML,
        input: {},
        props: {},
        context,
      })
    ).rejects.toBeInstanceOf(DeclarativeSchemaValidationError);

    expect(context.error).toContain("Output validation failed");
  });
});

describe("DeclarativeSchemaCompiler caching", () => {
  it("reuses compiled schemas for identical definitions to avoid recompilation", () => {
    const compiler = new DeclarativeSchemaCompiler();
    const schemaDefinition = { type: "string" };

    const first = compiler.compile(schemaDefinition, "schema.input");
    const second = compiler.compile({ ...schemaDefinition }, "schema.input");

    expect(first).toBe(second);
    expect(compiler.size).toBe(1);
  });
});
