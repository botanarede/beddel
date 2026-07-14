import { describe, it, expect } from 'vitest';
import {
  FilterClauseSchema,
  OrderClauseSchema,
  CollectionQuerySchema,
  DocumentQuerySchema,
  DataBindingSchema,
  QueryNotPublicError,
  assertPublicRead,
} from './query';

describe('FilterClauseSchema', () => {
  it('validates a valid filter clause', () => {
    const result = FilterClauseSchema.safeParse({ field: 'status', op: 'eq', value: 'active' });
    expect(result.success).toBe(true);
  });

  it('rejects invalid op', () => {
    const result = FilterClauseSchema.safeParse({ field: 'x', op: 'like', value: 1 });
    expect(result.success).toBe(false);
  });

  it('rejects unknown fields (strict)', () => {
    const result = FilterClauseSchema.safeParse({ field: 'x', op: 'eq', value: 1, extra: true });
    expect(result.success).toBe(false);
  });
});

describe('OrderClauseSchema', () => {
  it('validates asc/desc', () => {
    expect(OrderClauseSchema.safeParse({ field: 'date', direction: 'asc' }).success).toBe(true);
    expect(OrderClauseSchema.safeParse({ field: 'date', direction: 'desc' }).success).toBe(true);
  });

  it('rejects invalid direction', () => {
    expect(OrderClauseSchema.safeParse({ field: 'date', direction: 'up' }).success).toBe(false);
  });
});

describe('CollectionQuerySchema', () => {
  it('validates a full collection query with all optional fields', () => {
    const result = CollectionQuerySchema.safeParse({
      type: 'collection',
      tableSlug: 'agenda',
      filters: [{ field: 'status', op: 'eq', value: 'published' }],
      orderBy: { field: 'date', direction: 'desc' },
      limit: 10,
      publicRead: true,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.tableSlug).toBe('agenda');
      expect(result.data.filters).toHaveLength(1);
      expect(result.data.orderBy?.direction).toBe('desc');
      expect(result.data.limit).toBe(10);
      expect(result.data.publicRead).toBe(true);
    }
  });

  it('validates a minimal collection query (required fields only)', () => {
    const result = CollectionQuerySchema.safeParse({
      type: 'collection',
      tableSlug: 'emails',
      publicRead: false,
    });
    expect(result.success).toBe(true);
  });

  it('rejects missing tableSlug with descriptive error', () => {
    const result = CollectionQuerySchema.safeParse({
      type: 'collection',
      publicRead: true,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path.join('.'));
      expect(paths).toContain('tableSlug');
    }
  });

  it('rejects non-positive limit', () => {
    const result = CollectionQuerySchema.safeParse({
      type: 'collection',
      tableSlug: 'agenda',
      publicRead: true,
      limit: 0,
    });
    expect(result.success).toBe(false);
  });

  it('rejects non-integer limit', () => {
    const result = CollectionQuerySchema.safeParse({
      type: 'collection',
      tableSlug: 'agenda',
      publicRead: true,
      limit: 2.5,
    });
    expect(result.success).toBe(false);
  });
});

describe('DocumentQuerySchema', () => {
  it('validates a valid document query', () => {
    const result = DocumentQuerySchema.safeParse({
      type: 'document',
      tableSlug: 'metadata',
      documentId: 'page_contato',
      publicRead: true,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.documentId).toBe('page_contato');
    }
  });

  it('rejects missing documentId', () => {
    const result = DocumentQuerySchema.safeParse({
      type: 'document',
      tableSlug: 'metadata',
      publicRead: true,
    });
    expect(result.success).toBe(false);
  });

  it('rejects missing tableSlug', () => {
    const result = DocumentQuerySchema.safeParse({
      type: 'document',
      documentId: 'page_contato',
      publicRead: true,
    });
    expect(result.success).toBe(false);
  });
});

describe('DataBindingSchema', () => {
  it('discriminates collection type correctly', () => {
    const result = DataBindingSchema.safeParse({
      type: 'collection',
      tableSlug: 'agenda',
      publicRead: true,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.type).toBe('collection');
    }
  });

  it('discriminates document type correctly', () => {
    const result = DataBindingSchema.safeParse({
      type: 'document',
      tableSlug: 'metadata',
      documentId: 'page_contato',
      publicRead: true,
    });
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.type).toBe('document');
    }
  });

  it('rejects unknown type', () => {
    const result = DataBindingSchema.safeParse({
      type: 'rpc',
      tableSlug: 'x',
      publicRead: true,
    });
    expect(result.success).toBe(false);
  });
});

describe('QueryNotPublicError', () => {
  it('is an instance of Error', () => {
    const err = new QueryNotPublicError('agenda');
    expect(err).toBeInstanceOf(Error);
  });

  it('has correct name property', () => {
    const err = new QueryNotPublicError('agenda');
    expect(err.name).toBe('QueryNotPublicError');
  });

  it('includes table slug in message', () => {
    const err = new QueryNotPublicError('secret_table');
    expect(err.message).toContain('secret_table');
  });
});

describe('assertPublicRead', () => {
  it('does not throw for publicRead: true', () => {
    expect(() =>
      assertPublicRead({ type: 'collection', tableSlug: 'agenda', publicRead: true }),
    ).not.toThrow();
  });

  it('throws QueryNotPublicError for publicRead: false', () => {
    expect(() =>
      assertPublicRead({ type: 'collection', tableSlug: 'secret', publicRead: false }),
    ).toThrow(QueryNotPublicError);
  });
});

describe('index exports', () => {
  it('all schemas are importable from @botanarede/schema', async () => {
    const mod = await import('./index');
    expect(mod.CollectionQuerySchema).toBeDefined();
    expect(mod.DocumentQuerySchema).toBeDefined();
    expect(mod.DataBindingSchema).toBeDefined();
    expect(mod.FilterClauseSchema).toBeDefined();
    expect(mod.OrderClauseSchema).toBeDefined();
    expect(mod.QueryNotPublicError).toBeDefined();
    expect(mod.assertPublicRead).toBeDefined();
  });
});
