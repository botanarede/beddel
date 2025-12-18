"use strict";
/**
 * GraphQL helpers used by the /api/graphql route.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.getGraphQLSchema = getGraphQLSchema;
exports.executeRegisteredMethod = executeRegisteredMethod;
exports.handleGraphQLPost = handleGraphQLPost;
exports.handleGraphQLGet = handleGraphQLGet;
const agentRegistry_1 = require("../../agents/agentRegistry");
const kvStore_1 = require("../kvStore");
const runtimeSecurity_1 = require("../runtimeSecurity");
const errors_1 = require("../errors");
const schema = `
  type Query { ping: String! }
  type Mutation { executeMethod(methodName: String!, params: JSON!, props: JSON!): ExecutionResult! }
  type ExecutionResult { success: Boolean!, data: JSON, error: String, executionTime: Int! }
  scalar JSON
`;
function getGraphQLSchema() {
    return schema;
}
async function executeRegisteredMethod(input, clientId) {
    const startTime = Date.now();
    const context = {
        logs: [],
        status: "running",
        output: undefined,
        error: undefined,
        log: (message) => context.logs.push(`[${new Date().toISOString()}] ${message}`),
        setOutput: (output) => {
            context.output = output;
            context.status = "success";
        },
        setError: (error) => {
            context.error = error;
            context.status = "error";
        },
    };
    try {
        context.log("Method execution initiated.");
        if (!(0, runtimeSecurity_1.isValidMethodName)(input.methodName)) {
            throw new errors_1.ValidationError("Invalid method name format");
        }
        const declarativeAgent = agentRegistry_1.agentRegistry.getAgent(input.methodName);
        if (declarativeAgent) {
            context.log(`Found declarative agent: ${input.methodName}`);
            const result = await agentRegistry_1.agentRegistry.executeAgent(input.methodName, (0, runtimeSecurity_1.sanitizeInput)(input.params), (0, runtimeSecurity_1.sanitizeInput)(input.props), context);
            const executionTime = Date.now() - startTime;
            await (0, kvStore_1.logExecution)({
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
        const endpoint = await (0, kvStore_1.getEndpointByName)(input.methodName);
        if (!endpoint) {
            throw new errors_1.NotFoundError(`Method '${input.methodName}' not found`);
        }
        context.log(`Found endpoint: ${endpoint.name}`);
        const sanitizedParams = (0, runtimeSecurity_1.sanitizeInput)(input.params);
        const sanitizedProps = (0, runtimeSecurity_1.sanitizeInput)(input.props);
        const { valid, missing } = (0, runtimeSecurity_1.validateRequiredProps)(endpoint.requiredProps, sanitizedProps);
        if (!valid) {
            throw new errors_1.ValidationError(`Missing required props: ${missing.join(", ")}`);
        }
        context.log("Props validated. Executing sandbox.");
        await (0, runtimeSecurity_1.executeInSandbox)(endpoint.code, sanitizedParams, sanitizedProps, context);
        context.log("Sandbox execution finished.");
        if (context.status === "error") {
            throw new Error(context.error || "Sandbox execution failed.");
        }
        if (context.status !== "success") {
            throw new Error("Sandbox finished in an indeterminate state.");
        }
        const executionTime = Date.now() - startTime;
        await (0, kvStore_1.logExecution)({
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
    }
    catch (error) {
        const executionTime = Date.now() - startTime;
        const errorMessage = error instanceof Error ? error.message : "Unknown error";
        if (!context.error)
            context.setError(errorMessage);
        await (0, kvStore_1.logExecution)({
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
async function handleGraphQLPost(request) {
    try {
        let clientId;
        const authHeader = request.headers.get("authorization");
        if (authHeader && authHeader.startsWith("Bearer ")) {
            const apiKey = authHeader.substring(7);
            if (!(0, runtimeSecurity_1.isValidApiKey)(apiKey)) {
                throw new errors_1.AuthenticationError("Invalid API key format");
            }
            const client = await (0, kvStore_1.getClientByApiKey)(apiKey);
            if (!client)
                throw new errors_1.AuthenticationError("Invalid API key");
            const rateLimitOk = await (0, kvStore_1.checkRateLimit)(client.id, client.rateLimit);
            if (!rateLimitOk)
                throw new errors_1.RateLimitError("Rate limit exceeded.");
            clientId = client.id;
        }
        else if (request.headers.get("x-admin-tenant") === "true") {
            clientId = "admin_tenant";
        }
        else {
            throw new errors_1.AuthenticationError("Missing or invalid authorization header");
        }
        const body = await request.json();
        if (!body.query) {
            throw new errors_1.ValidationError("Missing query in request body");
        }
        if (body.query && body.query.includes("executeMethod")) {
            if (!body.variables || !body.variables.methodName) {
                throw new errors_1.ValidationError("Missing 'variables' or 'methodName' in request body");
            }
            const result = await executeRegisteredMethod({
                methodName: body.variables.methodName,
                params: body.variables.params || {},
                props: body.variables.props || {},
            }, clientId);
            return Response.json({ data: { executeMethod: result } });
        }
        return Response.json({ errors: [{ message: "Unsupported operation" }] }, { status: 400 });
    }
    catch (error) {
        const status = error instanceof errors_1.AuthenticationError
            ? 401
            : error instanceof errors_1.RateLimitError
                ? 429
                : error instanceof errors_1.ValidationError
                    ? 400
                    : error instanceof errors_1.NotFoundError
                        ? 404
                        : 500;
        return Response.json({
            errors: [
                {
                    message: error instanceof Error ? error.message : "Internal server error",
                },
            ],
        }, { status });
    }
}
function handleGraphQLGet() {
    return new Response(`<!DOCTYPE html>
    <html><head><title>Opal Support API - GraphQL</title><style>body{font-family:sans-serif;max-width:800px;margin:50px auto;padding:20px}code,pre{background:#f4f4f4;padding:4px 8px;border-radius:4px}</style></head>
    <body><h1>Opal Support API</h1><p>GraphQL endpoint for executing registered methods.</p><h2>Endpoint</h2><code>POST /api/graphql</code><h2>Authentication</h2><p>Use Bearer token in Authorization header.</p><h2>Schema</h2><pre>${schema}</pre></body></html>`, { headers: { "Content-Type": "text/html" } });
}
//# sourceMappingURL=graphql.js.map