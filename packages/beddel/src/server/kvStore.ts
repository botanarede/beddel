/**
 * Upstash KV helpers shared between the Next.js runtime and npm package.
 */

import { Redis } from "@upstash/redis";
import type { Client, Endpoint, ExecutionLog } from "./types";

if (!process.env.KV_REST_API_URL || !process.env.KV_REST_API_TOKEN) {
  throw new Error("Missing Upstash Redis credentials in environment variables");
}

const redis = new Redis({
  url: process.env.KV_REST_API_URL,
  token: process.env.KV_REST_API_TOKEN,
});

export const KV_PREFIXES = {
  CLIENT: "client:",
  API_KEY: "apikey:",
  ENDPOINT: "endpoint:",
  ENDPOINT_NAME: "endpoint:name:",
  EXECUTION_LOG: "log:",
  RATE_LIMIT: "ratelimit:",
  CLIENTS_LIST: "clients:list",
  ENDPOINTS_LIST: "endpoints:list",
} as const;

export async function getClient(clientId: string): Promise<Client | null> {
  return await redis.get<Client>(`${KV_PREFIXES.CLIENT}${clientId}`);
}

export async function getClientByApiKey(apiKey: string): Promise<Client | null> {
  const clientId = await redis.get<string>(`${KV_PREFIXES.API_KEY}${apiKey}`);
  if (!clientId) return null;
  return await getClient(clientId);
}

export async function getAllClients(): Promise<Client[]> {
  const clientIds =
    (await redis.get<string[]>(KV_PREFIXES.CLIENTS_LIST)) || [];
  if (clientIds.length === 0) return [];
  const clients = await Promise.all(clientIds.map((id) => getClient(id)));
  return clients.filter((c): c is Client => c !== null);
}

export async function saveClient(client: Client): Promise<void> {
  await redis.set(`${KV_PREFIXES.CLIENT}${client.id}`, JSON.stringify(client));

  for (const apiKey of client.apiKeys) {
    await redis.set(`${KV_PREFIXES.API_KEY}${apiKey}`, client.id);
  }

  const clientIds =
    (await redis.get<string[]>(KV_PREFIXES.CLIENTS_LIST)) || [];
  if (!clientIds.includes(client.id)) {
    clientIds.push(client.id);
    await redis.set(KV_PREFIXES.CLIENTS_LIST, clientIds);
  }
}

export async function deleteClient(clientId: string): Promise<void> {
  const client = await getClient(clientId);
  if (!client) return;

  for (const apiKey of client.apiKeys) {
    await redis.del(`${KV_PREFIXES.API_KEY}${apiKey}`);
  }

  let clientIds =
    (await redis.get<string[]>(KV_PREFIXES.CLIENTS_LIST)) || [];
  clientIds = clientIds.filter((id) => id !== clientId);
  await redis.set(KV_PREFIXES.CLIENTS_LIST, clientIds);

  await redis.del(`${KV_PREFIXES.CLIENT}${clientId}`);
}

export async function getEndpoint(endpointId: string): Promise<Endpoint | null> {
  return await redis.get<Endpoint>(`${KV_PREFIXES.ENDPOINT}${endpointId}`);
}

export async function getEndpointByName(
  name: string
): Promise<Endpoint | null> {
  const endpointId = await redis.get<string>(
    `${KV_PREFIXES.ENDPOINT_NAME}${name}`
  );
  if (!endpointId) return null;
  return await getEndpoint(endpointId);
}

export async function getAllEndpoints(): Promise<Endpoint[]> {
  const endpointIds =
    (await redis.get<string[]>(KV_PREFIXES.ENDPOINTS_LIST)) || [];
  if (endpointIds.length === 0) return [];
  const endpoints = await Promise.all(endpointIds.map((id) => getEndpoint(id)));
  return endpoints.filter((e): e is Endpoint => e !== null);
}

export async function saveEndpoint(endpoint: Endpoint): Promise<void> {
  await redis.set(
    `${KV_PREFIXES.ENDPOINT}${endpoint.id}`,
    JSON.stringify(endpoint)
  );
  await redis.set(`${KV_PREFIXES.ENDPOINT_NAME}${endpoint.name}`, endpoint.id);

  const endpointIds =
    (await redis.get<string[]>(KV_PREFIXES.ENDPOINTS_LIST)) || [];
  if (!endpointIds.includes(endpoint.id)) {
    endpointIds.push(endpoint.id);
    await redis.set(KV_PREFIXES.ENDPOINTS_LIST, endpointIds);
  }
}

export async function deleteEndpoint(endpointId: string): Promise<void> {
  const endpoint = await getEndpoint(endpointId);
  if (!endpoint) return;

  await redis.del(`${KV_PREFIXES.ENDPOINT_NAME}${endpoint.name}`);

  let endpointIds =
    (await redis.get<string[]>(KV_PREFIXES.ENDPOINTS_LIST)) || [];
  endpointIds = endpointIds.filter((id) => id !== endpointId);
  await redis.set(KV_PREFIXES.ENDPOINTS_LIST, endpointIds);

  await redis.del(`${KV_PREFIXES.ENDPOINT}${endpointId}`);
}

export async function logExecution(log: ExecutionLog): Promise<void> {
  const key = `${KV_PREFIXES.EXECUTION_LOG}${log.id}`;
  await redis.set(key, JSON.stringify(log), {
    ex: 60 * 60 * 24 * 30,
  });
}

export async function checkRateLimit(
  clientId: string,
  limit: number
): Promise<boolean> {
  const key = `${KV_PREFIXES.RATE_LIMIT}${clientId}`;

  const pipeline = redis.pipeline();
  pipeline.incr(key);
  pipeline.ttl(key);

  const [current, ttl] = await pipeline.exec<[number, number]>();

  if (ttl === -1) {
    await redis.expire(key, 60);
  }

  return current <= limit;
}
