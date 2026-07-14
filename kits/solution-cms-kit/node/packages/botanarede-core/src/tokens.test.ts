import { describe, it, expect } from 'vitest';
import type { DesignTokens } from '@botanarede/schema';
import { resolveToken, resolveTokensInProps } from './tokens';

const tokens: DesignTokens = {
  colors: {
    primary: '#c8a96e',
    neutral: { 50: '#fafafa', 900: '#171717' },
  },
  typography: {
    fontFamilies: { sans: 'Inter, sans-serif' },
    fontSizes: { sm: '0.875rem', lg: '1.125rem' },
  },
  spacing: { sm: '0.5rem', md: '1rem', lg: '1.5rem' },
  custom: { borderRadius: '8px' },
};

describe('resolveToken', () => {
  it('resolves flat token path "$colors.primary" to CSS value', () => {
    expect(resolveToken(tokens, '$colors.primary')).toBe('#c8a96e');
  });

  it('resolves nested token path "$typography.fontSizes.lg" to leaf value', () => {
    expect(resolveToken(tokens, '$typography.fontSizes.lg')).toBe('1.125rem');
  });

  it('resolves nested color token "$colors.neutral.50" to leaf value', () => {
    expect(resolveToken(tokens, '$colors.neutral.50')).toBe('#fafafa');
  });

  it('returns undefined for non-existent token path', () => {
    expect(resolveToken(tokens, '$colors.nonexistent')).toBeUndefined();
  });

  it('returns undefined when intermediate segment is missing', () => {
    expect(resolveToken(tokens, '$missing.deep.path')).toBeUndefined();
  });

  it('returns plain CSS value unchanged when not starting with "$"', () => {
    expect(resolveToken(tokens, '16px')).toBe('16px');
    expect(resolveToken(tokens, '#ff0000')).toBe('#ff0000');
  });
});

describe('resolveTokensInProps', () => {
  it('resolves all token references in a props object', () => {
    const props = {
      backgroundColor: '$colors.primary',
      fontSize: '$typography.fontSizes.lg',
    };
    expect(resolveTokensInProps(tokens, props)).toEqual({
      backgroundColor: '#c8a96e',
      fontSize: '1.125rem',
    });
  });

  it('leaves non-token values unchanged', () => {
    const props = {
      width: '100%',
      color: '#000',
    };
    expect(resolveTokensInProps(tokens, props)).toEqual({
      width: '100%',
      color: '#000',
    });
  });

  it('keeps original token string when token is not found', () => {
    const props = {
      color: '$colors.nonexistent',
      padding: '$spacing.sm',
    };
    expect(resolveTokensInProps(tokens, props)).toEqual({
      color: '$colors.nonexistent',
      padding: '0.5rem',
    });
  });
});
