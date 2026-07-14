import { describe, it, expect, vi } from 'vitest';
import { BehaviorContractSchema, isBehavior, dispatchBehavior } from './behaviors';
import type { BehaviorContract, BehaviorDispatcher } from './behaviors';

describe('BehaviorContractSchema', () => {
  it('parses a valid route-navigate behavior', () => {
    const result = BehaviorContractSchema.safeParse({ type: 'route-navigate', route: '/about' });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual({ type: 'route-navigate', route: '/about' });
    }
  });

  it('parses a valid hash-navigate behavior', () => {
    const result = BehaviorContractSchema.safeParse({ type: 'hash-navigate', hash: '#section-1' });
    expect(result.success).toBe(true);
  });

  it('parses a valid external-link behavior with optional target', () => {
    const result = BehaviorContractSchema.safeParse({
      type: 'external-link',
      href: 'https://example.com',
      target: '_blank',
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual({
        type: 'external-link',
        href: 'https://example.com',
        target: '_blank',
      });
    }
  });

  it('parses a valid external-link behavior without target', () => {
    const result = BehaviorContractSchema.safeParse({
      type: 'external-link',
      href: 'https://example.com',
    });
    expect(result.success).toBe(true);
  });

  it('parses a valid dialog-open behavior', () => {
    const result = BehaviorContractSchema.safeParse({
      type: 'dialog-open',
      dialogId: 'confirm-delete',
    });
    expect(result.success).toBe(true);
  });

  it('parses a valid dialog-close behavior', () => {
    const result = BehaviorContractSchema.safeParse({
      type: 'dialog-close',
      dialogId: 'confirm-delete',
    });
    expect(result.success).toBe(true);
  });

  it('parses a valid tab-sync behavior', () => {
    const result = BehaviorContractSchema.safeParse({
      type: 'tab-sync',
      tabGroupId: 'menu',
      tabId: 'lunch',
    });
    expect(result.success).toBe(true);
  });

  it('parses a valid toast behavior', () => {
    const result = BehaviorContractSchema.safeParse({ type: 'toast', message: 'Saved!' });
    expect(result.success).toBe(true);
  });

  it('parses a valid toast behavior with variant', () => {
    const result = BehaviorContractSchema.safeParse({
      type: 'toast',
      message: 'Error occurred',
      variant: 'error',
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).toEqual({ type: 'toast', message: 'Error occurred', variant: 'error' });
    }
  });

  it('rejects an unknown behavior type', () => {
    const result = BehaviorContractSchema.safeParse({ type: 'unknown-action', data: 'foo' });
    expect(result.success).toBe(false);
  });

  it('rejects a route-navigate missing route field', () => {
    const result = BehaviorContractSchema.safeParse({ type: 'route-navigate' });
    expect(result.success).toBe(false);
  });
});

describe('isBehavior', () => {
  it('returns true for a valid behavior object', () => {
    expect(isBehavior({ type: 'route-navigate', route: '/home' })).toBe(true);
  });

  it('returns false for a plain string', () => {
    expect(isBehavior('not-a-behavior')).toBe(false);
  });

  it('returns false for null', () => {
    expect(isBehavior(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isBehavior(undefined)).toBe(false);
  });

  it('returns false for an object with unknown type', () => {
    expect(isBehavior({ type: 'fly-to-moon', destination: 'crater' })).toBe(false);
  });
});

describe('dispatchBehavior', () => {
  it('invokes the dispatcher with the behavior', () => {
    const dispatcher: BehaviorDispatcher = vi.fn();
    const behavior: BehaviorContract = { type: 'dialog-open', dialogId: 'settings' };
    dispatchBehavior(dispatcher, behavior);
    expect(dispatcher).toHaveBeenCalledWith(behavior);
    expect(dispatcher).toHaveBeenCalledTimes(1);
  });
});
