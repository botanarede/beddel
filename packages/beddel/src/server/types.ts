/**
 * Shared server-side types for the Opal Support App runtime.
 * These live inside the Beddel package so both the Next.js app and
 * the npm distribution reference exactly the same contracts.
 */

import type { ExecutionContext as DeclarativeExecutionContext } from "../types/executionContext";

export interface Client {
  id: string;
  name: string;
  email: string;
  apiKeys: string[];
  createdAt: string;
  rateLimit: number;
}

export interface Endpoint {
  id: string;
  name: string;
  description: string;
  code: string;
  visibility: "public" | "private";
  requiredProps: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ExecutionLog {
  id: string;
  clientId: string;
  endpointName: string;
  timestamp: string;
  duration: number;
  success: boolean;
  error?: string;
  input?: unknown;
  output?: unknown;
  logs?: string[];
}

export type ExecutionContext = DeclarativeExecutionContext;

export interface ExecuteMethodInput {
  methodName: string;
  params: Record<string, unknown>;
  props: Record<string, string>;
}

export interface ExecuteMethodResult {
  success: boolean;
  data?: unknown;
  error?: string;
  executionTime: number;
}

export interface GraphQLContext {
  clientId: string;
  client: Client;
}
