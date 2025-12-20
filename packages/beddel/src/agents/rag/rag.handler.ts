import 'server-only';

/**
 * RAG Agent Handler - Server-only execution logic
 * Generates natural language answers based on provided context using Gemini
 */

import { generateText } from 'ai';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import type { ExecutionContext } from '../../types/executionContext';
import type { RagHandlerParams, RagHandlerResult, ConversationMessage } from './rag.types';

const GEMINI_RAG_MODEL = 'models/gemini-2.0-flash-exp';

/**
 * Execute RAG answer generation
 */
export async function executeRagHandler(
  params: RagHandlerParams,
  props: Record<string, string>,
  context: ExecutionContext
): Promise<RagHandlerResult> {
  const apiKey = props?.gemini_api_key?.trim();
  if (!apiKey) {
    throw new Error('Missing required prop: gemini_api_key');
  }

  const query = params.query;
  const ragContext = params.context || params.documents;
  const history = params.history;

  if (!query) {
    throw new Error('Missing required RAG input: query');
  }
  if (!ragContext) {
    throw new Error('Missing required RAG input: context or documents');
  }

  const google = createGoogleGenerativeAI({ apiKey });
  const model = google(GEMINI_RAG_MODEL);

  // Build conversation history context
  const conversationContext = history?.length
    ? `CONVERSATION HISTORY:\n${history.map((m: ConversationMessage) => `${m.role.toUpperCase()}: ${m.content}`).join('\n')}\n\n`
    : '';

  const prompt = `You are a helpful and expert assistant for the Beddel Protocol.

${conversationContext}CONTEXT INFORMATION:
${ragContext}

USER QUESTION:
${query}

INSTRUCTIONS:
1. Answer the user's question based on the CONTEXT INFORMATION provided above.
2. Consider the CONVERSATION HISTORY for context continuity if available.
3. If the context does not contain the answer, politely state that you don't have enough information in the documentation to answer.
4. Be concise but comprehensive.

ANSWER:`;

  try {
    context.log(`[RAG] Generating answer for query: "${query.substring(0, 50)}..."`);

    const { text } = await generateText({
      model,
      prompt,
      temperature: 0.3,
    });

    return {
      response: text,
      answer: text,
      timestamp: new Date().toISOString(),
    };

  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    context.log(`[RAG] Error: ${message}`);
    return {
      response: '',
      answer: '',
      timestamp: new Date().toISOString(),
      error: message,
    };
  }
}
