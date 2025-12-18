"use strict";
/**
 * Next.js route handlers for managing clients via Upstash KV.
 * Exported from the Beddel package so the application code stays thin.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.dynamic = void 0;
exports.POST = POST;
exports.PUT = PUT;
exports.DELETE = DELETE;
const kvStore_1 = require("../kvStore");
exports.dynamic = "force-dynamic";
async function POST(request) {
    try {
        const body = await request.json();
        const { name, email, rateLimit, apiKeys } = body;
        const client = {
            id: `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            name,
            email,
            rateLimit: rateLimit || 60,
            apiKeys: apiKeys || [],
            createdAt: new Date().toISOString(),
        };
        await (0, kvStore_1.saveClient)(client);
        return Response.json({ success: true, client });
    }
    catch (error) {
        console.error("[beddel] Error creating client:", error);
        return Response.json({ success: false, error: "Failed to create client" }, { status: 500 });
    }
}
async function PUT(request) {
    try {
        const body = await request.json();
        const { id, name, email, rateLimit, apiKeys } = body;
        const existing = await (0, kvStore_1.getClient)(id);
        if (!existing) {
            return Response.json({ success: false, error: "Client not found" }, { status: 404 });
        }
        const client = {
            ...existing,
            name,
            email,
            rateLimit: rateLimit || 60,
            apiKeys: apiKeys || [],
        };
        await (0, kvStore_1.saveClient)(client);
        return Response.json({ success: true, client });
    }
    catch (error) {
        console.error("[beddel] Error updating client:", error);
        return Response.json({ success: false, error: "Failed to update client" }, { status: 500 });
    }
}
async function DELETE(request) {
    try {
        const { searchParams } = new URL(request.url);
        const id = searchParams.get("id");
        if (!id) {
            return Response.json({ success: false, error: "Missing client ID" }, { status: 400 });
        }
        await (0, kvStore_1.deleteClient)(id);
        return Response.json({ success: true });
    }
    catch (error) {
        console.error("[beddel] Error deleting client:", error);
        return Response.json({ success: false, error: "Failed to delete client" }, { status: 500 });
    }
}
//# sourceMappingURL=clientsRoute.js.map