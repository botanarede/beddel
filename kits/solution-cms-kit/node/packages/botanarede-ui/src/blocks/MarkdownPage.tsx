/**
 * MarkdownPage — renders HTML content from a resolved content binding.
 *
 * Receives `data[0].html` from the data binding resolver (type: "content")
 * and renders it inside a prose container.
 *
 * Supports optional `className` prop for styling overrides.
 */

import type { SectionComponentProps } from '../types';

interface MarkdownData {
  html: string;
  rawMarkdown: string;
}

export function MarkdownPage({ data, className }: SectionComponentProps) {
  const content = data?.[0] as MarkdownData | undefined;
  const containerClass = (className as string) ?? 'mx-auto max-w-2xl px-6 py-20';

  if (!content?.html) {
    return (
      <main className={containerClass}>
        <p className="text-muted-foreground">Content not available.</p>
      </main>
    );
  }

  return (
    <main className={containerClass}>
      <div
        className="prose prose-sm max-w-none prose-headings:font-heading prose-a:underline"
        dangerouslySetInnerHTML={{ __html: content.html }}
      />
      <div className="mt-16 border-t pt-6 text-center text-xs text-muted-foreground">
        <a href="/" className="hover:text-foreground">← Voltar ao início</a>
      </div>
    </main>
  );
}
