/**
 * StructuredData — renders JSON-LD structured data as a script tag.
 *
 * No hardcoded values — all data comes from props.
 * Supports LocalBusiness, Restaurant, and Event schema.org types.
 */

import type { SectionComponentProps } from '../types';

interface StructuredDataProps extends SectionComponentProps {
  type?: 'LocalBusiness' | 'Restaurant' | 'Event';
  schemaData?: Record<string, unknown>;
}

export function StructuredData({ type, schemaData }: StructuredDataProps) {
  if (!schemaData) return null;

  // Ensure @context and @type are set
  const schema: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': type ?? schemaData['@type'] ?? 'LocalBusiness',
    ...schemaData,
  };

  // XSS protection: escape < characters in JSON output
  const jsonLd = JSON.stringify(schema).replace(/</g, '\\u003c');

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: jsonLd }}
    />
  );
}
