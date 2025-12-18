"use strict";
/**
 * Upstash KV helpers shared between the Next.js runtime and npm package.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.KV_PREFIXES = void 0;
exports.getClient = getClient;
exports.getClientByApiKey = getClientByApiKey;
exports.getAllClients = getAllClients;
exports.saveClient = saveClient;
exports.deleteClient = deleteClient;
exports.getEndpoint = getEndpoint;
exports.getEndpointByName = getEndpointByName;
exports.getAllEndpoints = getAllEndpoints;
exports.saveEndpoint = saveEndpoint;
exports.deleteEndpoint = deleteEndpoint;
exports.logExecution = logExecution;
exports.checkRateLimit = checkRateLimit;
const redis_1 = require("@upstash/redis");
if (!process.env.KV_REST_API_URL || !process.env.KV_REST_API_TOKEN) {
    throw new Error("Missing Upstash Redis credentials in environment variables");
}
const redis = new redis_1.Redis({
    url: process.env.KV_REST_API_URL,
    token: process.env.KV_REST_API_TOKEN,
});
exports.KV_PREFIXES = {
    CLIENT: "client:",
    API_KEY: "apikey:",
    ENDPOINT: "endpoint:",
    ENDPOINT_NAME: "endpoint:name:",
    EXECUTION_LOG: "log:",
    RATE_LIMIT: "ratelimit:",
    CLIENTS_LIST: "clients:list",
    ENDPOINTS_LIST: "endpoints:list",
};
async function getClient(clientId) {
    return await redis.get(`${exports.KV_PREFIXES.CLIENT}${clientId}`);
}
async function getClientByApiKey(apiKey) {
    const clientId = await redis.get(`${exports.KV_PREFIXES.API_KEY}${apiKey}`);
    if (!clientId)
        return null;
    return await getClient(clientId);
}
async function getAllClients() {
    const clientIds = (await redis.get(exports.KV_PREFIXES.CLIENTS_LIST)) || [];
    if (clientIds.length === 0)
        return [];
    const clients = await Promise.all(clientIds.map((id) => getClient(id)));
    return clients.filter((c) => c !== null);
}
async function saveClient(client) {
    await redis.set(`${exports.KV_PREFIXES.CLIENT}${client.id}`, JSON.stringify(client));
    for (const apiKey of client.apiKeys) {
        await redis.set(`${exports.KV_PREFIXES.API_KEY}${apiKey}`, client.id);
    }
    const clientIds = (await redis.get(exports.KV_PREFIXES.CLIENTS_LIST)) || [];
    if (!clientIds.includes(client.id)) {
        clientIds.push(client.id);
        await redis.set(exports.KV_PREFIXES.CLIENTS_LIST, clientIds);
    }
}
async function deleteClient(clientId) {
    const client = await getClient(clientId);
    if (!client)
        return;
    for (const apiKey of client.apiKeys) {
        await redis.del(`${exports.KV_PREFIXES.API_KEY}${apiKey}`);
    }
    let clientIds = (await redis.get(exports.KV_PREFIXES.CLIENTS_LIST)) || [];
    clientIds = clientIds.filter((id) => id !== clientId);
    await redis.set(exports.KV_PREFIXES.CLIENTS_LIST, clientIds);
    await redis.del(`${exports.KV_PREFIXES.CLIENT}${clientId}`);
}
async function getEndpoint(endpointId) {
    return await redis.get(`${exports.KV_PREFIXES.ENDPOINT}${endpointId}`);
}
async function getEndpointByName(name) {
    const endpointId = await redis.get(`${exports.KV_PREFIXES.ENDPOINT_NAME}${name}`);
    if (!endpointId)
        return null;
    return await getEndpoint(endpointId);
}
async function getAllEndpoints() {
    const endpointIds = (await redis.get(exports.KV_PREFIXES.ENDPOINTS_LIST)) || [];
    if (endpointIds.length === 0)
        return [];
    const endpoints = await Promise.all(endpointIds.map((id) => getEndpoint(id)));
    return endpoints.filter((e) => e !== null);
}
async function saveEndpoint(endpoint) {
    await redis.set(`${exports.KV_PREFIXES.ENDPOINT}${endpoint.id}`, JSON.stringify(endpoint));
    await redis.set(`${exports.KV_PREFIXES.ENDPOINT_NAME}${endpoint.name}`, endpoint.id);
    const endpointIds = (await redis.get(exports.KV_PREFIXES.ENDPOINTS_LIST)) || [];
    if (!endpointIds.includes(endpoint.id)) {
        endpointIds.push(endpoint.id);
        await redis.set(exports.KV_PREFIXES.ENDPOINTS_LIST, endpointIds);
    }
}
async function deleteEndpoint(endpointId) {
    const endpoint = await getEndpoint(endpointId);
    if (!endpoint)
        return;
    await redis.del(`${exports.KV_PREFIXES.ENDPOINT_NAME}${endpoint.name}`);
    let endpointIds = (await redis.get(exports.KV_PREFIXES.ENDPOINTS_LIST)) || [];
    endpointIds = endpointIds.filter((id) => id !== endpointId);
    await redis.set(exports.KV_PREFIXES.ENDPOINTS_LIST, endpointIds);
    await redis.del(`${exports.KV_PREFIXES.ENDPOINT}${endpointId}`);
}
async function logExecution(log) {
    const key = `${exports.KV_PREFIXES.EXECUTION_LOG}${log.id}`;
    await redis.set(key, JSON.stringify(log), {
        ex: 60 * 60 * 24 * 30,
    });
}
async function checkRateLimit(clientId, limit) {
    const key = `${exports.KV_PREFIXES.RATE_LIMIT}${clientId}`;
    const pipeline = redis.pipeline();
    pipeline.incr(key);
    pipeline.ttl(key);
    const [current, ttl] = await pipeline.exec();
    if (ttl === -1) {
        await redis.expire(key, 60);
    }
    return current <= limit;
}
//# sourceMappingURL=kvStore.js.map