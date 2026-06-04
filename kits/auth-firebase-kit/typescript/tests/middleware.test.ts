import { describe, it, expect, vi, beforeEach } from "vitest";

const mockVerifyIdToken = vi.fn();
const mockVerifyToken = vi.fn();

vi.mock("firebase-admin", () => ({
  apps: [{}],
  app: vi.fn(() => ({})),
  initializeApp: vi.fn(() => ({})),
  auth: vi.fn(() => ({ verifyIdToken: mockVerifyIdToken })),
  appCheck: vi.fn(() => ({ verifyToken: mockVerifyToken })),
  firestore: {
    FieldPath: { documentId: vi.fn(() => "__id__") },
  },
}));

const { withFirebaseAuth } = await import("../src/middleware.js");

const validClaims = {
  uid: "u1",
  email: "u@x.com",
  email_verified: true,
  firebase: { sign_in_provider: "password" },
  iss: "i",
  aud: "p",
  exp: 9999,
  iat: 1,
};

function makeDb(tenantId = "t1") {
  return {
    collection: vi.fn(() => ({
      doc: vi.fn(() => ({
        collection: vi.fn(() => ({
          doc: vi.fn(() => ({
            get: vi.fn(async () => ({
              exists: true,
              data: () => ({ role: "owner", email: "u@x.com" }),
            })),
          })),
        })),
      })),
    })),
    collectionGroup: vi.fn(() => ({
      where: vi.fn(() => ({
        limit: vi.fn(() => ({
          get: vi.fn(async () => ({
            empty: false,
            docs: [{
              data: () => ({ role: "owner", email: "u@x.com" }),
              ref: { parent: { parent: { id: tenantId } } },
            }],
          })),
        })),
      })),
    })),
  };
}

describe("withFirebaseAuth", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns 401 when Authorization header is missing", async () => {
    const handler = withFirebaseAuth(vi.fn(), makeDb() as never);
    const res = await handler(new Request("http://x/"));
    expect(res.status).toBe(401);
  });

  it("returns 401 on invalid token", async () => {
    mockVerifyIdToken.mockRejectedValue(new Error("bad token"));
    const handler = withFirebaseAuth(vi.fn(), makeDb() as never);
    const res = await handler(new Request("http://x/", { headers: { Authorization: "Bearer bad" } }));
    expect(res.status).toBe(401);
  });

  it("returns 401 on invalid App Check token", async () => {
    mockVerifyIdToken.mockResolvedValue(validClaims);
    mockVerifyToken.mockRejectedValue(new Error("bad ac"));
    const handler = withFirebaseAuth(vi.fn(), makeDb() as never);
    const res = await handler(new Request("http://x/", {
      headers: { Authorization: "Bearer t", "X-Firebase-AppCheck": "bad-ac" },
    }));
    expect(res.status).toBe(401);
  });

  it("calls handler with AuthContext on success", async () => {
    mockVerifyIdToken.mockResolvedValue(validClaims);
    const innerHandler = vi.fn(async () => new Response("ok", { status: 200 }));
    const handler = withFirebaseAuth(innerHandler, makeDb() as never);
    const res = await handler(new Request("http://x/", {
      headers: { Authorization: "Bearer valid", "X-Tenant-Id": "t1" },
    }));
    expect(res.status).toBe(200);
    expect(innerHandler).toHaveBeenCalledOnce();
    const ctx = innerHandler.mock.calls[0]![1];
    expect(ctx.uid).toBe("u1");
    expect(ctx.tenantId).toBe("t1");
    expect(ctx.appCheckVerified).toBe(false);
  });

  it("sets appCheckVerified=true when App Check passes", async () => {
    mockVerifyIdToken.mockResolvedValue(validClaims);
    mockVerifyToken.mockResolvedValue({ appId: "app1", iss: "i", exp: 9999 });
    const innerHandler = vi.fn(async () => new Response("ok"));
    const handler = withFirebaseAuth(innerHandler, makeDb() as never);
    await handler(new Request("http://x/", {
      headers: { Authorization: "Bearer v", "X-Firebase-AppCheck": "ac-token", "X-Tenant-Id": "t1" },
    }));
    expect(innerHandler.mock.calls[0]![1].appCheckVerified).toBe(true);
  });
});
