/** Tenant role types and hierarchy helpers. */

export type TenantRole = 'owner' | 'admin' | 'editor';

export const ROLE_HIERARCHY: Record<TenantRole, number> = {
  owner: 3,
  admin: 2,
  editor: 1,
};

export function hasMinimumRole(userRoles: string[], minimumRole: TenantRole): boolean {
  const minLevel = ROLE_HIERARCHY[minimumRole];
  return userRoles.some((r) => (ROLE_HIERARCHY[r as TenantRole] ?? 0) >= minLevel);
}
