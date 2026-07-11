import { z } from 'zod';

// --- Nav item type schemas (discriminated by 'type') ---

export const RouteNavItemSchema = z.object({
  label: z.string(),
  type: z.literal('route'),
  route: z.string(),
}).strict();
export type RouteNavItem = z.infer<typeof RouteNavItemSchema>;

export const ExternalNavItemSchema = z.object({
  label: z.string(),
  type: z.literal('external'),
  href: z.string(),
}).strict();
export type ExternalNavItem = z.infer<typeof ExternalNavItemSchema>;

export const HashNavItemSchema = z.object({
  label: z.string(),
  type: z.literal('hash'),
  hash: z.string(),
}).strict();
export type HashNavItem = z.infer<typeof HashNavItemSchema>;

// Children of a group cannot contain groups (flat PoC constraint)
const ChildNavItemSchema = z.discriminatedUnion('type', [
  RouteNavItemSchema,
  ExternalNavItemSchema,
  HashNavItemSchema,
]);

export const GroupNavItemSchema = z.object({
  label: z.string(),
  type: z.literal('group'),
  children: z.array(ChildNavItemSchema),
}).strict();
export type GroupNavItem = z.infer<typeof GroupNavItemSchema>;

// --- Composite nav item schema ---

export const NavItemSchema = z.discriminatedUnion('type', [
  RouteNavItemSchema,
  ExternalNavItemSchema,
  HashNavItemSchema,
  GroupNavItemSchema,
]);
export type NavItem = z.infer<typeof NavItemSchema>;

// --- Menu and navigation config ---

export const MenuDefinitionSchema = z.object({
  items: z.array(NavItemSchema),
}).strict();
export type MenuDefinition = z.infer<typeof MenuDefinitionSchema>;

export const NavigationConfigSchema = z
  .object({
    menus: z.record(z.string(), MenuDefinitionSchema),
  })
  .strict();
export type NavigationConfig = z.infer<typeof NavigationConfigSchema>;

// --- Semantic validation: dangling route references ---

export interface RouteRefError {
  itemLabel: string;
  route: string;
  message: string;
}

export function validateRouteRefs(
  nav: NavigationConfig,
  pageRoutes: string[],
): RouteRefError[] {
  const errors: RouteRefError[] = [];
  const routeSet = new Set(pageRoutes);

  for (const menu of Object.values(nav.menus)) {
    if (!menu) continue; // noUncheckedIndexedAccess guard
    for (const item of menu.items) {
      if (item.type === 'route' && !routeSet.has(item.route)) {
        errors.push({
          itemLabel: item.label,
          route: item.route,
          message: `Dangling route reference: "${item.route}" is not a known page route`,
        });
      }
      if (item.type === 'group') {
        for (const child of item.children) {
          if (child.type === 'route' && !routeSet.has(child.route)) {
            errors.push({
              itemLabel: child.label,
              route: child.route,
              message: `Dangling route reference: "${child.route}" is not a known page route`,
            });
          }
        }
      }
    }
  }

  return errors;
}
