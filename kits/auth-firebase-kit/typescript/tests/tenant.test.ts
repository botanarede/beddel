import { describe, it, expect, vi } from "vitest";

vi.mock("firebase-admin", () => ({
  apps: [{}],
  app: vi.fn(() => ({})),
  initializeApp: vi.fn(() => ({})),
  firestore: {
    FieldPath: {
      documentId: vi.fn(() => "__id__"),
    },
  },
}));

const { resolveTenant } = await import("../src/tenant.js");

function makeDb(snapExists: boolean, data: Record<string, unknown> = {}, docs: unknown[] = []) {
  const snap = { exists: snapExists, data: () => data };
  const queryResult = { empty: docs.length === 0, docs };
  return {
    collection: vi.fn(() => ({
      doc: vi.fn(() => ({
        collection: vi.fn(() => ({
          doc: vi.fn(() => ({ get: vi.fn(async () => snap) })),
        })),
      })),
    })),
    collectionGroup: vi.fn(() => ({
      where: vi.fn(() => ({
        limit: vi.fn(() => ({
          get: vi.fn(async () => queryResult),
        })),
      })),
    })),
  };
}

describe("resolveTenant", () => {
  it("throws on empty uid", async () => {
    await expect(resolveTenant("", {} as never)).rejects.toThrow("uid must not be empty");
  });

  it("scoped: returns membership when doc exists", async () => {
    const db = makeDb(true, { role: "editor", email: "e@x.com" });
    const result = await resolveTenant("u1", db as never, "tenant1");
    expect(result.tenantId).toBe("tenant1");
    expect(result.role).toBe("editor");
  });

  it("scoped: throws 403 when doc not found", async () => {
    const db = makeDb(false);
    await expect(resolveTenant("u1", db as never, "tenant1")).rejects.toThrow("not a member");
  });

  it("discovery: returns first membership", async () => {
    const mockDoc = {
      data: () => ({ role: "viewer", email: "v@x.com" }),
      ref: { parent: { parent: { id: "tenantX" } } },
    };
    const db = makeDb(false, {}, [mockDoc]);
    const result = await resolveTenant("u1", db as never);
    expect(result.tenantId).toBe("tenantX");
    expect(result.role).toBe("viewer");
  });

  it("discovery: throws 404 when no membership found", async () => {
    const db = makeDb(false, {}, []);
    await expect(resolveTenant("u1", db as never)).rejects.toThrow("No tenant membership");
  });
});
