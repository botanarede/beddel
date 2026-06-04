import * as admin from "firebase-admin";
import type { AppCheckClaims, DecodedToken } from "./types.js";

function ensureApp(projectId?: string): admin.app.App {
  if (admin.apps.length > 0) return admin.app();
  const resolved = projectId ?? process.env["GOOGLE_CLOUD_PROJECT"];
  return admin.initializeApp(resolved ? { projectId: resolved } : undefined);
}

export async function verifyIdToken(
  token: string,
  projectId?: string,
): Promise<DecodedToken> {
  if (!token) throw new Error("ID token must not be empty");
  const app = ensureApp(projectId);
  const claims = await admin.auth(app).verifyIdToken(token);
  return {
    uid: claims.uid,
    email: claims.email,
    emailVerified: claims.email_verified ?? false,
    name: claims.name,
    picture: claims.picture,
    providerId: (claims["firebase"] as { sign_in_provider?: string } | undefined)
      ?.sign_in_provider,
    iss: claims.iss,
    aud: typeof claims.aud === "string" ? claims.aud : claims.aud[0] ?? "",
    exp: claims.exp,
    iat: claims.iat,
  };
}

export async function verifyAppCheck(
  token: string,
  projectId?: string,
): Promise<AppCheckClaims> {
  if (!token) throw new Error("App Check token must not be empty");
  const app = ensureApp(projectId);
  const claims = await (admin as unknown as {
    appCheck(app: admin.app.App): {
      verifyToken(t: string): Promise<Record<string, unknown>>;
    };
  }).appCheck(app).verifyToken(token);
  return {
    sub: String(claims["appId"] ?? claims["sub"] ?? ""),
    appId: String(claims["appId"] ?? ""),
    iss: String(claims["iss"] ?? ""),
    exp: Number(claims["exp"] ?? 0),
  };
}
