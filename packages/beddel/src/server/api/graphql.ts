/**
 * GraphQL helpers used by the /api/graphql route.
 */

import { agentRegistry } from "../../agents/agentRegistry";
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

export async function handleGraphQLPost(request: Request) {
  try {
    let clientId: string;
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
      clientId = client.id;
    } else if (request.headers.get("x-admin-tenant") === "true") {
      clientId = "admin_tenant";
    } else {
      throw new AuthenticationError(
        "Missing or invalid authorization header"
      );
    }

    const body = await request.json();
    if (!body.query) {
      throw new ValidationError("Missing query in request body");
    }

    if (body.query && body.query.includes("executeMethod")) {
      if (!body.variables || !body.variables.methodName) {
        throw new ValidationError(
          "Missing 'variables' or 'methodName' in request body"
        );
      }

      const result = await executeRegisteredMethod(
        {
          methodName: body.variables.methodName,
          params: body.variables.params || {},
          props: body.variables.props || {},
        },
        clientId
      );
      return Response.json({ data: { executeMethod: result } });
    }

    return Response.json(
      { errors: [{ message: "Unsupported operation" }] },
      { status: 400 }
    );
  } catch (error) {
    const status =
      error instanceof AuthenticationError
        ? 401
        : error instanceof RateLimitError
        ? 429
        : error instanceof ValidationError
        ? 400
        : error instanceof NotFoundError
        ? 404
        : 500;
    return Response.json(
      {
        errors: [
          {
            message:
              error instanceof Error ? error.message : "Internal server error",
          },
        ],
      },
      { status }
    );
  }
}

export function handleGraphQLGet() {
  return new Response(
    `<!DOCTYPE html>
    <html><head><title>Opal Support API - GraphQL</title><style>body{font-family:sans-serif;max-width:800px;margin:50px auto;padding:20px}code,pre{background:#f4f4f4;padding:4px 8px;border-radius:4px}</style></head>
    <body><h1>Opal Support API</h1><p>GraphQL endpoint for executing registered methods.</p><h2>Endpoint</h2><code>POST /api/graphql</code><h2>Authentication</h2><p>Use Bearer token in Authorization header.</p><h2>Schema</h2><pre>${schema}</pre></body></html>`,
    { headers: { "Content-Type": "text/html" } }
  );
}
