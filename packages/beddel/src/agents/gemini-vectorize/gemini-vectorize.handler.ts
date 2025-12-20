import 'server-only';

/**
 * Gemini Vectorize Agent Handler - Server-only execution logic
 * Generates text embeddings using Google's Gemini text-embedding-004 model
 */

import { embed, embedMany } from 'ai';
import { google } from '@ai-sdk/google';
import type { ExecutionContext } from '../../types/executionContext';
import type { VectorizeHandlerParams, VectorizeHandlerResult } from './gemini-vectorize.types';

const GEMINI_EMBEDDING_MODEL = 'text-embedding-004';

/**
 * Execute vectorization using Gemini embeddings
 */
export async function executeVectorizeHandler(
  params: VectorizeHandlerParams,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<VectorizeHandlerResult> {
  const apiKey = props?.gemini_api_key?.trim();
  if (!apiKey) {
    throw new Error('Missing required prop: gemini_api_key');
  }

  // Set API key in environment for google provider
  process.env.GOOGLE_GENERATIVE_AI_API_KEY = apiKey;

  const action = params.action || 'embedSingle';

  try {
    if (action === 'embedSingle') {
      const text = params.text;
      if (!text) {
        throw new Error('Text input is required for embedSingle');
      }

      context.log(`[Gemini Vectorize] Embedding single text (${text.length} chars)...`);

      const { embedding } = await embed({
        model: google.textEmbeddingModel(GEMINI_EMBEDDING_MODEL),
        value: text,
      });

      return { success: true, vector: embedding };

    } else if (action === 'embedBatch') {
      const texts = params.texts;
      if (!texts || !Array.isArray(texts)) {
        throw new Error('Texts array input is required for embedBatch');
      }

      context.log(`[Gemini Vectorize] Embedding batch of ${texts.length} texts...`);

      const { embeddings } = await embedMany({
        model: google.textEmbeddingModel(GEMINI_EMBEDDING_MODEL),
        values: texts,
      });

      return { success: true, vectors: embeddings };

    } else {
      throw new Error(`Unknown vectorize action: ${action}`);
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    context.log(`[Gemini Vectorize] Error: ${message}`);
    return { success: false, error: message };
  }
}
