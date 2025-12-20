import 'server-only';

/**
 * ChromaDB Agent Handler - Server-only execution logic
 * Vector storage and retrieval using ChromaDB
 */

import type { ExecutionContext } from '../../types/executionContext';
import type { ChromaDBHandlerParams, ChromaDBHandlerResult, ChromaDBSearchResult } from './chromadb.types';

// ChromaDB imports (lazy loaded)
let chromaClient: any = null;

/**
 * Execute ChromaDB operations
 */
export async function executeChromaDBHandler(
  params: ChromaDBHandlerParams,
  _props: Record<string, string>,
  context: ExecutionContext
): Promise<ChromaDBHandlerResult> {
  const action = params.action;
  const collectionName = params.collection_name;

  if (!collectionName) {
    throw new Error('Missing required ChromaDB input: collection_name');
  }

  try {
    // Lazy load ChromaDB
    if (!chromaClient) {
      const chromaModule = await import('chromadb');

      if (process.env.CHROMADB_API_KEY) {
        context.log('[ChromaDB] Initializing CloudClient...');
        chromaClient = new chromaModule.CloudClient({
          apiKey: process.env.CHROMADB_API_KEY,
          tenant: process.env.CHROMADB_TENANT || 'default_tenant',
          database: process.env.CHROMADB_DATABASE || 'dev',
        });
      } else {
        context.log('[ChromaDB] Initializing Local ChromaClient...');
        chromaClient = new chromaModule.ChromaClient({
          path: process.env.CHROMADB_URL || 'http://localhost:8000',
        });
      }
    }

    if (action === 'hasData') {
      const minCount = params.min_count || 1;
      context.log(`[ChromaDB] Checking data for collection: ${collectionName}`);

      try {
        const collection = await chromaClient.getCollection({
          name: collectionName,
          embeddingFunction: undefined,
        });
        const count = await collection.count();
        const hasEnoughData = count >= minCount;

        return { success: true, has_data: hasEnoughData, count };
      } catch {
        return { success: true, has_data: false, count: 0 };
      }

    } else if (action === 'store') {
      const ids = params.ids;
      const vectors = params.vectors;
      const documents = params.documents;
      const metadatas = params.metadatas;

      context.log(`[ChromaDB] Storing ${ids?.length || 0} items in ${collectionName}...`);

      const collection = await chromaClient.getOrCreateCollection({
        name: collectionName,
        embeddingFunction: undefined,
      });

      await collection.add({
        ids,
        embeddings: vectors,
        documents,
        metadatas,
      });

      return { success: true, stored_count: ids?.length || 0 };

    } else if (action === 'search') {
      const queryVector = params.query_vector;
      const limit = params.limit || 5;

      context.log(`[ChromaDB] Searching ${collectionName}...`);

      const collection = await chromaClient.getCollection({
        name: collectionName,
        embeddingFunction: undefined,
      });

      const results = await collection.query({
        queryEmbeddings: [queryVector],
        nResults: limit,
      });

      const flatResults: ChromaDBSearchResult[] = (results.documents[0] || []).map(
        (doc: string | null, idx: number) => ({
          text: doc,
          metadata: results.metadatas[0]?.[idx] || null,
          distance: results.distances?.[0]?.[idx] || null,
        })
      );

      const documentsString = flatResults.map((r) => r.text).join('\n\n---\n\n');

      return { success: true, results: flatResults, documents: documentsString };

    } else {
      throw new Error(`Unknown ChromaDB action: ${action}`);
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    context.log(`[ChromaDB] Error: ${message}`);
    return { success: false, error: message };
  }
}
