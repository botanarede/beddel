/**
 * Next.js route handlers for managing endpoint definitions.
 */

import { saveEndpoint, deleteEndpoint, getEndpoint } from "../kvStore";
import type { Endpoint } from "../types";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { name, description, code, visibility, requiredProps } = body;

    const endpoint: Endpoint = {
      id: `endpoint_${Date.now()}_${Math.random()
        .toString(36)
        .substr(2, 9)}`,
      name,
      description,
      code,
      visibility,
      requiredProps: requiredProps || [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    await saveEndpoint(endpoint);

    return Response.json({ success: true, endpoint });
  } catch (error) {
    console.error("[beddel] Error creating endpoint:", error);
    return Response.json(
      { success: false, error: "Failed to create endpoint" },
      { status: 500 }
    );
  }
}

export async function PUT(request: Request) {
  try {
    const body = await request.json();
    const { id, name, description, code, visibility, requiredProps } = body;

    const existing = await getEndpoint(id);
    if (!existing) {
      return Response.json(
        { success: false, error: "Endpoint not found" },
        { status: 404 }
      );
    }

    const endpoint: Endpoint = {
      ...existing,
      name,
      description,
      code,
      visibility,
      requiredProps: requiredProps || [],
      updatedAt: new Date().toISOString(),
    };

    await saveEndpoint(endpoint);

    return Response.json({ success: true, endpoint });
  } catch (error) {
    console.error("[beddel] Error updating endpoint:", error);
    return Response.json(
      { success: false, error: "Failed to update endpoint" },
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
        { success: false, error: "Missing endpoint ID" },
        { status: 400 }
      );
    }

    await deleteEndpoint(id);

    return Response.json({ success: true });
  } catch (error) {
    console.error("[beddel] Error deleting endpoint:", error);
    return Response.json(
      { success: false, error: "Failed to delete endpoint" },
      { status: 500 }
    );
  }
}
