import { describe, it, expect, vi } from 'vitest';
import type { CollectionQuery } from '@botanarede/schema';
import { QueryNotPublicError } from '@botanarede/schema';
import { resolveCollectionQuery } from './collection-reader';
import type { Row, CollectionDataAdapter } from './collection-reader';

function makeAdapter(rows: Row[] = []): CollectionDataAdapter {
  return { fetchRows: vi.fn().mockResolvedValue(rows) };
}

const publicQuery: CollectionQuery = {
  type: 'collection',
  tableSlug: 'agenda',
  publicRead: true,
};

const privateQuery: CollectionQuery = {
  type: 'collection',
  tableSlug: 'secret',
  publicRead: false,
};

describe('resolveCollectionQuery', () => {
  it('returns rows from adapter for a valid public query', async () => {
    const rows: Row[] = [
      { id: '1', title: 'Event A' },
      { id: '2', title: 'Event B' },
    ];
    const adapter = makeAdapter(rows);
    const result = await resolveCollectionQuery(publicQuery, 'tenant-1', adapter);
    expect(result).toEqual(rows);
    expect(adapter.fetchRows).toHaveBeenCalledOnce();
  });

  it('throws QueryNotPublicError for publicRead: false and does NOT call adapter', async () => {
    const adapter = makeAdapter();
    await expect(resolveCollectionQuery(privateQuery, 'tenant-1', adapter)).rejects.toThrow(
      QueryNotPublicError,
    );
    expect(adapter.fetchRows).not.toHaveBeenCalled();
  });

  it('applies limit when adapter returns more rows', async () => {
    const rows: Row[] = Array.from({ length: 10 }, (_, i) => ({ id: String(i), n: i }));
    const adapter = makeAdapter(rows);
    const query: CollectionQuery = { ...publicQuery, limit: 5 };
    const result = await resolveCollectionQuery(query, 'tenant-1', adapter);
    expect(result).toHaveLength(5);
    expect(result[0]!.id).toBe('0');
    expect(result[4]!.id).toBe('4');
  });

  it('uses cache on second call — adapter called only once', async () => {
    const rows: Row[] = [{ id: '1', title: 'Cached' }];
    const adapter = makeAdapter(rows);
    const cache = new Map<string, Row[]>();

    const r1 = await resolveCollectionQuery(publicQuery, 'tenant-1', adapter, cache);
    const r2 = await resolveCollectionQuery(publicQuery, 'tenant-1', adapter, cache);

    expect(r1).toEqual(rows);
    expect(r2).toEqual(rows);
    expect(adapter.fetchRows).toHaveBeenCalledOnce();
  });

  it('returns [] when adapter throws (graceful degradation)', async () => {
    const adapter: CollectionDataAdapter = {
      fetchRows: vi.fn().mockRejectedValue(new Error('Network error')),
    };
    const result = await resolveCollectionQuery(publicQuery, 'tenant-1', adapter);
    expect(result).toEqual([]);
  });

  it('works without cache parameter', async () => {
    const adapter = makeAdapter([{ id: '1' }]);
    const result = await resolveCollectionQuery(publicQuery, 'tenant-1', adapter);
    expect(result).toHaveLength(1);
  });
});
