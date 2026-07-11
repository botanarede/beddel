import type {
  TenantConfig,
  PageDefinition,
  LayoutDefinition,
  ComponentDefinition,
} from '@botanarede/schema';

/**
 * Result of resolving a route to a page definition.
 */
export type ResolvedPage = { page: PageDefinition; pageId: string };

/**
 * Maps slot names to their ordered component lists.
 * Sections targeting unknown or missing slots land in "_unassigned".
 */
export type SlotMap = Record<string, ComponentDefinition[]>;

/**
 * Full resolution result: page + layout + slot assignments.
 */
export type ResolvedPageTree = {
  page: PageDefinition;
  layout: LayoutDefinition | null;
  slots: SlotMap;
};

/**
 * Finds the page whose route exactly matches the given string.
 * Returns the page definition and its key, or null if not found.
 */
export function resolvePage(config: TenantConfig, route: string): ResolvedPage | null {
  for (const [pageId, page] of Object.entries(config.pages)) {
    if (page.route === route) {
      return { page, pageId };
    }
  }
  return null;
}

/**
 * Looks up the layout referenced by a page's layoutRef.
 * Returns null if the layout does not exist in the config.
 */
export function resolveLayout(config: TenantConfig, page: PageDefinition): LayoutDefinition | null {
  return config.layouts[page.layoutRef] ?? null;
}

/**
 * Groups a page's sections into their target layout slots.
 *
 * Each section is converted to a ComponentDefinition ({ type, props }).
 * Sections whose slot is undefined, empty, or not present in the layout
 * are placed in the "_unassigned" bucket.
 */
export function resolveSlots(layout: LayoutDefinition, page: PageDefinition): SlotMap {
  const validSlotNames = new Set(layout.slots.map((s) => s.name));
  const slots: SlotMap = {};

  for (const section of page.sections) {
    const targetSlot =
      section.slot != null && validSlotNames.has(section.slot) ? section.slot : '_unassigned';

    const existing = slots[targetSlot];
    if (existing) {
      existing.push({ type: section.type, props: section.props });
    } else {
      slots[targetSlot] = [{ type: section.type, props: section.props }];
    }
  }

  return slots;
}

/**
 * Resolves a route to a full page tree: page, layout, and slot map.
 * Returns null if no page matches the route.
 * When the layout is missing, all sections go to "_unassigned".
 */
export function resolvePageTree(config: TenantConfig, route: string): ResolvedPageTree | null {
  const resolved = resolvePage(config, route);
  if (!resolved) return null;

  const layout = resolveLayout(config, resolved.page);

  const slots = layout
    ? resolveSlots(layout, resolved.page)
    : resolveSlots({ id: '', slots: [] }, resolved.page);

  return { page: resolved.page, layout, slots };
}
