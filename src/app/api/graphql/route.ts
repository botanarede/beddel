import { NextRequest, NextResponse } from "next/server";
import { executeChatHandler } from "beddel/agents/chat/chat.handler";
import type { ExecutionContext } from "beddel";
import type { ChatHandlerParams } from "beddel/agents/chat";

/**
 * GraphQL-like API route for Beddel Chat
 * Simplified implementation (Option B) - calls executeChatHandler directly
 */

interface GraphQLRequest {
  query: string;
  variables?: {
    input?: ChatHandlerParams;
  };
}

interface ExecuteMethodResult {
  success: boolean;
  data?: unknown;
  error?: string | null;
  executionTime?: number;
}

// Create execution context for the handler
function createExecutionContext(): ExecutionContext {
  const context: ExecutionContext = {
    logs: [],
    status: "running",
    output: null,
    error: undefined,
    log: (message: string) => {
      context.logs.push(`[${new Date().toISOString()}] ${message}`);
      console.log(message);
    },
    setOutput: (data: unknown) => {
      context.output = data;
      context.status = "success";
    },
    setError: (err: string) => {
      context.error = err;
      context.status = "error";
    },
  };

  return context;
}

// Get props from environment variables
function getPropsFromEnv(): Record<string, string> {
  return {
    gemini_api_key: process.env.GEMINI_API_KEY || "",
    chromadb_tenant: process.env.CHROMADB_TENANT || "",
    chromadb_api_key: process.env.CHROMADB_API_KEY || "",
    chromadb_database: process.env.CHROMADB_DATABASE || "",
  };
}

export async function POST(request: NextRequest) {
  const startTime = Date.now();

  try {
    const body: GraphQLRequest = await request.json();
    const { variables } = body;

    // Extract params from GraphQL variables
    const params = variables?.input;

    if (!params || !params.messages) {
      return NextResponse.json(
        {
          errors: [{ message: "Missing required input.messages parameter" }],
        },
        { status: 400 }
      );
    }

    // Create execution context and props
    const context = createExecutionContext();
    const props = getPropsFromEnv();

    // Execute chat handler
    const result = await executeChatHandler(params, props, context);

    const executionTime = Date.now() - startTime;

    // Return GraphQL-formatted response
    const executeMethodResult: ExecuteMethodResult = {
      success: true,
      data: result,
      error: null,
      executionTime,
    };

    return NextResponse.json({
      data: {
        executeMethod: executeMethodResult,
      },
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("[GraphQL API] Error:", message);

    return NextResponse.json({
      data: {
        executeMethod: {
          success: false,
          data: null,
          error: message,
          executionTime: Date.now() - startTime,
        },
      },
    });
  }
}

// Handle OPTIONS for CORS preflight
export async function OPTIONS() {
  return new NextResponse(null, {
    status: 200,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    },
  });
}
