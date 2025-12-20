import type { 
  ConversationMessage, 
  ChatHandlerResult,
  ExecutionStep 
} from "beddel";

// Re-export types for convenience
export type { ConversationMessage as Message, ChatHandlerResult, ExecutionStep };

export interface ApiResponse {
  success: boolean;
  data?: ChatHandlerResult;
  error?: string;
  executionTime?: number;
}

const GRAPHQL_QUERY = `
mutation ExecuteChat($input: JSON!) {
  executeMethod(
    methodName: "chat.execute",
    params: $input,
    props: {}
  ) {
    success
    data
    error
    executionTime
  }
}
`;

export async function sendChatMessage(messages: ConversationMessage[]): Promise<ApiResponse> {
  try {
    const response = await fetch("/api/graphql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: GRAPHQL_QUERY,
        variables: { input: { messages } },
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      return {
        success: false,
        error: errorData.error || `HTTP error! status: ${response.status}`,
      };
    }

    const json = await response.json();

    if (json.errors) {
      return {
        success: false,
        error: json.errors[0]?.message || "GraphQL Error",
      };
    }

    const result = json.data?.executeMethod;
    if (!result) {
      return { success: false, error: "Invalid GraphQL response structure" };
    }

    return {
      success: result.success,
      data: result.data as ChatHandlerResult,
      error: result.error,
      executionTime: result.executionTime,
    };
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to send message";
    return { success: false, error: message };
  }
}
