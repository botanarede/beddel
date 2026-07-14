/**
 * Typed behavior contract for declarative component interactions.
 *
 * Defines a Zod-validated discriminated union of all supported behavior types.
 * Tenant JSON configs specify behaviors (navigation, dialogs, toasts) without
 * embedding arbitrary JavaScript — this is a security boundary.
 */

import { z } from 'zod';

// --- Individual behavior schemas ---

const RouteNavigateSchema = z
  .object({
    type: z.literal('route-navigate'),
    route: z.string(),
  })
  .strict();

const HashNavigateSchema = z
  .object({
    type: z.literal('hash-navigate'),
    hash: z.string(),
  })
  .strict();

const ExternalLinkSchema = z
  .object({
    type: z.literal('external-link'),
    href: z.string(),
    target: z.enum(['_blank', '_self']).optional(),
  })
  .strict();

const DialogOpenSchema = z
  .object({
    type: z.literal('dialog-open'),
    dialogId: z.string(),
  })
  .strict();

const DialogCloseSchema = z
  .object({
    type: z.literal('dialog-close'),
    dialogId: z.string(),
  })
  .strict();

const TabSyncSchema = z
  .object({
    type: z.literal('tab-sync'),
    tabGroupId: z.string(),
    tabId: z.string(),
  })
  .strict();

const ToastSchema = z
  .object({
    type: z.literal('toast'),
    message: z.string(),
    variant: z.enum(['info', 'success', 'warning', 'error']).optional(),
  })
  .strict();

const FullscreenMediaSchema = z
  .object({
    type: z.literal('fullscreen-media'),
    mediaRef: z.string(),
  })
  .strict();

// --- Discriminated union ---

export const BehaviorContractSchema = z.discriminatedUnion('type', [
  RouteNavigateSchema,
  HashNavigateSchema,
  ExternalLinkSchema,
  DialogOpenSchema,
  DialogCloseSchema,
  TabSyncSchema,
  ToastSchema,
  FullscreenMediaSchema,
]);

/** Discriminated union of all supported behavior types. */
export type BehaviorContract = z.infer<typeof BehaviorContractSchema>;

/** Callback provided by the runtime host to handle behavior dispatch. */
export type BehaviorDispatcher = (behavior: BehaviorContract) => void;

/**
 * Type guard: returns true if value is a valid BehaviorContract.
 * Uses Zod safeParse for runtime validation.
 */
export function isBehavior(value: unknown): value is BehaviorContract {
  return BehaviorContractSchema.safeParse(value).success;
}

/**
 * Invokes the dispatcher with the given behavior.
 * Intentionally thin — exists to provide a typed call site and
 * allow future middleware without changing the component API.
 */
export function dispatchBehavior(dispatcher: BehaviorDispatcher, behavior: BehaviorContract): void {
  dispatcher(behavior);
}
