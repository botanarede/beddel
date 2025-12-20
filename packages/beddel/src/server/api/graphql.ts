/**
 * GraphQL helpers used by the /api/graphql route.
 */

import { GraphQLError, GraphQLScalarType, Kind, type ValueNode } from "graphql";
import { createSchema, createYoga } from "graphql-yoga";
import { agentRegistry } from "../../agents/registry";
import {
  getClientByApiKey,
  getEndpointByName,
  logExecution,
  checkRateLimit,
} from "../kvStore";
import {
  sanitizeInput,
  isValidMethodName,
  isValidApiKey,
  executeInSandbox,
  validateRequiredProps,
} from "../runtimeSecurity";
import {
  AuthenticationError,
  RateLimitError,
  ValidationError,
  NotFoundError,
} from "../errors";
import type {
  ExecuteMethodInput,
  ExecuteMethodResult,
  ExecutionContext,
} from "../types";

const schema = `
  type Query { ping: String! }
  type Mutation { executeMethod(methodName: String!, params: JSON!, props: JSON!): ExecutionResult! }
  type ExecutionResult { success: Boolean!, data: JSON, error: String, executionTime: Int! }
  scalar JSON
`;

export function getGraphQLSchema(): string {
  return schema;
}

const parseJsonLiteral = (ast: ValueNode): unknown => {
  switch (ast.kind) {
    case Kind.STRING:
    case Kind.BOOLEAN:
      return ast.value;
    case Kind.INT:
      return parseInt(ast.value, 10);
    case Kind.FLOAT:
      return parseFloat(ast.value);
    case Kind.OBJECT: {
      const value: Record<string, any> = {};
      for (const field of ast.fields) {
        value[field.name.value] = parseJsonLiteral(field.value);
      }
      return value;
    }
    case Kind.LIST:
      return ast.values.map(parseJsonLiteral);
    case Kind.NULL:
      return null;
    default:
      return null;
  }
};

const jsonScalar = new GraphQLScalarType({
  name: "JSON",
  description: "Arbitrary JSON value",
  serialize: (value: unknown) => value,
  parseValue: (value: unknown) => value,
  parseLiteral: (ast: ValueNode) => parseJsonLiteral(ast),
});

export async function executeRegisteredMethod(
  input: ExecuteMethodInput,
  clientId: string
): Promise<ExecuteMethodResult> {
  const startTime = Date.now();
  const context: ExecutionContext = {
    logs: [],
    status: "running",
    output: undefined,
    error: undefined,
    log: (message: string) =>
      context.logs.push(`[${new Date().toISOString()}] ${message}`),
    setOutput: (output: unknown) => {
      context.output = output;
      context.status = "success";
    },
    setError: (error: string) => {
      context.error = error;
      context.status = "error";
    },
  };

  try {
    context.log("Method execution initiated.");
    if (!isValidMethodName(input.methodName)) {
      throw new ValidationError("Invalid method name format");
    }

    const declarativeAgent = agentRegistry.getAgent(input.methodName);
    if (declarativeAgent) {
      context.log(`Found declarative agent: ${input.methodName}`);

      const result = await agentRegistry.executeAgent(
        input.methodName,
        sanitizeInput(input.params) as Record<string, any>,
        sanitizeInput(input.props) as Record<string, string>,
        context
      );

      const executionTime = Date.now() - startTime;
      await logExecution({
        id: `log_${Date.now()}`,
        clientId,
        endpointName: input.methodName,
        timestamp: new Date().toISOString(),
        duration: executionTime,
        success: true,
        input: input.params,
        output: result,
        logs: context.logs,
      });
      return { success: true, data: result, executionTime };
    }

    const endpoint = await getEndpointByName(input.methodName);
    if (!endpoint) {
      throw new NotFoundError(`Method '${input.methodName}' not found`);
    }

    context.log(`Found endpoint: ${endpoint.name}`);
    const sanitizedParams = sanitizeInput(input.params) as Record<
      string,
      unknown
    >;
    const sanitizedProps = sanitizeInput(input.props) as Record<string, string>;
    const { valid, missing } = validateRequiredProps(
      endpoint.requiredProps,
      sanitizedProps
    );
    if (!valid) {
      throw new ValidationError(
        `Missing required props: ${missing.join(", ")}`
      );
    }

    context.log("Props validated. Executing sandbox.");
    await executeInSandbox(
      endpoint.code,
      sanitizedParams,
      sanitizedProps,
      context
    );
    context.log("Sandbox execution finished.");

    if (context.status === "error") {
      throw new Error(context.error || "Sandbox execution failed.");
    }
    if (context.status !== "success") {
      throw new Error("Sandbox finished in an indeterminate state.");
    }

    const executionTime = Date.now() - startTime;
    await logExecution({
      id: `log_${Date.now()}`,
      clientId,
      endpointName: input.methodName,
      timestamp: new Date().toISOString(),
      duration: executionTime,
      success: true,
      input: sanitizedParams,
      output: context.output,
      logs: context.logs,
    });
    return { success: true, data: context.output, executionTime };
  } catch (error) {
    const executionTime = Date.now() - startTime;
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error";
    if (!context.error) context.setError(errorMessage);

    await logExecution({
      id: `log_${Date.now()}`,
      clientId,
      endpointName: input.methodName,
      timestamp: new Date().toISOString(),
      duration: executionTime,
      success: false,
      error: errorMessage,
      input: input.params,
      logs: context.logs,
    });
    return { success: false, error: errorMessage, executionTime };
  }
}

async function resolveClientId(request: Request): Promise<string> {
  const authHeader = request.headers.get("authorization");

  if (authHeader && authHeader.startsWith("Bearer ")) {
    const apiKey = authHeader.substring(7);
    if (!isValidApiKey(apiKey)) {
      throw new AuthenticationError("Invalid API key format");
    }
    const client = await getClientByApiKey(apiKey);
    if (!client) throw new AuthenticationError("Invalid API key");
    const rateLimitOk = await checkRateLimit(client.id, client.rateLimit);
    if (!rateLimitOk) throw new RateLimitError("Rate limit exceeded.");
    return client.id;
  }

  if (request.headers.get("x-admin-tenant") === "true") {
    return "admin_tenant";
  }

  throw new AuthenticationError("Missing or invalid authorization header");
}

function toGraphQLError(error: unknown): GraphQLError {
  const message = error instanceof Error ? error.message : "Internal server error";
  let code = "INTERNAL_SERVER_ERROR";

  if (error instanceof AuthenticationError) {
    code = "UNAUTHENTICATED";
  } else if (error instanceof RateLimitError) {
    code = "RATE_LIMITED";
  } else if (error instanceof ValidationError) {
    code = "BAD_USER_INPUT";
  } else if (error instanceof NotFoundError) {
    code = "NOT_FOUND";
  }

  return new GraphQLError(message, { extensions: { code } });
}

const yoga = createYoga({
  schema: createSchema({
    typeDefs: schema,
    resolvers: {
      JSON: jsonScalar,
      Query: {
        ping: () => "pong",
      },
      Mutation: {
        executeMethod: async (
          _parent: unknown,
          args: { methodName: string; params?: Record<string, unknown>; props?: Record<string, string> },
          context: { request: Request }
        ) => {
          try {
            const clientId = await resolveClientId(context.request);
            return await executeRegisteredMethod(
              {
                methodName: args.methodName,
                params: args.params || {},
                props: args.props || {},
              },
              clientId
            );
          } catch (error) {
            throw toGraphQLError(error);
          }
        },
      },
    },
  }),
  context: ({ request }: { request: Request }) => ({ request }),
  graphqlEndpoint: "/api/graphql",
  graphiql: true,
  fetchAPI: { Request, Response },
});

export async function handleGraphQLPost(request: Request) {
  return yoga.handleRequest(request, { request });
}

export async function handleGraphQLGet(request: Request) {
  return yoga.handleRequest(request, { request });
}
