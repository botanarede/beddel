/**
 * Schema Types - Shared type definitions for agent schemas
 * Used for input/output validation on both client and server
 */

/**
 * JSON Schema-like type definition
 */
export interface SchemaProperty {
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  description?: string;
  enum?: string[];
  items?: SchemaProperty;
  properties?: Record<string, SchemaProperty>;
  required?: string[];
  default?: unknown;
  minLength?: number;
  maxLength?: number;
  minimum?: number;
  maximum?: number;
  pattern?: string;
}

/**
 * Agent schema definition
 */
export interface AgentSchemaDefinition {
  input: {
    type: 'object';
    properties: Record<string, SchemaProperty>;
    required?: string[];
  };
  output: {
    type: 'object';
    properties: Record<string, SchemaProperty>;
    required?: string[];
  };
}

/**
 * Validation result
 */
export interface ValidationResult {
  valid: boolean;
  errors?: ValidationError[];
}

/**
 * Validation error detail
 */
export interface ValidationError {
  path: string;
  message: string;
  code: string;
}
