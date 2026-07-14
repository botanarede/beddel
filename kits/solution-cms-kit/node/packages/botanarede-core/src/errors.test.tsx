import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { JSDOM } from 'jsdom';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { UnknownComponentFallback, ComponentErrorFallback, ComponentErrorBoundary } from './errors';

// --- UnknownComponentFallback ---

describe('UnknownComponentFallback', () => {
  it('renders a div with data-unknown-component attribute set to the component type', () => {
    const html = renderToStaticMarkup(<UnknownComponentFallback type="HeroBlock" />);
    expect(html).toContain('data-unknown-component="HeroBlock"');
  });

  it('shows visible warning text in development', () => {
    const html = renderToStaticMarkup(<UnknownComponentFallback type="MissingWidget" />);
    expect(html).toContain('Unknown component: MissingWidget');
  });
});

// --- ComponentErrorFallback ---

describe('ComponentErrorFallback', () => {
  it('renders a div with data-error-component attribute set to the component type', () => {
    const html = renderToStaticMarkup(<ComponentErrorFallback type="BrokenCard" />);
    expect(html).toContain('data-error-component="BrokenCard"');
  });

  it('shows the component type and a generic error message in development', () => {
    const html = renderToStaticMarkup(<ComponentErrorFallback type="BrokenCard" />);
    expect(html).toContain('Component &quot;BrokenCard&quot; failed to render');
  });

  it('does NOT show a raw error stack', () => {
    const html = renderToStaticMarkup(<ComponentErrorFallback type="BrokenCard" />);
    expect(html).not.toContain('Error:');
    expect(html).not.toContain('at ');
    expect(html).not.toContain('stack');
  });
});

// --- ComponentErrorBoundary (requires DOM) ---

function ThrowingComponent({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Boom');
  }
  return <div data-testid="child">OK</div>;
}

function setupDOM() {
  const dom = new JSDOM('<!DOCTYPE html><html><body><div id="root"></div></body></html>');
  const container = dom.window.document.getElementById('root')!;
  const origWindow = globalThis.window;
  const origDocument = globalThis.document;
  (globalThis as any).window = dom.window;
  (globalThis as any).document = dom.window.document;
  return {
    container,
    cleanup() {
      (globalThis as any).window = origWindow;
      (globalThis as any).document = origDocument;
    },
  };
}

describe('ComponentErrorBoundary', () => {
  let env: ReturnType<typeof setupDOM>;

  beforeEach(() => {
    env = setupDOM();
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    env.cleanup();
    vi.restoreAllMocks();
  });

  it('renders children normally when no error occurs', () => {
    let root: ReturnType<typeof createRoot>;
    act(() => {
      root = createRoot(env.container);
      root.render(
        <ComponentErrorBoundary componentType="TestComp">
          <div data-testid="child">Hello</div>
        </ComponentErrorBoundary>,
      );
    });
    expect(env.container.innerHTML).toContain('data-testid="child"');
    expect(env.container.innerHTML).toContain('Hello');
    expect(env.container.innerHTML).not.toContain('data-error-component');
    act(() => { root!.unmount(); });
  });

  it('catches render errors and renders ComponentErrorFallback', () => {
    let root: ReturnType<typeof createRoot>;
    act(() => {
      root = createRoot(env.container);
      root.render(
        <ComponentErrorBoundary componentType="BrokenWidget">
          <ThrowingComponent shouldThrow={true} />
        </ComponentErrorBoundary>,
      );
    });
    expect(env.container.innerHTML).toContain('data-error-component="BrokenWidget"');
    expect(env.container.innerHTML).toContain('Component "BrokenWidget" failed to render');
    act(() => { root!.unmount(); });
  });

  it('invokes onError callback with the error and component type', () => {
    const onError = vi.fn();
    let root: ReturnType<typeof createRoot>;
    act(() => {
      root = createRoot(env.container);
      root.render(
        <ComponentErrorBoundary componentType="CallbackTest" onError={onError}>
          <ThrowingComponent shouldThrow={true} />
        </ComponentErrorBoundary>,
      );
    });
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith(expect.any(Error), 'CallbackTest');
    act(() => { root!.unmount(); });
  });

  it('does not propagate the error up the tree', () => {
    let root: ReturnType<typeof createRoot>;
    act(() => {
      root = createRoot(env.container);
      root.render(
        <div>
          <div data-testid="sibling">Sibling OK</div>
          <ComponentErrorBoundary componentType="Isolated">
            <ThrowingComponent shouldThrow={true} />
          </ComponentErrorBoundary>
        </div>,
      );
    });
    expect(env.container.innerHTML).toContain('Sibling OK');
    expect(env.container.innerHTML).toContain('data-error-component="Isolated"');
    act(() => { root!.unmount(); });
  });
});
