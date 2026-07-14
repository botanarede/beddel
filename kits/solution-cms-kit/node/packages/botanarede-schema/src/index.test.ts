import { describe, it, expect } from 'vitest';
import { PACKAGE_NAME } from './index';

describe('@botanarede/schema', () => {
  it('exports the correct PACKAGE_NAME', () => {
    expect(PACKAGE_NAME).toBe('@botanarede/schema');
  });
});
