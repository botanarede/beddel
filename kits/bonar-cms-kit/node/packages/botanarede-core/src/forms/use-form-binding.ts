/**
 * useFormBinding — React hook for declarative form state management.
 *
 * Consumes a FormBindingConfig and manages values, errors, and submission.
 * Integrates with BehaviorDispatcher for toast-feedback submit behavior.
 */

import { useCallback, useState } from 'react';
import type { FormBindingConfig, FormField } from '@botanarede/schema';
import { useBehaviorDispatch } from '../behaviors/dispatcher';

interface FormBindingResult {
  fields: FormField[];
  values: Record<string, string | boolean>;
  errors: Record<string, string>;
  handleChange: (name: string, value: string | boolean) => void;
  handleSubmit: () => Promise<void>;
  isSubmitting: boolean;
}

function initValues(fields: FormField[]): Record<string, string | boolean> {
  const values: Record<string, string | boolean> = {};
  for (const field of fields) {
    values[field.name] = field.type === 'checkbox' ? false : '';
  }
  return values;
}

export function useFormBinding(config: FormBindingConfig): FormBindingResult {
  const [values, setValues] = useState<Record<string, string | boolean>>(() =>
    initValues(config.fields),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const dispatch = useBehaviorDispatch();

  const handleChange = useCallback((name: string, value: string | boolean) => {
    setValues((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }, []);

  const handleSubmit = useCallback(async () => {
    // Validate required fields
    const newErrors: Record<string, string> = {};
    for (const field of config.fields) {
      if (field.required) {
        const val = values[field.name];
        if (val === '' || val === false) {
          newErrors[field.name] = `${field.label} is required`;
        }
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setIsSubmitting(true);
    try {
      if (config.submitBehavior.type === 'api-submit') {
        const response = await fetch(config.submitBehavior.endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(values),
        });
        if (!response.ok) {
          setErrors({ _submit: `Request failed: ${response.status}` });
          return;
        }
      }

      if (config.submitBehavior.type === 'toast-feedback') {
        dispatch({ type: 'toast', message: config.submitBehavior.message });
      }
    } catch (err) {
      setErrors({ _submit: err instanceof Error ? err.message : 'Unknown error' });
    } finally {
      setIsSubmitting(false);
    }
  }, [config, values, dispatch]);

  return { fields: config.fields, values, errors, handleChange, handleSubmit, isSubmitting };
}
