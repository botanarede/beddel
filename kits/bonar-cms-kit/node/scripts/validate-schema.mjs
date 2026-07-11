#!/usr/bin/env node
/**
 * validate-schema.mjs — Validates a tenant JSON file against @botanarede/schema TenantConfigSchema.
 *
 * Usage: node scripts/validate-schema.mjs <path-to-tenant.json>
 *
 * Output (stdout): JSON line {"valid": bool, "errors": [...], "warnings": []}
 * Exit 0: Validation ran successfully (result may be valid or invalid)
 * Exit 1: Script/IO error (file not found, bad JSON, import failure)
 */

import { readFileSync } from "node:fs";
import { TenantConfigSchema } from "@botanarede/schema";

const filePath = process.argv[2];

if (!filePath) {
  process.stderr.write("Error: No file path provided. Usage: node validate-schema.mjs <path>\n");
  process.exit(1);
}

let raw;
try {
  raw = readFileSync(filePath, "utf-8");
} catch (err) {
  process.stderr.write(`Error: Cannot read file: ${err.message}\n`);
  process.exit(1);
}

let data;
try {
  data = JSON.parse(raw);
} catch (err) {
  process.stderr.write(`Error: Invalid JSON: ${err.message}\n`);
  process.exit(1);
}

const result = TenantConfigSchema.safeParse(data);

if (result.success) {
  console.log(JSON.stringify({ valid: true, errors: [], warnings: [] }));
} else {
  const errors = result.error.issues.map(
    (issue) => `${issue.path.join(".")}: ${issue.message}`
  );
  console.log(JSON.stringify({ valid: false, errors, warnings: [] }));
}
