/**
 * Declarative Agent Runtime - YAML Interpreter for Beddel Declarative Protocol
 * Safely interprets declarative YAML agent definitions without dynamic code execution
 *
 * Phase 3 Refactored: Delegates to individual agent handlers via workflowExecutor
 */

import 'server-only';

import * as yaml from 'js-yaml';
import { type ZodTypeAny } from 'zod';
import { ExecutionContext } from '../types/executionContext';
import { agentRegistry } from '../agents/registry';
import {
  DeclarativeSchemaCompiler,
  DeclarativeSchemaValidationError,
  type DeclarativeSchemaPhase,
} from './schemaCompiler';

// Import handlers from workflowExecutor
import {
  executeJokeHandler,
  executeTranslationHandler,
  executeImageHandler,
  executeMcpToolHandler,
  executeVectorizeHandler,
  executeChromaDBHandler,
  executeGitMcpHandler,
  executeRagHandler,
  executeChatHandler,
} from './workflowExecutor';

export interface YamlAgentDefinition {
  agent: {
    id: string;
    version: string;
    protocol: string;
  };
  metadata: {
    name: string;
    description: string;
    category: string;
    route?: string;
  };
  schema: {
    input: any;
    output: any;
  };
  logic: {
    variables?: Array<{
      name: string;
      type: string;
      init: string;
    }>;
    workflow: Array<{
      name: string;
      type: string;
      action: {
        type: string;
        output?: Record<string, any>;
        [key: string]: any;
      };
    }>;
  };
  output?: {
    schema?: any;
  };
}

export interface YamlAgentInterpreterOptions {
  yamlContent: string;
  input: Record<string, any>;
  props: Record<string, string>;
  context: ExecutionContext;
}

export type YamlExecutionResult = Record<string, any>;

/**
 * Safe declarative YAML interpreter - no dynamic code execution
 * Delegates execution to individual agent handlers
 */
export class DeclarativeAgentInterpreter {
  private readonly MAX_VARIABLE_SIZE = 1024;
  private readonly MAX_WORKFLOW_STEPS = 100;
  private readonly MAX_OUTPUT_SIZE = 5 * 1024 * 1024;
  private readonly schemaCompiler = new DeclarativeSchemaCompiler();

  /**
   * Interpret declarative YAML agent definition
   */
  public async interpret(
    options: YamlAgentInterpreterOptions
  ): Promise<YamlExecutionResult> {
    const startTime = Date.now();

    try {
      const agent = this.parseYaml(options.yamlContent);
      this.validateAgentDefinition(agent);

      const schemas = this.buildSchemaSet(agent);
      const validatedInput = this.validateAgainstSchema(
        options.input,
        schemas.input,
        'input',
        options.context
      );

      const executionOptions: YamlAgentInterpreterOptions = {
        ...options,
        input: validatedInput,
      };

      const result = await this.executeWorkflow(agent, executionOptions);

      const validatedOutput = this.validateAgainstSchema(
        result,
        schemas.output,
        'output',
        options.context
      );
      this.enforceOutputSize(validatedOutput);

      const executionTime = Date.now() - startTime;
      options.context.log(`Declarative agent executed in ${executionTime}ms`);

      return validatedOutput;
    } catch (error) {
      options.context.log(`Declarative agent execution failed: ${error}`);
      options.context.setError(
        error instanceof Error ? error.message : 'Unknown declarative agent error'
      );
      throw error;
    }
  }

  private parseYaml(yamlContent: string): YamlAgentDefinition {
    try {
      const parsed = yaml.load(yamlContent) as YamlAgentDefinition;

      if (!parsed || typeof parsed !== 'object') {
        throw new Error('Invalid YAML: expected object');
      }

      if (!parsed.agent || !parsed.logic || !parsed.schema) {
        throw new Error('Invalid agent definition: missing required sections');
      }

      return parsed;
    } catch (error) {
      throw new Error(`YAML parsing failed: ${error}`);
    }
  }

  private validateAgentDefinition(agent: YamlAgentDefinition): void {
    if (agent.agent.protocol !== 'beddel-declarative-protocol/v2.0') {
      throw new Error(`Unsupported protocol: ${agent.agent.protocol}`);
    }

    if (!agent.schema.input || !agent.schema.output) {
      throw new Error('Invalid schema: missing input or output definition');
    }

    if (!Array.isArray(agent.logic.workflow) || agent.logic.workflow.length === 0) {
      throw new Error('Invalid workflow: must be non-empty array');
    }

    if (agent.logic.workflow.length > this.MAX_WORKFLOW_STEPS) {
      throw new Error(`Workflow too complex: max ${this.MAX_WORKFLOW_STEPS} steps allowed`);
    }
  }

  private buildSchemaSet(agent: YamlAgentDefinition): {
    input: ZodTypeAny;
    output: ZodTypeAny;
  } {
    return {
      input: this.schemaCompiler.compile(agent.schema.input, 'schema.input'),
      output: this.schemaCompiler.compile(agent.schema.output, 'schema.output'),
    };
  }

  private validateAgainstSchema(
    data: unknown,
    schema: ZodTypeAny,
    phase: DeclarativeSchemaPhase,
    context: ExecutionContext
  ): any {
    const validationResult = schema.safeParse(data);
    if (!validationResult.success) {
      const issues = validationResult.error.issues;
      const issueSummary = issues
        .map((issue) => `${issue.path.join('.') || 'root'}: ${issue.message}`)
        .join('; ');
      const label = phase === 'input' ? 'Input' : 'Output';
      const message = `${label} validation failed: ${issueSummary}`;
      context.setError(message);
      throw new DeclarativeSchemaValidationError(message, phase, issues);
    }
    return validationResult.data;
  }

  private enforceOutputSize(output: any): void {
    const outputSize = JSON.stringify(output).length;
    if (outputSize > this.MAX_OUTPUT_SIZE) {
      throw new Error(`Output size exceeds maximum allowed: ${outputSize} > ${this.MAX_OUTPUT_SIZE}`);
    }
  }

  private async executeWorkflow(
    agent: YamlAgentDefinition,
    options: YamlAgentInterpreterOptions
  ): Promise<YamlExecutionResult> {
    const variables = new Map<string, any>();
    let output: any = undefined;

    if (agent.logic.variables) {
      for (const variable of agent.logic.variables) {
        this.validateVariable(variable);
        const value = this.evaluateValue(variable.init, variables);
        variables.set(variable.name, value);
      }
    }

    for (const step of agent.logic.workflow) {
      output = await this.executeWorkflowStep(step, variables, options);
    }

    return output;
  }

  private async executeWorkflowStep(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    options.context.log(`Executing workflow step: ${step.name} (${step.type})`);

    switch (step.type) {
      case 'output-generator':
        return this.executeOutputGenerator(step, variables, options);
      case 'genkit-joke':
        return this.executeGenkitJoke(step, variables, options);
      case 'genkit-translation':
        return this.executeGenkitTranslation(step, variables, options);
      case 'genkit-image':
        return this.executeGenkitImage(step, variables, options);
      case 'custom-action':
        return this.executeCustomAction(step, variables, options);
      case 'mcp-tool':
        return this.executeMcpTool(step, variables, options);
      case 'gemini-vectorize':
        return this.executeGeminiVectorize(step, variables, options);
      case 'chromadb':
        return this.executeChromaDB(step, variables, options);
      case 'gitmcp':
        return this.executeGitMcp(step, variables, options);
      case 'rag':
        return this.executeRag(step, variables, options);
      case 'chat':
        return this.executeChat(step, variables, options);
      case 'builtin-agent':
        return this.executeBuiltinAgent(step, variables, options);
      default:
        throw new Error(`Unsupported workflow step type: ${step.type}`);
    }
  }

  // ============================================================================
  // Output Generator (kept inline - orchestration logic)
  // ============================================================================

  private executeOutputGenerator(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): any {
    if (step.action?.type !== 'generate' || !step.action.output) {
      throw new Error('Invalid output generator configuration');
    }

    const output: any = {};

    options.context.log(
      `Output generator: Available variables: ${Array.from(variables.keys()).join(', ')}`
    );

    for (const [key, valueExpr] of Object.entries(step.action.output)) {
      if (typeof valueExpr === 'string' && valueExpr.startsWith('$')) {
        try {
          const reference = valueExpr.substring(1);
          const resolved = this.resolveReference(reference, variables);
          output[key] = resolved;
        } catch (error) {
          options.context.log(
            `Output generator: Failed to resolve ${valueExpr}: ${error instanceof Error ? error.message : String(error)}`
          );
          throw error;
        }
      } else {
        output[key] = valueExpr;
      }
    }

    return output;
  }

  // ============================================================================
  // Delegated Handlers - Using extracted agent handlers
  // ============================================================================

  private async executeGenkitJoke(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const prompt =
      typeof step.action?.prompt === 'string' && step.action.prompt.trim().length
        ? step.action.prompt.trim()
        : 'Tell a short and original joke that works for any audience.';
    const temperature =
      typeof step.action?.temperature === 'number' ? step.action.temperature : 0.8;
    const maxTokens =
      typeof step.action?.maxTokens === 'number' ? step.action.maxTokens : undefined;
    const resultVar =
      typeof step.action?.result === 'string' && step.action.result.length > 0
        ? step.action.result
        : 'jokerResult';

    const result = await executeJokeHandler(
      { prompt, temperature, maxTokens },
      options.props,
      options.context
    );

    variables.set(resultVar, result);
    return result;
  }

  private async executeGenkitTranslation(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const text = options.input?.texto || options.input?.text;
    const sourceLanguage = options.input?.idioma_origem || options.input?.source_language;
    const targetLanguage = options.input?.idioma_destino || options.input?.target_language;

    const resultVar =
      typeof step.action?.result === 'string' && step.action.result.length > 0
        ? step.action.result
        : 'translationResult';

    const result = await executeTranslationHandler(
      {
        text,
        source_language: sourceLanguage,
        target_language: targetLanguage,
        promptTemplate:
          typeof step.action?.promptTemplate === 'string'
            ? step.action.promptTemplate
            : undefined,
      },
      options.props,
      options.context
    );

    variables.set(resultVar, result);
    return result;
  }

  private async executeGenkitImage(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const description =
      typeof options.input?.descricao === 'string'
        ? options.input.descricao.trim()
        : typeof options.input?.description === 'string'
          ? options.input.description.trim()
          : '';
    const style =
      typeof options.input?.estilo === 'string'
        ? options.input.estilo.trim()
        : typeof options.input?.style === 'string'
          ? options.input.style.trim()
          : '';
    const resolution =
      typeof options.input?.resolucao === 'string'
        ? options.input.resolucao.trim()
        : typeof options.input?.resolution === 'string'
          ? options.input.resolution.trim()
          : '';

    if (!description) {
      throw new Error('Missing required image input: description');
    }
    if (!style) {
      throw new Error('Missing required image input: style');
    }
    if (!resolution) {
      throw new Error('Missing required image input: resolution');
    }

    const promptTemplate =
      typeof step.action?.promptTemplate === 'string' &&
      step.action.promptTemplate.trim().length > 0
        ? step.action.promptTemplate
        : 'Create a detailed image in {{style}} style focusing on: {{description}}';

    const resultVar =
      typeof step.action?.result === 'string' && step.action.result.length > 0
        ? step.action.result
        : 'imageResult';

    const result = await executeImageHandler(
      {
        description,
        style,
        resolution,
        promptTemplate,
      },
      options.props,
      options.context
    );

    variables.set(resultVar, result);
    return result;
  }

  private async executeMcpTool(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const serverUrl = this.resolveInputValue(step.action?.server_url, options.input, variables);
    const toolName = this.resolveInputValue(step.action?.tool_name, options.input, variables);
    const toolArguments =
      this.resolveInputValue(step.action?.tool_arguments, options.input, variables) || {};
    const resultVar = step.action?.result || 'mcpResult';

    const result = await executeMcpToolHandler(
      {
        server_url: serverUrl,
        tool_name: toolName,
        tool_arguments: toolArguments,
      },
      options.props,
      options.context
    );

    variables.set(resultVar, result);
    return result;
  }

  private async executeGeminiVectorize(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const action = step.action?.action || 'embedSingle';
    const resultVar = step.action?.result || 'vectorizeResult';

    let result;
    if (action === 'embedSingle') {
      const text = this.resolveInputValue(step.action?.text, options.input, variables);
      result = await executeVectorizeHandler(
        { action: 'embedSingle', text },
        options.props,
        options.context
      );
    } else if (action === 'embedBatch') {
      const texts = this.resolveInputValue(step.action?.texts, options.input, variables);
      result = await executeVectorizeHandler(
        { action: 'embedBatch', texts },
        options.props,
        options.context
      );
    } else {
      throw new Error(`Unknown vectorize action: ${action}`);
    }

    variables.set(resultVar, result);
    return result;
  }

  private async executeChromaDB(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const action = this.resolveInputValue(step.action?.action, options.input, variables);
    const collectionName = this.resolveInputValue(
      step.action?.collection_name,
      options.input,
      variables
    );
    const resultVar = step.action?.result || 'chromaResult';

    let params: any = { action, collection_name: collectionName };

    if (action === 'hasData') {
      params.min_count =
        this.resolveInputValue(step.action?.min_count, options.input, variables) || 1;
    } else if (action === 'store') {
      params.ids = this.resolveInputValue(step.action?.ids, options.input, variables);
      params.vectors = this.resolveInputValue(step.action?.vectors, options.input, variables);
      params.documents = this.resolveInputValue(step.action?.documents, options.input, variables);
      params.metadatas = this.resolveInputValue(step.action?.metadatas, options.input, variables);
    } else if (action === 'search') {
      params.query_vector = this.resolveInputValue(
        step.action?.query_vector,
        options.input,
        variables
      );
      params.limit =
        this.resolveInputValue(step.action?.limit, options.input, variables) || 5;
    }

    const result = await executeChromaDBHandler(params, options.props, options.context);

    variables.set(resultVar, result);
    return result;
  }

  private async executeGitMcp(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const gitmcpUrl = this.resolveInputValue(step.action?.gitmcp_url, options.input, variables);
    const resultVar = step.action?.result || 'gitmcpResult';

    const result = await executeGitMcpHandler(
      { gitmcp_url: gitmcpUrl },
      options.props,
      options.context
    );

    variables.set(resultVar, result);
    return result;
  }

  private async executeRag(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const query = this.resolveInputValue(step.action?.query, options.input, variables);
    const context =
      this.resolveInputValue(step.action?.context, options.input, variables) ||
      this.resolveInputValue(step.action?.documents, options.input, variables);
    const history = this.resolveInputValue(step.action?.history, options.input, variables);
    const resultVar = step.action?.result || 'ragResult';

    const result = await executeRagHandler(
      { query, context, documents: context, history },
      options.props,
      options.context
    );

    variables.set(resultVar, result);
    return result;
  }

  private async executeChat(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const messages = this.resolveInputValue(step.action?.messages, options.input, variables);
    const query = this.resolveInputValue(step.action?.query, options.input, variables);
    const resultVar = step.action?.result || 'chatResult';

    const result = await executeChatHandler(
      { messages, query },
      options.props,
      options.context
    );

    variables.set(resultVar, result);
    return result;
  }

  // ============================================================================
  // Custom Action & Builtin Agent (orchestration logic)
  // ============================================================================

  private async executeCustomAction(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const functionName = step.action?.function;
    if (!functionName) {
      throw new Error("Missing 'function' in custom-action");
    }

    options.context.log(`Custom action: Looking up function '${functionName}'`);

    const customFunc = agentRegistry.getCustomFunction(functionName);
    if (!customFunc) {
      throw new Error(
        `Custom function '${functionName}' not found in registry. ` +
          `Make sure the corresponding .ts file is in the /agents directory.`
      );
    }

    const args = {
      input: options.input,
      variables: Object.fromEntries(variables),
      action: step.action,
      context: options.context,
    };

    options.context.log(`Custom action: Executing function '${functionName}'`);

    try {
      const result = await customFunc(args);

      if (step.action.result) {
        variables.set(step.action.result, result);
      }

      return result;
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : String(e);
      options.context.log(`Custom action execution failed: ${errorMessage}`);
      options.context.setError(errorMessage);
      throw new Error(`Custom action execution failed: ${errorMessage}`);
    }
  }

  private async executeBuiltinAgent(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const agentName = step.action?.agent;
    const agentInput =
      this.resolveInputValue(step.action?.input, options.input, variables) || options.input;
    const agentProps = step.action?.props || options.props;
    const resultVar = step.action?.result || 'builtinResult';

    if (!agentName) {
      throw new Error('Missing required builtin-agent input: agent');
    }

    options.context.log(`[Builtin Agent] Invoking agent: ${agentName}`);

    try {
      const result = await agentRegistry.executeAgent(
        agentName,
        agentInput,
        agentProps,
        options.context
      );

      variables.set(resultVar, result);
      return result;
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      options.context.log(`[Builtin Agent] Error: ${message}`);
      throw new Error(`Builtin agent '${agentName}' execution failed: ${message}`);
    }
  }

  // ============================================================================
  // Helper Methods
  // ============================================================================

  private resolveInputValue(
    value: any,
    input: Record<string, any>,
    variables: Map<string, any>
  ): any {
    if (value === undefined || value === null) return undefined;

    if (typeof value === 'string' && value.startsWith('$')) {
      const ref = value.substring(1);
      if (ref.startsWith('input.')) {
        const inputKey = ref.substring(6);
        return this.getNestedValue(input, inputKey);
      }
      return this.resolveReference(ref, variables);
    }

    if (typeof value === 'string' && input[value] !== undefined) {
      return input[value];
    }

    return value;
  }

  private getNestedValue(obj: any, path: string): any {
    const parts = path.split('.');
    let current = obj;
    for (const part of parts) {
      if (current == null) return undefined;
      current = current[part];
    }
    return current;
  }

  private evaluateValue(expr: string, variables: Map<string, any>): any {
    if (expr.startsWith('"') && expr.endsWith('"')) {
      if (expr.length - 2 > this.MAX_VARIABLE_SIZE) {
        throw new Error('Variable initialization exceeds maximum size');
      }
      return expr.slice(1, -1);
    }

    if (expr.startsWith("'") && expr.endsWith("'")) {
      if (expr.length - 2 > this.MAX_VARIABLE_SIZE) {
        throw new Error('Variable initialization exceeds maximum size');
      }
      return expr.slice(1, -1);
    }

    if (expr.length > this.MAX_VARIABLE_SIZE) {
      throw new Error('Variable initialization exceeds maximum size');
    }

    if (expr === 'true') return true;
    if (expr === 'false') return false;
    if (expr === 'null') return null;

    if (expr.startsWith('$')) {
      return this.resolveReference(expr.substring(1), variables);
    }

    if (/^-?\d+$/.test(expr)) return parseInt(expr, 10);
    if (/^-?\d+\.\d+$/.test(expr)) return parseFloat(expr);

    throw new Error(`Unsupported value expression: ${expr}`);
  }

  private validateVariable(variable: any): void {
    if (!variable.name || !variable.type) {
      throw new Error('Invalid variable declaration: missing name or type');
    }

    if (!['string', 'number', 'boolean', 'object'].includes(variable.type)) {
      throw new Error(`Unsupported variable type: ${variable.type}`);
    }
  }

  private resolveReference(reference: string, variables: Map<string, any>): any {
    const [varName, ...pathSegments] = reference.split('.');
    let value = variables.get(varName);
    if (value === undefined) {
      throw new Error(`Undefined variable referenced: ${varName}`);
    }

    for (const segment of pathSegments) {
      if (value == null || typeof value !== 'object') {
        throw new Error(
          `Cannot resolve path '${reference}': segment '${segment}' is invalid`
        );
      }
      value = value[segment];
    }

    return value;
  }
}

// Singleton instance
export const declarativeInterpreter = new DeclarativeAgentInterpreter();

export default DeclarativeAgentInterpreter;
