/**
 * Chat Agent Types - Shared between client and server
 */

import type { ConversationMessage } from '../rag/rag.types';
import type { ExecutionStep } from '../../shared/types/agent.types';

/**
 * Parameters for chat orchestration
 */
export interface ChatHandlerParams {
  messages: ConversationMessage[];
  query?: string;
  knowledge_sources?: string[];
}

/**
 * Result from chat orchestration
 */
export interface ChatHandlerResult {
  response: string;
  timestamp: string;
  execution_steps?: ExecutionStep[];
  total_duration?: number;
}

/**
 * Chat agent metadata
 */
export interface ChatMetadata {
  id: 'chat';
  name: string;
  description: string;
  category: 'chat';
  route: '/agents/chat';
  knowledge_sources: string[];
  tags: string[];
}
