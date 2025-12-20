/**
 * Image Agent - Public exports (client-safe)
 */

// Schema exports (client-safe)
export { ImageInputSchema, ImageOutputSchema } from './image.schema';
export type { ImageInput, ImageOutput } from './image.schema';

// Type exports (client-safe)
export type { ImageStyle, ImageHandlerParams, ImageHandlerResult, ImageMetadata } from './image.types';

// Metadata (client-safe)
export const imageMetadata = {
  id: 'image',
  name: 'Image Generator Agent',
  description: 'Generates images using Gemini Flash with curated styles',
  category: 'creative',
  route: '/agents/image',
} as const;
