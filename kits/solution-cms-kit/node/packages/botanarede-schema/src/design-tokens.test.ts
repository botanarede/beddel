import { describe, it, expect } from 'vitest';

import {
  DesignTokensSchema,
  ColorTokensSchema,
  TypographyTokensSchema,
  SpacingTokensSchema,
  BreakpointsSchema,
} from './design-tokens';

describe('DesignTokensSchema', () => {
  it('parses empty object (all sections optional)', () => {
    const result = DesignTokensSchema.safeParse({});
    expect(result.success).toBe(true);
  });

  it('parses object with all sections', () => {
    const result = DesignTokensSchema.safeParse({
      colors: { primary: '#3b82f6' },
      typography: { fontFamilies: { sans: 'Inter, sans-serif' } },
      spacing: { sm: '0.5rem' },
      breakpoints: { md: '768px' },
      custom: { radius: '8px' },
    });
    expect(result.success).toBe(true);
  });

  it('rejects unknown top-level keys', () => {
    const result = DesignTokensSchema.safeParse({
      colors: { primary: '#000' },
      unknownSection: { foo: 'bar' },
    });
    expect(result.success).toBe(false);
  });
});

describe('ColorTokensSchema', () => {
  it('parses flat color tokens', () => {
    const result = ColorTokensSchema.safeParse({
      primary: '#3b82f6',
      secondary: 'rgb(59,130,246)',
      accent: 'hsl(210, 100%, 50%)',
    });
    expect(result.success).toBe(true);
  });

  it('parses nested grouped color tokens', () => {
    const result = ColorTokensSchema.safeParse({
      primary: { '50': '#f0f9ff', '500': '#0ea5e9', '900': '#0c4a6e' },
    });
    expect(result.success).toBe(true);
  });

  it('parses mixed flat and nested color tokens', () => {
    const result = ColorTokensSchema.safeParse({
      primary: '#3b82f6',
      secondary: { '50': '#f0f9ff', '500': '#0ea5e9' },
    });
    expect(result.success).toBe(true);
  });

  it('rejects non-string color values', () => {
    const result = ColorTokensSchema.safeParse({ primary: 123 });
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['primary']);
    }
  });
});

describe('TypographyTokensSchema', () => {
  it('parses typography with all sub-fields', () => {
    const result = TypographyTokensSchema.safeParse({
      fontFamilies: { sans: 'Inter, sans-serif', mono: 'Fira Code, monospace' },
      fontSizes: { sm: '0.875rem', base: '1rem', lg: '1.125rem' },
      fontWeights: { normal: '400', bold: '700' },
      lineHeights: { tight: '1.25', normal: '1.5', relaxed: '1.75' },
    });
    expect(result.success).toBe(true);
  });

  it('parses typography with only some sub-fields', () => {
    const result = TypographyTokensSchema.safeParse({
      fontFamilies: { sans: 'Inter' },
    });
    expect(result.success).toBe(true);
  });

  it('rejects unknown keys in typography', () => {
    const result = TypographyTokensSchema.safeParse({
      fontFamilies: { sans: 'Inter' },
      bogus: 'should-fail',
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const keys = result.error.issues.map((i) => (i as { keys?: string[] }).keys ?? []);
      expect(keys).toContainEqual(['bogus']);
    }
  });
});

describe('SpacingTokensSchema', () => {
  it('parses named spacing values', () => {
    const result = SpacingTokensSchema.safeParse({
      xs: '0.25rem',
      sm: '0.5rem',
      md: '1rem',
      lg: '1.5rem',
      xl: '2rem',
    });
    expect(result.success).toBe(true);
  });

  it('rejects non-string spacing values', () => {
    const result = SpacingTokensSchema.safeParse({ sm: 8 });
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['sm']);
    }
  });
});

describe('BreakpointsSchema', () => {
  it('parses named breakpoints', () => {
    const result = BreakpointsSchema.safeParse({
      sm: '640px',
      md: '768px',
      lg: '1024px',
      xl: '1280px',
    });
    expect(result.success).toBe(true);
  });
});

describe('custom section', () => {
  it('accepts arbitrary string key-value pairs', () => {
    const result = DesignTokensSchema.safeParse({
      custom: { borderRadius: '8px', shadow: '0 2px 4px rgba(0,0,0,0.1)' },
    });
    expect(result.success).toBe(true);
  });

  it('rejects non-string values in custom', () => {
    const result = DesignTokensSchema.safeParse({
      custom: { radius: 8 },
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path);
      expect(paths).toContainEqual(['custom', 'radius']);
    }
  });
});
