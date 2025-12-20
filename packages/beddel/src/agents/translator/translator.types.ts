/**
 * Translator Agent Types - Shared between client and server
 */

/**
 * Parameters for translation
 */
export interface TranslationHandlerParams {
  text: string;
  source_language: string;
  target_language: string;
  promptTemplate?: string;
}

/**
 * Result from translation
 */
export interface TranslationHandlerResult {
  translated_text: string;
  metadata: {
    model_used: string;
    processing_time: number;
    confidence: number;
    supported_languages: string[];
    requested_languages: {
      source: string;
      target: string;
    };
    prompt_used: string;
  };
}

/**
 * Translator agent metadata
 */
export interface TranslatorMetadata {
  id: 'translator';
  name: string;
  description: string;
  category: 'translation';
  route: '/agents/translator';
}
