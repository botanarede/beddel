'use client';

/**
 * Behavior dispatch system — React context provider + hooks.
 *
 * Components call useBehaviorDispatch() to trigger declarative behaviors.
 * The provider manages tab-sync, dialog, and toast state internally.
 * DOM-dependent behaviors (navigation, fullscreen) are handled via callbacks.
 *
 * Framework-agnostic: route-navigate uses onRouteNavigate prop, not useRouter.
 */

import React, { createContext, useCallback, useContext, useRef, useState } from 'react';
import type { BehaviorContract } from '../behaviors';

export interface ToastItem {
  id: string;
  message: string;
  variant?: 'info' | 'success' | 'warning' | 'error';
}

interface BehaviorState {
  tabs: Record<string, string>;
  dialogs: Record<string, boolean>;
  toasts: ToastItem[];
}

interface BehaviorContextValue {
  dispatch: (behavior: BehaviorContract) => void;
  state: BehaviorState;
}

const BehaviorContext = createContext<BehaviorContextValue | null>(null);

interface BehaviorDispatcherProviderProps {
  children: React.ReactNode;
  /** Called for route-navigate behaviors. In the host app, pass router.push. */
  onRouteNavigate?: (route: string) => void;
}

let toastCounter = 0;
function generateToastId(): string {
  toastCounter += 1;
  return `toast-${toastCounter}-${Date.now()}`;
}

const TOAST_DURATION = 4000;

export function BehaviorDispatcherProvider({
  children,
  onRouteNavigate,
}: BehaviorDispatcherProviderProps) {
  const [tabs, setTabs] = useState<Record<string, string>>({});
  const [dialogs, setDialogs] = useState<Record<string, boolean>>({});
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dispatch = useCallback(
    (behavior: BehaviorContract) => {
      switch (behavior.type) {
        case 'route-navigate':
          onRouteNavigate?.(behavior.route);
          break;

        case 'hash-navigate': {
          const id = behavior.hash.replace(/^#/, '');
          if (typeof document !== 'undefined') {
            document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
          }
          break;
        }

        case 'external-link':
          if (typeof window !== 'undefined') {
            window.open(behavior.href, behavior.target ?? '_blank');
          }
          break;

        case 'tab-sync':
          setTabs((prev) => ({ ...prev, [behavior.tabGroupId]: behavior.tabId }));
          break;

        case 'dialog-open':
          setDialogs((prev) => ({ ...prev, [behavior.dialogId]: true }));
          break;

        case 'dialog-close':
          setDialogs((prev) => ({ ...prev, [behavior.dialogId]: false }));
          break;

        case 'fullscreen-media':
          if (typeof document !== 'undefined') {
            document.getElementById(behavior.mediaRef)?.requestFullscreen?.();
          }
          break;

        case 'toast': {
          const id = generateToastId();
          const item: ToastItem = { id, message: behavior.message, variant: behavior.variant };
          setToasts((prev) => [...prev, item]);
          const timer = setTimeout(() => {
            setToasts((prev) => prev.filter((t) => t.id !== id));
            toastTimers.current.delete(id);
          }, TOAST_DURATION);
          toastTimers.current.set(id, timer);
          break;
        }

        default:
          console.warn('Unknown behavior type:', (behavior as { type: string }).type);
      }
    },
    [onRouteNavigate],
  );

  const value: BehaviorContextValue = { dispatch, state: { tabs, dialogs, toasts } };

  return <BehaviorContext.Provider value={value}>{children}</BehaviorContext.Provider>;
}

/** Returns the dispatch function for triggering behaviors. */
export function useBehaviorDispatch(): (behavior: BehaviorContract) => void {
  const ctx = useContext(BehaviorContext);
  if (!ctx) throw new Error('useBehaviorDispatch must be used within BehaviorDispatcherProvider');
  return ctx.dispatch;
}

/** Returns the active tab id for a given tab group. */
export function useTabState(tabGroupId: string): string | undefined {
  const ctx = useContext(BehaviorContext);
  if (!ctx) throw new Error('useTabState must be used within BehaviorDispatcherProvider');
  return ctx.state.tabs[tabGroupId];
}

/** Returns whether a dialog is open. */
export function useDialogState(dialogId: string): boolean {
  const ctx = useContext(BehaviorContext);
  if (!ctx) throw new Error('useDialogState must be used within BehaviorDispatcherProvider');
  return ctx.state.dialogs[dialogId] ?? false;
}

/** Returns the current toast queue. */
export function useToasts(): ToastItem[] {
  const ctx = useContext(BehaviorContext);
  if (!ctx) throw new Error('useToasts must be used within BehaviorDispatcherProvider');
  return ctx.state.toasts;
}
