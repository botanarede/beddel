/**
 * Next.js route handlers for managing clients via Upstash KV.
 * Exported from the Beddel package so the application code stays thin.
 */

import { saveClient, deleteClient, getClient } from "../kvStore";
import type { Client } from "../types";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { name, email, rateLimit, apiKeys } = body;

    const client: Client = {
      id: `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name,
      email,
      rateLimit: rateLimit || 60,
      apiKeys: apiKeys || [],
      createdAt: new Date().toISOString(),
    };

    await saveClient(client);

    return Response.json({ success: true, client });
  } catch (error) {
    console.error("[beddel] Error creating client:", error);
    return Response.json(
      { success: false, error: "Failed to create client" },
      { status: 500 }
    );
  }
}

export async function PUT(request: Request) {
  try {
    const body = await request.json();
    const { id, name, email, rateLimit, apiKeys } = body;

    const existing = await getClient(id);
    if (!existing) {
      return Response.json(
        { success: false, error: "Client not found" },
        { status: 404 }
      );
    }

    const client: Client = {
      ...existing,
      name,
      email,
      rateLimit: rateLimit || 60,
      apiKeys: apiKeys || [],
    };

    await saveClient(client);

    return Response.json({ success: true, client });
  } catch (error) {
    console.error("[beddel] Error updating client:", error);
    return Response.json(
      { success: false, error: "Failed to update client" },
      { status: 500 }
    );
  }
}

export async function DELETE(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get("id");

    if (!id) {
      return Response.json(
        { success: false, error: "Missing client ID" },
        { status: 400 }
      );
    }

    await deleteClient(id);

    return Response.json({ success: true });
  } catch (error) {
    console.error("[beddel] Error deleting client:", error);
    return Response.json(
      { success: false, error: "Failed to delete client" },
      { status: 500 }
    );
  }
}
