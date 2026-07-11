/**
 * Form binding contract — Zod schemas for declarative form definitions.
 *
 * Tenant JSON declares form fields and submit behavior; the runtime
 * useFormBinding hook consumes this config to manage form state.
 */

import { z } from 'zod';

export const FormFieldSchema = z
  .object({
    name: z.string().min(1),
    type: z.enum(['text', 'email', 'tel', 'textarea', 'select', 'checkbox']),
    label: z.string().min(1),
    required: z.boolean().optional(),
    options: z.array(z.string()).optional(),
  })
  .strict();

export type FormField = z.infer<typeof FormFieldSchema>;

const ApiSubmitSchema = z
  .object({
    type: z.literal('api-submit'),
    endpoint: z.string().min(1),
  })
  .strict();

const ToastFeedbackSchema = z
  .object({
    type: z.literal('toast-feedback'),
    message: z.string().min(1),
  })
  .strict();

export const SubmitBehaviorSchema = z.discriminatedUnion('type', [
  ApiSubmitSchema,
  ToastFeedbackSchema,
]);

export type SubmitBehavior = z.infer<typeof SubmitBehaviorSchema>;

export const FormBindingConfigSchema = z
  .object({
    fields: z.array(FormFieldSchema).min(1),
    submitBehavior: SubmitBehaviorSchema,
  })
  .strict();

export type FormBindingConfig = z.infer<typeof FormBindingConfigSchema>;
