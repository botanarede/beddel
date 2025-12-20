import 'server-only';

/**
 * Joker Agent Handler - Server-only execution logic
 * Generates jokes using Gemini Flash
 */

import { generateText } from 'ai';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import type { ExecutionContext } from '../../types/executionContext';
import type { JokeHandlerParams, JokeHandlerResult } from './joker.types';

const GEMINI_MODEL = 'models/gemini-2.5-flash';

/**
 * Execute joke generation using Gemini Flash
 */
export async function executeJokeHandler(
  params: JokeHandlerParams,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<JokeHandlerResult> {
  const apiKey = props?.gemini_api_key?.trim();
  if (!apiKey) {
    throw new Error('Missing required prop: gemini_api_key');
  }

  const prompt = params.prompt?.trim() || 'Tell a short and original joke that works for any audience.';
  const temperature = params.temperature ?? 0.8;
  const maxTokens = params.maxTokens;

  const google = createGoogleGenerativeAI({ apiKey });
  const model = google(GEMINI_MODEL);
  const startTime = Date.now();

  context.log(`[Joker] Generating joke with temperature=${temperature}`);

  const { text } = await generateText({
    model,
    prompt,
    temperature,
    ...(maxTokens && { maxOutputTokens: maxTokens }),
  });

  const finalText = text?.trim() || '';
  if (!finalText) {
    throw new Error('Gemini returned empty response');
  }

  return {
    text: finalText,
    metadata: {
      model_used: GEMINI_MODEL,
      processing_time: Date.now() - startTime,
      temperature,
      max_tokens: maxTokens ?? null,
      prompt_used: prompt,
    },
  };
}
