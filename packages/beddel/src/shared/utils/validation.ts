/**
 * Validation Utilities - Shared validation helpers
 * Safe for use in both client and server environments
 */

import type { ValidationResult, ValidationError } from '../types/schema.types';

/**
 * Validate that a value is a non-empty string
 */
export function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

/**
 * Validate that a value is a positive number
 */
export function isPositiveNumber(value: unknown): value is number {
  return typeof value === 'number' && value > 0 && !isNaN(value);
}

/**
 * Validate that a value is a valid URL
 */
export function isValidUrl(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  try {
    new URL(value);
    return true;
  } catch {
    return false;
  }
}

/**
 * Validate resolution format (e.g., "1024x1024")
 */
export function isValidResolution(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  return /^\d+x\d+$/.test(value);
}

/**
 * Validate language code (e.g., "en", "pt", "es")
 */
export function isValidLanguageCode(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  return /^[a-z]{2}(-[A-Z]{2})?$/.test(value);
}

/**
 * Create a validation result with errors
 */
export function createValidationResult(errors: ValidationError[]): ValidationResult {
  return {
    valid: errors.length === 0,
    errors: errors.length > 0 ? errors : undefined,
  };
}

/**
 * Create a validation error
 */
export function createValidationError(
  path: string,
  message: string,
  code: string
): ValidationError {
  return { path, message, code };
}

/**
 * Sanitize string input by trimming whitespace
 */
export function sanitizeString(value: unknown): string {
  if (typeof value !== 'string') return '';
  return value.trim();
}

/**
 * Validate required fields in an object
 */
export function validateRequiredFields(
  obj: Record<string, unknown>,
  requiredFields: string[]
): ValidationError[] {
  const errors: ValidationError[] = [];
  
  for (const field of requiredFields) {
    if (obj[field] === undefined || obj[field] === null) {
      errors.push(createValidationError(
        field,
        `Missing required field: ${field}`,
        'REQUIRED_FIELD_MISSING'
      ));
    }
  }
  
  return errors;
}
