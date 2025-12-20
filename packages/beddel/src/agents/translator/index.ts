/**
 * Translator Agent - Public exports (client-safe)
 */

// Schema exports (client-safe)
export { TranslatorInputSchema, TranslatorOutputSchema } from './translator.schema';
export type { TranslatorInput, TranslatorOutput } from './translator.schema';

// Type exports (client-safe)
export type { TranslationHandlerParams, TranslationHandlerResult, TranslatorMetadata } from './translator.types';

// Metadata (client-safe)
export const translatorMetadata = {
  id: 'translator',
  name: 'Translator Agent',
  description: 'Translates text between languages using Gemini Flash via Genkit',
  category: 'translation',
  route: '/agents/translator',
} as const;
