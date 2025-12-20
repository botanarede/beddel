/**
 * Image Agent Types - Shared between client and server
 */

/**
 * Supported image styles
 */
export type ImageStyle = 'watercolor' | 'neon' | 'sketch' | string;

/**
 * Parameters for image generation
 */
export interface ImageHandlerParams {
  description: string;
  style: ImageStyle;
  resolution: string;
  promptTemplate?: string;
}

/**
 * Result from image generation
 */
export interface ImageHandlerResult {
  image_url: string;
  image_base64: string;
  media_type: string;
  prompt_used: string;
  metadata: {
    model_used: string;
    processing_time: number;
    style: string;
    resolution: string;
  };
}

/**
 * Image agent metadata
 */
export interface ImageMetadata {
  id: 'image';
  name: string;
  description: string;
  category: 'creative';
  route: '/agents/image';
}
