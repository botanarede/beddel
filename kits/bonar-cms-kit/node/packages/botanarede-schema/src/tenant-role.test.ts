import { describe, it, expect } from 'vitest';
import { hasMinimumRole } from './tenant-role';

describe('hasMinimumRole', () => {
  it('admin meets minimum editor', () => {
    expect(hasMinimumRole(['admin'], 'editor')).toBe(true);
  });

  it('editor does not meet minimum admin', () => {
    expect(hasMinimumRole(['editor'], 'admin')).toBe(false);
  });

  it('owner meets minimum admin', () => {
    expect(hasMinimumRole(['owner'], 'admin')).toBe(true);
  });

  it('highest role wins when user has multiple roles', () => {
    expect(hasMinimumRole(['editor', 'admin'], 'admin')).toBe(true);
  });

  it('empty array does not meet any minimum', () => {
    expect(hasMinimumRole([], 'editor')).toBe(false);
  });
});
