'use client';

/**
 * Client-only exports from @botanarede/core.
 *
 * These require React context/hooks and must only be imported
 * in client components (files with 'use client' directive).
 */

export type { ToastItem } from './behaviors/dispatcher';
export {
  BehaviorDispatcherProvider,
  useBehaviorDispatch,
  useTabState,
  useDialogState,
  useToasts,
} from './behaviors/dispatcher';

export { UnknownComponentFallback, ComponentErrorFallback, ComponentErrorBoundary } from './errors';

export { useFormBinding } from './forms/use-form-binding';
