import { z } from 'zod';

/**
 * Color tokens — flat string-to-string record or nested grouped records.
 * Supports both `{ primary: "#3b82f6" }` and `{ primary: { 50: "#f0f9ff", 500: "#0ea5e9" } }`.
 */
export const ColorTokensSchema = z.record(
  z.string(),
  z.union([z.string(), z.record(z.string(), z.string())]),
);

export type ColorTokens = z.infer<typeof ColorTokensSchema>;

/**
 * Typography tokens — named groups for font families, sizes, weights, and line heights.
 * All sub-fields are optional.
 */
export const TypographyTokensSchema = z
  .object({
    fontFamilies: z.record(z.string(), z.string()).optional(),
    fontSizes: z.record(z.string(), z.string()).optional(),
    fontWeights: z.record(z.string(), z.string()).optional(),
    lineHeights: z.record(z.string(), z.string()).optional(),
  })
  .strict();

export type TypographyTokens = z.infer<typeof TypographyTokensSchema>;

/** Spacing tokens — named spacing values mapped to CSS length values. */
export const SpacingTokensSchema = z.record(z.string(), z.string());

export type SpacingTokens = z.infer<typeof SpacingTokensSchema>;

/** Breakpoints — named breakpoints mapped to min-width CSS values. */
export const BreakpointsSchema = z.record(z.string(), z.string());

export type Breakpoints = z.infer<typeof BreakpointsSchema>;

/**
 * Design tokens schema — defines the visual language of a tenant.
 * All sections are optional. Strict object rejects unknown top-level keys.
 */
export const DesignTokensSchema = z
  .object({
    colors: ColorTokensSchema.optional(),
    typography: TypographyTokensSchema.optional(),
    spacing: SpacingTokensSchema.optional(),
    breakpoints: BreakpointsSchema.optional(),
    backgroundImage: z.string().optional(),
    custom: z.record(z.string(), z.string()).optional(),
  })
  .strict();

export type DesignTokens = z.infer<typeof DesignTokensSchema>;
