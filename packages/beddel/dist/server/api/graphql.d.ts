/**
 * GraphQL helpers used by the /api/graphql route.
 */
import type { ExecuteMethodInput, ExecuteMethodResult } from "../types";
export declare function getGraphQLSchema(): string;
export declare function executeRegisteredMethod(input: ExecuteMethodInput, clientId: string): Promise<ExecuteMethodResult>;
export declare function handleGraphQLPost(request: Request): Promise<Response>;
export declare function handleGraphQLGet(): Response;
//# sourceMappingURL=graphql.d.ts.map