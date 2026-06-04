import * as admin from "firebase-admin";
import type { AuthContext } from "./types.js";
import { verifyIdToken, verifyAppCheck } from "./verify.js";
import { resolveTenant } from "./tenant.js";

type Firestore = admin.firestore.Firestore;

export type AuthenticatedHandler = (
  req: Request,
  ctx: AuthContext,
) => Promise<Response>;

function json401(detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status: 401,
    headers: { "Content-Type": "application/json", "WWW-Authenticate": "Bearer" },
  });
}

function json403(detail: string): Response {
  return new Response(JSON.stringify({ detail }), {
    status: 403,
    headers: { "Content-Type": "application/json" },
  });
}

export function withFirebaseAuth(
  handler: AuthenticatedHandler,
  db: Firestore,
): (req: Request) => Promise<Response> {
  return async (req: Request): Promise<Response> => {
    const authHeader = req.headers.get("Authorization") ?? "";
    if (!authHeader.startsWith("Bearer ")) {
      return json401("Missing or malformed Authorization header");
    }
    const idToken = authHeader.slice(7).trim();
    if (!idToken) return json401("Empty bearer token");

    let decoded;
    try {
      decoded = await verifyIdToken(idToken);
    } catch {
      return json401("Invalid Firebase ID token");
    }

    let appCheckVerified = false;
    const appCheckToken = req.headers.get("X-Firebase-AppCheck");
    if (appCheckToken) {
      try {
        await verifyAppCheck(appCheckToken);
        appCheckVerified = true;
      } catch {
        return json401("Invalid Firebase App Check token");
      }
    }

    const tenantId = req.headers.get("X-Tenant-Id") ?? undefined;
    let membership;
    try {
      membership = await resolveTenant(decoded.uid, db, tenantId);
    } catch (err) {
      return json403(err instanceof Error ? err.message : "No tenant access");
    }

    const ctx: AuthContext = {
      uid: decoded.uid,
      email: decoded.email,
      tenantId: membership.tenantId,
      role: membership.role,
      appCheckVerified,
    };
    return handler(req, ctx);
  };
}
