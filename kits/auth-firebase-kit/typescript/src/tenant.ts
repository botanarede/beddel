import { Firestore, FieldPath } from "firebase-admin/firestore.js";
import type { TenantMembership } from "./types.js";

export async function resolveTenant(
  uid: string,
  db: Firestore,
  tenantId?: string,
): Promise<TenantMembership> {
  if (!uid) throw new Error("uid must not be empty");

  if (tenantId !== undefined) {
    const snap = await db
      .collection("tenants")
      .doc(tenantId)
      .collection("members")
      .doc(uid)
      .get();
    if (!snap.exists) {
      throw Object.assign(
        new Error(`User ${uid} is not a member of tenant ${tenantId}`),
        { code: 403 },
      );
    }
    const data = snap.data() ?? {};
    return {
      tenantId,
      uid,
      role: data["role"] as TenantMembership["role"],
      email: String(data["email"] ?? ""),
    };
  }

  // Discovery mode: collection group query
  const query = db
    .collectionGroup("members")
    .where(FieldPath.documentId(), "==", uid)
    .limit(1);
  const result = await query.get();
  if (result.empty) {
    throw Object.assign(new Error(`No tenant membership found for user ${uid}`), {
      code: 404,
    });
  }
  const doc = result.docs[0]!;
  const resolvedTenantId = doc.ref.parent.parent?.id ?? "";
  const data = doc.data();
  return {
    tenantId: resolvedTenantId,
    uid,
    role: data["role"] as TenantMembership["role"],
    email: String(data["email"] ?? ""),
  };
}
