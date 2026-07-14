import { describe, it, expect, vi } from 'vitest';
import type { DocumentQuery } from '@botanarede/schema';
import { QueryNotPublicError } from '@botanarede/schema';
import { resolveDocumentQuery } from './document-binding';
import type { DocumentDataAdapter } from './document-binding';

function makeAdapter(result: Record<string, unknown> | null = null): DocumentDataAdapter {
  return { fetchDocument: vi.fn().mockResolvedValue(result) };
}

const publicQuery: DocumentQuery = {
  type: 'document',
  tableSlug: 'metadata',
  documentId: 'page_contato',
  publicRead: true,
};

const privateQuery: DocumentQuery = {
  type: 'document',
  tableSlug: 'metadata',
  documentId: 'secret_doc',
  publicRead: false,
};

describe('resolveDocumentQuery', () => {
  it('returns the record from adapter for a valid public query', async () => {
    const doc = { phone: '555-1234', address: '123 Main St' };
    const adapter = makeAdapter(doc);
    const result = await resolveDocumentQuery(publicQuery, 'tenant-1', adapter);
    expect(result).toEqual(doc);
    expect(adapter.fetchDocument).toHaveBeenCalledOnce();
  });

  it('returns null when adapter returns null (document not found)', async () => {
    const adapter = makeAdapter(null);
    const result = await resolveDocumentQuery(publicQuery, 'tenant-1', adapter);
    expect(result).toBeNull();
  });

  it('throws QueryNotPublicError for publicRead: false and does NOT call adapter', async () => {
    const adapter = makeAdapter();
    await expect(resolveDocumentQuery(privateQuery, 'tenant-1', adapter)).rejects.toThrow(
      QueryNotPublicError,
    );
    expect(adapter.fetchDocument).not.toHaveBeenCalled();
  });

  it('uses cache on second call — adapter called only once', async () => {
    const doc = { title: 'Cached Doc' };
    const adapter = makeAdapter(doc);
    const cache = new Map<string, Record<string, unknown> | null>();

    const r1 = await resolveDocumentQuery(publicQuery, 'tenant-1', adapter, cache);
    const r2 = await resolveDocumentQuery(publicQuery, 'tenant-1', adapter, cache);

    expect(r1).toEqual(doc);
    expect(r2).toEqual(doc);
    expect(adapter.fetchDocument).toHaveBeenCalledOnce();
  });

  it('caches null result — adapter called only once even for missing doc', async () => {
    const adapter = makeAdapter(null);
    const cache = new Map<string, Record<string, unknown> | null>();

    const r1 = await resolveDocumentQuery(publicQuery, 'tenant-1', adapter, cache);
    const r2 = await resolveDocumentQuery(publicQuery, 'tenant-1', adapter, cache);

    expect(r1).toBeNull();
    expect(r2).toBeNull();
    expect(adapter.fetchDocument).toHaveBeenCalledOnce();
  });
});
