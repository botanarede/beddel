import { getApps, initializeApp } from "firebase-admin/app.js";
import { getAuth } from "firebase-admin/auth.js";
import { getAppCheck } from "firebase-admin/app-check.js";
import type { AppCheckClaims, DecodedToken } from "./types.js";

function ensureApp(projectId?: string) {
  if (getApps().length > 0) return getApps()[0]!;
  const resolved = projectId ?? process.env["GOOGLE_CLOUD_PROJECT"];
  return initializeApp(resolved ? { projectId: resolved } : undefined);
}

export async function verifyIdToken(
  token: string,
  projectId?: string,
): Promise<DecodedToken> {
  if (!token) throw new Error("ID token must not be empty");
  const app = ensureApp(projectId);
  const claims = await getAuth(app).verifyIdToken(token);
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
  const claims = await getAppCheck(app).verifyToken(token);
  return {
    sub: claims.appId,
    appId: claims.appId,
    iss: (claims as unknown as { iss?: string }).iss ?? "",
    exp: (claims as unknown as { exp?: number }).exp ?? 0,
  };
}
