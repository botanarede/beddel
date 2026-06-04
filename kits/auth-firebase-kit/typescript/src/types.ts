/** Decoded claims from a verified Firebase Auth ID token. */
export interface DecodedToken {
  uid: string;
  email?: string;
  emailVerified: boolean;
  name?: string;
  picture?: string;
  providerId?: string;
  iss: string;
  aud: string;
  exp: number;
  iat: number;
}

/** Decoded claims from a verified Firebase App Check attestation token. */
export interface AppCheckClaims {
  sub: string;
  appId: string;
  iss: string;
  exp: number;
}

/** A user's membership record within a tenant. */
export interface TenantMembership {
  tenantId: string;
  uid: string;
  role: "owner" | "editor" | "viewer";
  email: string;
}

/** Fully resolved authentication context for a request. */
export interface AuthContext {
  uid: string;
  email?: string;
  tenantId: string;
  role: string;
  appCheckVerified: boolean;
}
