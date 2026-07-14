/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { BehaviorContractSchema } from '../behaviors';
import type { BehaviorContract } from '../behaviors';
import {
  BehaviorDispatcherProvider,
  useBehaviorDispatch,
  useTabState,
  useDialogState,
  useToasts,
} from './dispatcher';

// Helper to render a hook inside the provider
function renderWithProvider(TestComponent: React.FC, onRouteNavigate?: (r: string) => void) {
  const container = document.createElement('div');
  document.body.appendChild(container);
  let root: ReturnType<typeof createRoot>;
  act(() => {
    root = createRoot(container);
    root.render(
      <BehaviorDispatcherProvider onRouteNavigate={onRouteNavigate}>
        <TestComponent />
      </BehaviorDispatcherProvider>,
    );
  });
  return {
    container,
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
}

describe('BehaviorContractSchema — fullscreen-media', () => {
  it('accepts fullscreen-media with mediaRef', () => {
    const result = BehaviorContractSchema.safeParse({
      type: 'fullscreen-media',
      mediaRef: 'video-1',
    });
    expect(result.success).toBe(true);
  });
});

describe('tab-sync behavior', () => {
  it('updates tab state for the correct tabGroupId', () => {
    let tabValue: string | undefined;
    let dispatchFn: (b: BehaviorContract) => void;

    function TestComp() {
      dispatchFn = useBehaviorDispatch();
      tabValue = useTabState('main-tabs');
      return <div data-testid="tab">{tabValue ?? 'none'}</div>;
    }

    const { container, unmount } = renderWithProvider(TestComp);

    expect(container.textContent).toContain('none');

    act(() => {
      dispatchFn({ type: 'tab-sync', tabGroupId: 'main-tabs', tabId: 'tab-2' });
    });

    expect(container.textContent).toContain('tab-2');
    unmount();
  });
});

describe('dialog-open / dialog-close behavior', () => {
  it('sets dialog state to true on open and false on close', () => {
    let dialogOpen = false;
    let dispatchFn: (b: BehaviorContract) => void;

    function TestComp() {
      dispatchFn = useBehaviorDispatch();
      dialogOpen = useDialogState('my-dialog');
      return <div>{dialogOpen ? 'open' : 'closed'}</div>;
    }

    const { container, unmount } = renderWithProvider(TestComp);
    expect(container.textContent).toContain('closed');

    act(() => {
      dispatchFn({ type: 'dialog-open', dialogId: 'my-dialog' });
    });
    expect(container.textContent).toContain('open');

    act(() => {
      dispatchFn({ type: 'dialog-close', dialogId: 'my-dialog' });
    });
    expect(container.textContent).toContain('closed');
    unmount();
  });
});

describe('toast behavior', () => {
  it('adds a toast to the queue', () => {
    let toastList: { id: string; message: string }[] = [];
    let dispatchFn: (b: BehaviorContract) => void;

    function TestComp() {
      dispatchFn = useBehaviorDispatch();
      toastList = useToasts();
      return <div>{toastList.length}</div>;
    }

    const { container, unmount } = renderWithProvider(TestComp);
    expect(container.textContent).toContain('0');

    act(() => {
      dispatchFn({ type: 'toast', message: 'Hello!', variant: 'success' });
    });

    expect(container.textContent).toContain('1');
    expect(toastList[0]!.message).toBe('Hello!');
    unmount();
  });
});

describe('unknown behavior type', () => {
  it('logs console.warn and does not throw', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    let dispatchFn: (b: BehaviorContract) => void;

    function TestComp() {
      dispatchFn = useBehaviorDispatch();
      return <div>ok</div>;
    }

    const { unmount } = renderWithProvider(TestComp);

    act(() => {
      dispatchFn({ type: 'nonexistent-type' } as unknown as BehaviorContract);
    });

    expect(warnSpy).toHaveBeenCalledWith('Unknown behavior type:', 'nonexistent-type');
    warnSpy.mockRestore();
    unmount();
  });
});

describe('route-navigate behavior', () => {
  it('calls onRouteNavigate prop', () => {
    const onNav = vi.fn();
    let dispatchFn: (b: BehaviorContract) => void;

    function TestComp() {
      dispatchFn = useBehaviorDispatch();
      return <div>nav</div>;
    }

    const { unmount } = renderWithProvider(TestComp, onNav);

    act(() => {
      dispatchFn({ type: 'route-navigate', route: '/dashboard' });
    });

    expect(onNav).toHaveBeenCalledWith('/dashboard');
    unmount();
  });
});
