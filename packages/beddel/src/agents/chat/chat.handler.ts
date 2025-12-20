import 'server-only';

/**
 * Chat Agent Handler - Server-only execution logic
 * Orchestrates RAG pipeline: vectorization, storage, retrieval and answer generation
 */

import type { ExecutionContext } from '../../types/executionContext';
import type { ExecutionStep } from '../../shared/types/agent.types';
import type { ChatHandlerParams, ChatHandlerResult } from './chat.types';
import { executeVectorizeHandler } from '../gemini-vectorize/gemini-vectorize.handler';
import { executeChromaDBHandler } from '../chromadb/chromadb.handler';
import { executeRagHandler } from '../rag/rag.handler';

const KNOWLEDGE_COLLECTION = 'beddel_knowledge';

/**
 * Execute chat orchestration
 */
export async function executeChatHandler(
  params: ChatHandlerParams,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<ChatHandlerResult> {
  const startTime = Date.now();
  const executionSteps: ExecutionStep[] = [];

  // Extract user query from messages
  const messages = params.messages || [];
  const lastUserMessage = [...messages].reverse().find((m) => m.role === 'user');
  const query = params.query || lastUserMessage?.content || '';

  if (!query) {
    throw new Error('No query found in messages or query parameter');
  }

  context.log(`[Chat] Processing query: "${query.substring(0, 50)}..."`);

  try {
    // Step 1: Vectorize user query
    const vectorizeStep: ExecutionStep = {
      agent: 'gemini-vectorize',
      action: 'embedSingle',
      status: 'running',
      startTime: Date.now(),
      phase: 'vectorization',
    };
    executionSteps.push(vectorizeStep);

    const vectorResult = await executeVectorizeHandler(
      { action: 'embedSingle', text: query },
      props,
      context
    );

    vectorizeStep.status = vectorResult.success ? 'success' : 'error';
    vectorizeStep.endTime = Date.now();
    vectorizeStep.duration = vectorizeStep.endTime - vectorizeStep.startTime;

    if (!vectorResult.success || !vectorResult.vector) {
      throw new Error(`Vectorization failed: ${vectorResult.error}`);
    }

    // Step 2: Check if knowledge base has data
    const checkStep: ExecutionStep = {
      agent: 'chromadb',
      action: 'hasData',
      status: 'running',
      startTime: Date.now(),
      phase: 'retrieval',
    };
    executionSteps.push(checkStep);

    const hasDataResult = await executeChromaDBHandler(
      { action: 'hasData', collection_name: KNOWLEDGE_COLLECTION, min_count: 5 },
      props,
      context
    );

    checkStep.status = hasDataResult.success ? 'success' : 'error';
    checkStep.endTime = Date.now();
    checkStep.duration = checkStep.endTime - checkStep.startTime;

    // Step 3: Search knowledge base
    const searchStep: ExecutionStep = {
      agent: 'chromadb',
      action: 'search',
      status: 'running',
      startTime: Date.now(),
      phase: 'retrieval',
    };
    executionSteps.push(searchStep);

    const searchResult = await executeChromaDBHandler(
      {
        action: 'search',
        collection_name: KNOWLEDGE_COLLECTION,
        query_vector: vectorResult.vector,
        limit: 5,
      },
      props,
      context
    );

    searchStep.status = searchResult.success ? 'success' : 'error';
    searchStep.endTime = Date.now();
    searchStep.duration = searchStep.endTime - searchStep.startTime;

    // Step 4: Generate answer using RAG
    const ragStep: ExecutionStep = {
      agent: 'rag',
      action: 'generate',
      status: 'running',
      startTime: Date.now(),
      phase: 'generation',
    };
    executionSteps.push(ragStep);

    const ragResult = await executeRagHandler(
      {
        query,
        documents: searchResult.documents || '',
        history: messages,
      },
      props,
      context
    );

    ragStep.status = ragResult.error ? 'error' : 'success';
    ragStep.endTime = Date.now();
    ragStep.duration = ragStep.endTime - ragStep.startTime;

    if (ragResult.error) {
      ragStep.error = ragResult.error;
    }

    const totalDuration = Date.now() - startTime;

    return {
      response: ragResult.response,
      timestamp: ragResult.timestamp,
      execution_steps: executionSteps,
      total_duration: totalDuration,
    };

  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    context.log(`[Chat] Error: ${message}`);
    context.setError(message);

    return {
      response: `Error processing your request: ${message}`,
      timestamp: new Date().toISOString(),
      execution_steps: executionSteps,
      total_duration: Date.now() - startTime,
    };
  }
}
