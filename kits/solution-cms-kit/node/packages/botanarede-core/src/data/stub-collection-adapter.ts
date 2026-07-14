/**
 * Stub collection adapter — returns empty arrays.
 * Used until a real data adapter (Firestore, API) is provided.
 */

import type { CollectionDataAdapter, Row } from './collection-reader';

export class StubCollectionAdapter implements CollectionDataAdapter {
  async fetchRows(): Promise<Row[]> {
    return [];
  }
}
