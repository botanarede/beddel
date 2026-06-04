export type { DecodedToken, AppCheckClaims, TenantMembership, AuthContext } from "./types.js";
export { verifyIdToken, verifyAppCheck } from "./verify.js";
export { resolveTenant } from "./tenant.js";
export { withFirebaseAuth } from "./middleware.js";
export type { AuthenticatedHandler } from "./middleware.js";
