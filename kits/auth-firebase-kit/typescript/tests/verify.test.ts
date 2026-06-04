import { describe, it, expect, vi, beforeEach } from "vitest";

const mockVerifyIdToken = vi.fn();
const mockVerifyToken = vi.fn();

vi.mock("firebase-admin", () => {
  const apps = [{}];
  return {
    apps,
    app: vi.fn(() => ({})),
    initializeApp: vi.fn(() => ({})),
    auth: vi.fn(() => ({ verifyIdToken: mockVerifyIdToken })),
    appCheck: vi.fn(() => ({ verifyToken: mockVerifyToken })),
  };
});

const { verifyIdToken, verifyAppCheck } = await import("../src/verify.js");

describe("verifyIdToken", () => {
  beforeEach(() => vi.clearAllMocks());

  it("throws on empty token", async () => {
    await expect(verifyIdToken("")).rejects.toThrow("must not be empty");
  });

  it("returns DecodedToken on valid JWT", async () => {
    mockVerifyIdToken.mockResolvedValue({
      uid: "user1",
      email: "u@example.com",
      email_verified: true,
      name: "User",
      picture: undefined,
      firebase: { sign_in_provider: "google.com" },
      iss: "iss",
      aud: "proj",
      exp: 9999,
      iat: 1000,
    });
    const result = await verifyIdToken("valid-token");
    expect(result.uid).toBe("user1");
    expect(result.email).toBe("u@example.com");
    expect(result.emailVerified).toBe(true);
    expect(result.providerId).toBe("google.com");
  });

  it("propagates SDK errors", async () => {
    mockVerifyIdToken.mockRejectedValue(new Error("invalid"));
    await expect(verifyIdToken("bad")).rejects.toThrow("invalid");
  });
});

describe("verifyAppCheck", () => {
  beforeEach(() => vi.clearAllMocks());

  it("throws on empty token", async () => {
    await expect(verifyAppCheck("")).rejects.toThrow("must not be empty");
  });

  it("returns AppCheckClaims on valid token", async () => {
    mockVerifyToken.mockResolvedValue({ appId: "app123", iss: "iss", exp: 9999 });
    const result = await verifyAppCheck("valid-ac-token");
    expect(result.appId).toBe("app123");
    expect(result.sub).toBe("app123");
  });
});
