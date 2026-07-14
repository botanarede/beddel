/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { FormBindingConfigSchema } from '@botanarede/schema';
import type { FormBindingConfig } from '@botanarede/schema';
import { BehaviorDispatcherProvider, useToasts } from '../behaviors/dispatcher';
import { useFormBinding } from './use-form-binding';

// Helper to render hook inside BehaviorDispatcherProvider
function renderFormHook(config: FormBindingConfig) {
  let result: ReturnType<typeof useFormBinding>;
  const container = document.createElement('div');
  document.body.appendChild(container);

  function TestComp() {
    result = useFormBinding(config);
    return null;
  }

  let root: ReturnType<typeof createRoot>;
  act(() => {
    root = createRoot(container);
    root.render(
      <BehaviorDispatcherProvider>
        <TestComp />
      </BehaviorDispatcherProvider>,
    );
  });

  return {
    getResult: () => result!,
    unmount: () => {
      act(() => root.unmount());
      container.remove();
    },
  };
}

describe('FormBindingConfigSchema', () => {
  it('accepts all 6 field types', () => {
    const config = {
      fields: [
        { name: 'name', type: 'text', label: 'Name' },
        { name: 'email', type: 'email', label: 'Email' },
        { name: 'phone', type: 'tel', label: 'Phone' },
        { name: 'message', type: 'textarea', label: 'Message' },
        { name: 'topic', type: 'select', label: 'Topic', options: ['A', 'B'] },
        { name: 'agree', type: 'checkbox', label: 'I agree' },
      ],
      submitBehavior: { type: 'toast-feedback' as const, message: 'Sent!' },
    };
    expect(FormBindingConfigSchema.safeParse(config).success).toBe(true);
  });

  it('rejects config with empty fields array', () => {
    const config = {
      fields: [],
      submitBehavior: { type: 'toast-feedback' as const, message: 'Sent!' },
    };
    expect(FormBindingConfigSchema.safeParse(config).success).toBe(false);
  });
});

describe('useFormBinding', () => {
  const baseConfig: FormBindingConfig = {
    fields: [
      { name: 'name', type: 'text', label: 'Name', required: true },
      { name: 'email', type: 'email', label: 'Email' },
    ],
    submitBehavior: { type: 'api-submit', endpoint: '/api/contact' },
  };

  it('handleSubmit with required field empty sets errors and does NOT call fetch', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response());
    const { getResult, unmount } = renderFormHook(baseConfig);

    await act(async () => {
      await getResult().handleSubmit();
    });

    expect(getResult().errors['name']).toBe('Name is required');
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
    unmount();
  });

  it('handleSubmit with api-submit and valid values calls fetch correctly', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response());
    const { getResult, unmount } = renderFormHook(baseConfig);

    act(() => {
      getResult().handleChange('name', 'John');
      getResult().handleChange('email', 'john@example.com');
    });

    await act(async () => {
      await getResult().handleSubmit();
    });

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [url, opts] = fetchSpy.mock.calls[0]!;
    expect(url).toBe('/api/contact');
    expect((opts as RequestInit).method).toBe('POST');
    expect((opts as RequestInit).headers).toEqual({ 'Content-Type': 'application/json' });
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.name).toBe('John');
    expect(body.email).toBe('john@example.com');
    fetchSpy.mockRestore();
    unmount();
  });

  it('handleSubmit with toast-feedback dispatches toast', async () => {
    const toastConfig: FormBindingConfig = {
      fields: [{ name: 'msg', type: 'text', label: 'Message' }],
      submitBehavior: { type: 'toast-feedback', message: 'Thank you!' },
    };

    const container = document.createElement('div');
    document.body.appendChild(container);
    let hookResult: ReturnType<typeof useFormBinding>;
    let toastCount = 0;

    function TestComp() {
      hookResult = useFormBinding(toastConfig);
      return null;
    }

    function ToastChecker() {
      const toasts = useToasts();
      toastCount = toasts.length;
      return null;
    }

    let root: ReturnType<typeof createRoot>;
    act(() => {
      root = createRoot(container);
      root.render(
        <BehaviorDispatcherProvider>
          <TestComp />
          <ToastChecker />
        </BehaviorDispatcherProvider>,
      );
    });

    await act(async () => {
      await hookResult!.handleSubmit();
    });

    expect(toastCount).toBe(1);
    act(() => root.unmount());
    container.remove();
  });

  it('handleChange updates values and clears corresponding error', async () => {
    const { getResult, unmount } = renderFormHook(baseConfig);

    await act(async () => {
      await getResult().handleSubmit();
    });
    expect(getResult().errors['name']).toBeDefined();

    act(() => {
      getResult().handleChange('name', 'Alice');
    });

    expect(getResult().values['name']).toBe('Alice');
    expect(getResult().errors['name']).toBeUndefined();
    unmount();
  });
});
