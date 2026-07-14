/**
 * Stub document adapter — returns null.
 * Used until a real data adapter (Firestore, API) is provided.
 */

import type { DocumentDataAdapter } from './document-binding';

export class StubDocumentAdapter implements DocumentDataAdapter {
  async fetchDocument(): Promise<null> {
    return null;
  }
}
