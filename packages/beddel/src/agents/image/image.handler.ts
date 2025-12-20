import 'server-only';

/**
 * Image Agent Handler - Server-only execution logic
 * Generates images using Gemini Flash with curated styles
 */

import { experimental_generateImage } from 'ai';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import type { ExecutionContext } from '../../types/executionContext';
import type { ImageHandlerParams, ImageHandlerResult } from './image.types';

const GEMINI_IMAGE_MODEL = 'imagen-4.0-fast-generate-001';

/**
 * Execute image generation using Gemini
 */
export async function executeImageHandler(
  params: ImageHandlerParams,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<ImageHandlerResult> {
  const apiKey = props?.gemini_api_key?.trim();
  if (!apiKey) {
    throw new Error('Missing required prop: gemini_api_key');
  }

  const description = params.description?.trim();
  const style = params.style?.trim();
  const resolution = params.resolution?.trim();

  if (!description) {
    throw new Error('Missing required image input: description');
  }
  if (!style) {
    throw new Error('Missing required image input: style');
  }
  if (!resolution || !/^\d+x\d+$/.test(resolution)) {
    throw new Error('Missing required image input: resolution (format: WIDTHxHEIGHT)');
  }

  const promptTemplate = params.promptTemplate?.trim() ||
    'Create a detailed image in {{style}} style focusing on: {{description}}';

  const prompt = promptTemplate
    .replace(/{{description}}/g, description)
    .replace(/{{style}}/g, style)
    .trim();

  const google = createGoogleGenerativeAI({ apiKey });
  const model = google.image(GEMINI_IMAGE_MODEL);
  const startTime = Date.now();

  context.log(`[Image] Generating image with style=${style}, resolution=${resolution}`);

  const result = await experimental_generateImage({
    model,
    prompt,
    size: resolution as `${number}x${number}`,
  });

  const image = result.image;
  if (!image?.base64 || !image.mediaType) {
    throw new Error('Gemini Flash image helper returned an invalid file');
  }

  const normalizedBase64 = image.base64.replace(/\s+/g, '');
  const imageUrl = `data:${image.mediaType};base64,${normalizedBase64}`;

  return {
    image_url: imageUrl,
    image_base64: normalizedBase64,
    media_type: image.mediaType,
    prompt_used: prompt,
    metadata: {
      model_used: GEMINI_IMAGE_MODEL,
      processing_time: Date.now() - startTime,
      style,
      resolution,
    },
  };
}
