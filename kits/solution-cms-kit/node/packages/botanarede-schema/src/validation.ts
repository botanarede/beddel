import { TenantConfigSchema } from './tenant-config';
import type { TenantConfig } from './tenant-config';
import { validateLayoutRefs } from './validate-refs';
import { validateRouteRefs } from './navigation';

// --- Types (Task 1) ---

export type ValidationStage = 'structural' | 'semantic' | 'manifest';

export interface ValidationError {
  stage: ValidationStage;
  path: string;
  message: string;
  severity: 'error' | 'warning';
}

export type ValidationWarning = ValidationError;

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}


// --- Structural validation (Task 2) ---

export function runStructuralValidation(json: unknown): ValidationError[] {
  const result = TenantConfigSchema.safeParse(json);
  if (result.success) return [];

  return result.error.issues.map((issue) => ({
    stage: 'structural' as const,
    path: issue.path.length > 0 ? issue.path.join('.') : '(root)',
    message: issue.message,
    severity: 'error' as const,
  }));
}

// --- Semantic validation (Task 3) ---

export function runSemanticValidation(config: TenantConfig): ValidationError[] {
  const errors: ValidationError[] = [];

  // Layout refs
  const layoutResult = validateLayoutRefs(config);
  for (const err of layoutResult.errors) {
    errors.push({
      stage: 'semantic',
      severity: 'error',
      path: `pages.${err.page}.layoutRef`,
      message: err.message,
    });
  }

  // Route refs
  const pageRoutes: string[] = [];
  for (const page of Object.values(config.pages)) {
    if (!page) continue;
    pageRoutes.push(page.route);
  }
  const routeErrors = validateRouteRefs(config.navigation, pageRoutes);
  for (const err of routeErrors) {
    errors.push({
      stage: 'semantic',
      severity: 'error',
      path: 'navigation',
      message: err.message,
    });
  }

  return errors;
}

// --- Manifest validation (Task 4) ---

export function runManifestValidation(
  config: TenantConfig,
  allowlist: string[],
): ValidationError[] {
  const errors: ValidationError[] = [];
  const allowlistSet = new Set(allowlist);

  // From config.components (top-level component definitions)
  for (const [key, comp] of Object.entries(config.components)) {
    if (!comp) continue;
    if (!allowlistSet.has(comp.type)) {
      errors.push({
        stage: 'manifest',
        severity: 'warning',
        path: `components.${key}.type`,
        message: `Component type "${comp.type}" is not in the component allowlist`,
      });
    }
  }

  // From page sections
  for (const [pageKey, page] of Object.entries(config.pages)) {
    if (!page) continue;
    page.sections.forEach((section, i) => {
      if (!allowlistSet.has(section.type)) {
        errors.push({
          stage: 'manifest',
          severity: 'warning',
          path: `pages.${pageKey}.sections[${i}].type`,
          message: `Component type "${section.type}" is not in the component allowlist`,
        });
      }
    });
  }

  return errors;
}

// --- Orchestrator (Task 5) ---

export function validateTenantConfig(
  json: unknown,
  options?: { allowlist?: string[] },
): ValidationResult {
  const allErrors: ValidationError[] = [];

  const structuralErrors = runStructuralValidation(json);
  allErrors.push(...structuralErrors);

  // Only proceed to semantic/manifest if structural passed
  const parseResult = TenantConfigSchema.safeParse(json);
  if (parseResult.success) {
    allErrors.push(...runSemanticValidation(parseResult.data));
    if (options?.allowlist) {
      allErrors.push(...runManifestValidation(parseResult.data, options.allowlist));
    }
  }

  const errors = allErrors.filter((e) => e.severity === 'error');
  const warnings = allErrors.filter((e) => e.severity === 'warning');
  return { valid: errors.length === 0, errors, warnings };
}
