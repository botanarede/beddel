/**
 * Upstash KV helpers shared between the Next.js runtime and npm package.
 */
import type { Client, Endpoint, ExecutionLog } from "./types";
export declare const KV_PREFIXES: {
    readonly CLIENT: "client:";
    readonly API_KEY: "apikey:";
    readonly ENDPOINT: "endpoint:";
    readonly ENDPOINT_NAME: "endpoint:name:";
    readonly EXECUTION_LOG: "log:";
    readonly RATE_LIMIT: "ratelimit:";
    readonly CLIENTS_LIST: "clients:list";
    readonly ENDPOINTS_LIST: "endpoints:list";
};
export declare function getClient(clientId: string): Promise<Client | null>;
export declare function getClientByApiKey(apiKey: string): Promise<Client | null>;
export declare function getAllClients(): Promise<Client[]>;
export declare function saveClient(client: Client): Promise<void>;
export declare function deleteClient(clientId: string): Promise<void>;
export declare function getEndpoint(endpointId: string): Promise<Endpoint | null>;
export declare function getEndpointByName(name: string): Promise<Endpoint | null>;
export declare function getAllEndpoints(): Promise<Endpoint[]>;
export declare function saveEndpoint(endpoint: Endpoint): Promise<void>;
export declare function deleteEndpoint(endpointId: string): Promise<void>;
export declare function logExecution(log: ExecutionLog): Promise<void>;
export declare function checkRateLimit(clientId: string, limit: number): Promise<boolean>;
//# sourceMappingURL=kvStore.d.ts.map