/**
 * Declarative Agent Runtime - YAML Interpreter for Beddel Declarative Protocol
 * Safely interprets declarative YAML agent definitions without dynamic code execution
 */

import * as yaml from "js-yaml";
import { experimental_generateImage, generateText, embed, embedMany } from "ai";
import { createGoogleGenerativeAI, google } from "@ai-sdk/google";
import { type ZodTypeAny } from "zod";
import { ExecutionContext } from "../types/executionContext";
import { agentRegistry } from "../agents/agentRegistry";
import {
  DeclarativeSchemaCompiler,
  DeclarativeSchemaValidationError,
  type DeclarativeSchemaPhase,
} from "./schemaCompiler";

// MCP imports (lazy loaded to avoid issues if not installed)
let mcpClient: any = null;
let mcpSSETransport: any = null;

// ChromaDB imports (lazy loaded)
let chromaClient: any = null;

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
 */
export class DeclarativeAgentInterpreter {
  private readonly MAX_VARIABLE_SIZE = 1024; // 1KB max variable size
  private readonly MAX_WORKFLOW_STEPS = 100; // Prevent infinite loops
  private readonly MAX_OUTPUT_SIZE = 5 * 1024 * 1024; // 5MB max output to accommodate image payloads
  private readonly GEMINI_MODEL = "models/gemini-2.5-flash";
  private readonly GEMINI_RAG_MODEL = "models/gemini-2.0-flash-exp";
  private readonly GEMINI_IMAGE_MODEL = "imagen-4.0-fast-generate-001";
  private readonly GEMINI_EMBEDDING_MODEL = "text-embedding-004";
  private readonly SUPPORTED_TRANSLATION_LANGUAGES = ["pt", "en", "es", "fr"];
  private readonly schemaCompiler = new DeclarativeSchemaCompiler();

  /**
   * Interpret declarative YAML agent definition
   */
  public async interpret(
    options: YamlAgentInterpreterOptions
  ): Promise<YamlExecutionResult> {
    const startTime = Date.now();

    try {
      // Parse and validate YAML
      const agent = this.parseYaml(options.yamlContent);
      this.validateAgentDefinition(agent);

      // Compile schemas and validate input up front
      const schemas = this.buildSchemaSet(agent);
      const validatedInput = this.validateAgainstSchema(
        options.input,
        schemas.input,
        "input",
        options.context
      );

      const executionOptions: YamlAgentInterpreterOptions = {
        ...options,
        input: validatedInput,
      };

      // Execute declarative logic
      const result = await this.executeWorkflow(agent, executionOptions);

      // Validate output
      const validatedOutput = this.validateAgainstSchema(
        result,
        schemas.output,
        "output",
        options.context
      );
      this.enforceOutputSize(validatedOutput);

      const executionTime = Date.now() - startTime;
      options.context.log(`Declarative agent executed in ${executionTime}ms`);

      return validatedOutput;
    } catch (error) {
      const executionTime = Date.now() - startTime;
      options.context.log(`Declarative agent execution failed: ${error}`);
      options.context.setError(
        error instanceof Error
          ? error.message
          : "Unknown declarative agent error"
      );
      throw error;
    }
  }

  /**
   * Parse and validate YAML content
   */
  private parseYaml(yamlContent: string): YamlAgentDefinition {
    try {
      const parsed = yaml.load(yamlContent) as YamlAgentDefinition;

      if (!parsed || typeof parsed !== "object") {
        throw new Error("Invalid YAML: expected object");
      }

      if (!parsed.agent || !parsed.logic || !parsed.schema) {
        throw new Error("Invalid agent definition: missing required sections");
      }

      return parsed;
    } catch (error) {
      throw new Error(`YAML parsing failed: ${error}`);
    }
  }

  /**
   * Validate agent definition structure
   */
  private validateAgentDefinition(agent: YamlAgentDefinition): void {
    // Validate protocol version
    if (agent.agent.protocol !== "beddel-declarative-protocol/v2.0") {
      throw new Error(`Unsupported protocol: ${agent.agent.protocol}`);
    }

    // Validate schema
    if (!agent.schema.input || !agent.schema.output) {
      throw new Error("Invalid schema: missing input or output definition");
    }

    // Validate workflow
    if (
      !Array.isArray(agent.logic.workflow) ||
      agent.logic.workflow.length === 0
    ) {
      throw new Error("Invalid workflow: must be non-empty array");
    }

    if (agent.logic.workflow.length > this.MAX_WORKFLOW_STEPS) {
      throw new Error(
        `Workflow too complex: max ${this.MAX_WORKFLOW_STEPS} steps allowed`
      );
    }
  }

  private buildSchemaSet(agent: YamlAgentDefinition): {
    input: ZodTypeAny;
    output: ZodTypeAny;
  } {
    return {
      input: this.schemaCompiler.compile(agent.schema.input, "schema.input"),
      output: this.schemaCompiler.compile(agent.schema.output, "schema.output"),
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
        .map((issue) => `${issue.path.join(".") || "root"}: ${issue.message}`)
        .join("; ");
      const label = phase === "input" ? "Input" : "Output";
      const message = `${label} validation failed: ${issueSummary}`;
      context.setError(message);
      throw new DeclarativeSchemaValidationError(message, phase, issues);
    }

    return validationResult.data;
  }

  private enforceOutputSize(output: any): void {
    const outputSize = JSON.stringify(output).length;
    if (outputSize > this.MAX_OUTPUT_SIZE) {
      throw new Error(
        `Output size exceeds maximum allowed: ${outputSize} > ${this.MAX_OUTPUT_SIZE}`
      );
    }
  }

  /**
   * Execute declarative workflow
   */
  private async executeWorkflow(
    agent: YamlAgentDefinition,
    options: YamlAgentInterpreterOptions
  ): Promise<YamlExecutionResult> {
    const variables = new Map<string, any>();
    let output: any = undefined;

    // Initialize variables
    if (agent.logic.variables) {
      for (const variable of agent.logic.variables) {
        this.validateVariable(variable);
        const value = this.evaluateValue(variable.init, variables);
        variables.set(variable.name, value);
      }
    }

    // Execute workflow steps
    for (const step of agent.logic.workflow) {
      output = await this.executeWorkflowStep(step, variables, options);
    }

    return output;
  }

  /**
   * Execute single workflow step
   */
  private async executeWorkflowStep(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    options.context.log(`Executing workflow step: ${step.name} (${step.type})`);

    switch (step.type) {
      case "output-generator":
        return this.executeOutputGenerator(step, variables, options);
      case "genkit-joke":
        return this.executeGenkitJoke(step, variables, options);
      case "genkit-translation":
        return this.executeGenkitTranslation(step, variables, options);
      case "genkit-image":
        return this.executeGenkitImage(step, variables, options);
      case "custom-action":
        return this.executeCustomAction(step, variables, options);
      // New native workflow step types for builtin agents
      case "mcp-tool":
        return this.executeMcpTool(step, variables, options);
      case "gemini-vectorize":
        return this.executeGeminiVectorize(step, variables, options);
      case "chromadb":
        return this.executeChromaDB(step, variables, options);
      case "gitmcp":
        return this.executeGitMcp(step, variables, options);
      case "rag":
        return this.executeRag(step, variables, options);
      case "builtin-agent":
        return this.executeBuiltinAgent(step, variables, options);
      default:
        throw new Error(`Unsupported workflow step type: ${step.type}`);
    }
  }

  /**
   * Execute output generator step
   */
  private executeOutputGenerator(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): any {
    if (step.action?.type !== "generate" || !step.action.output) {
      throw new Error("Invalid output generator configuration");
    }

    // Build output object
    const output: any = {};

    // Debug: Log available variables
    options.context.log(
      `Output generator: Available variables: ${Array.from(variables.keys()).join(", ")}`
    );

    for (const [key, valueExpr] of Object.entries(step.action.output)) {
      if (typeof valueExpr === "string" && valueExpr.startsWith("$")) {
        try {
          const reference = valueExpr.substring(1);
          options.context.log(
            `Output generator: Resolving reference ${valueExpr} -> ${reference}`
          );
          const resolved = this.resolveReference(reference, variables);
          output[key] = resolved;
          options.context.log(
            `Output generator: Resolved ${key} = ${typeof resolved === "string" ? resolved.substring(0, 50) + "..." : JSON.stringify(resolved).substring(0, 100)}`
          );
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

    options.context.log(
      `Output generator: Final output keys: ${Object.keys(output).join(", ")}`
    );

    return output;
  }

  /**
   * Execute Gemini Flash text helper for the joke agent
   */
  private async executeGenkitJoke(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const prompt =
      typeof step.action?.prompt === "string" && step.action.prompt.trim().length
        ? step.action.prompt.trim()
        : "Conte uma piada curta e original em português.";
    const temperature =
      typeof step.action?.temperature === "number"
        ? step.action.temperature
        : 0.8;
    const maxTokens =
      typeof step.action?.maxTokens === "number"
        ? step.action.maxTokens
        : undefined;
    const resultVar =
      typeof step.action?.result === "string" && step.action.result.length > 0
        ? step.action.result
        : "jokerResult";

    const joke = await this.callGeminiFlashText(
      { prompt, temperature, maxTokens },
      options.props,
      options.context
    );

    variables.set(resultVar, joke);
    return joke;
  }

  /**
   * Execute translation step backed by Gemini Flash
   */
  private async executeGenkitTranslation(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const texto = options.input?.texto;
    const idiomaOrigem = options.input?.idioma_origem;
    const idiomaDestino = options.input?.idioma_destino;

    const resultVar =
      typeof step.action?.result === "string" && step.action.result.length > 0
        ? step.action.result
        : "translationResult";

    const translation = await this.callGeminiFlashTranslation(
      {
        texto,
        idioma_origem: idiomaOrigem,
        idioma_destino: idiomaDestino,
        promptTemplate:
          typeof step.action?.promptTemplate === "string"
            ? step.action.promptTemplate
            : undefined,
      },
      options.props,
      options.context
    );

    variables.set(resultVar, translation);
    return translation;
  }

  /**
   * Execute image generation step backed by Gemini Flash
   */
  private async executeGenkitImage(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const descricao =
      typeof options.input?.descricao === "string"
        ? options.input.descricao.trim()
        : "";
    const estilo =
      typeof options.input?.estilo === "string"
        ? options.input.estilo.trim()
        : "";
    const resolucaoInput =
      typeof options.input?.resolucao === "string"
        ? options.input.resolucao.trim()
        : "";

    if (!descricao) {
      throw new Error("Missing required image input: descricao");
    }
    if (!estilo) {
      throw new Error("Missing required image input: estilo");
    }
    if (!resolucaoInput) {
      throw new Error("Missing required image input: resolucao");
    }

    const promptTemplate =
      typeof step.action?.promptTemplate === "string" &&
        step.action.promptTemplate.trim().length > 0
        ? step.action.promptTemplate
        : "Gere uma imagem detalhada no estilo {{estilo}} baseada na descrição: {{descricao}}";

    const prompt = promptTemplate
      .replace(/{{descricao}}/g, descricao)
      .replace(/{{estilo}}/g, estilo)
      .trim();

    const resultVar =
      typeof step.action?.result === "string" && step.action.result.length > 0
        ? step.action.result
        : "imageResult";

    const imageResult = await this.callGeminiFlashImage(
      {
        prompt,
        estilo,
        resolucao: resolucaoInput,
      },
      options.props,
      options.context
    );

    variables.set(resultVar, imageResult);
    options.context.log(
      `Image generator: Saved result in variable '${resultVar}' with keys: ${Object.keys(imageResult).join(", ")}`
    );
    options.context.log(
      `Image generator: imageResult.image_url exists: ${!!imageResult?.image_url}`
    );
    return imageResult;
  }

  /**
   * Execute custom action backed by TypeScript implementation
   */
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

    // Retrieve Code Implementation
    const customFunc = agentRegistry.getCustomFunction(functionName);
    if (!customFunc) {
      throw new Error(
        `Custom function '${functionName}' not found in registry. ` +
        `Make sure the corresponding .ts file is in the /agents directory.`
      );
    }

    // Prepare Arguments
    const args = {
      input: options.input,
      variables: Object.fromEntries(variables),
      action: step.action,
      context: options.context,
    };

    options.context.log(`Custom action: Executing function '${functionName}'`);

    // Execute Code
    try {
      const result = await customFunc(args);

      // Save Result
      if (step.action.result) {
        variables.set(step.action.result, result);
        options.context.log(
          `Custom action: Saved result to variable '${step.action.result}'`
        );
      }

      return result;
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : String(e);
      options.context.log(`Custom action execution failed: ${errorMessage}`);
      options.context.setError(errorMessage);
      throw new Error(`Custom action execution failed: ${errorMessage}`);
    }
  }

  /**
   * Execute MCP Tool step - connects to MCP server and invokes tools
   */
  private async executeMcpTool(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const serverUrl = this.resolveInputValue(step.action?.server_url, options.input, variables);
    const toolName = this.resolveInputValue(step.action?.tool_name, options.input, variables);
    const toolArguments = this.resolveInputValue(step.action?.tool_arguments, options.input, variables) || {};
    const resultVar = step.action?.result || "mcpResult";

    if (!serverUrl) {
      throw new Error("Missing required MCP input: server_url");
    }
    if (!toolName) {
      throw new Error("Missing required MCP input: tool_name");
    }

    options.context.log(`[MCP Tool] Connecting to ${serverUrl}...`);
    options.context.log(`[MCP Tool] Tool: ${toolName}`);

    try {
      // Lazy load MCP SDK
      if (!mcpClient) {
        const { Client } = await import("@modelcontextprotocol/sdk/client/index.js");
        const { SSEClientTransport } = await import("@modelcontextprotocol/sdk/client/sse.js");
        mcpClient = Client;
        mcpSSETransport = SSEClientTransport;
        
        // Setup EventSource for Node.js
        const eventsourceModule = await import("eventsource");
        const EventSourceClass = eventsourceModule.default || eventsourceModule;
        if (!(global as any).EventSource) {
          (global as any).EventSource = EventSourceClass;
        }
      }

      const transport = new mcpSSETransport(new URL(serverUrl));
      const client = new mcpClient(
        { name: "beddel-mcp-client", version: "1.0.0" },
        { capabilities: {} }
      );

      await client.connect(transport);
      options.context.log("[MCP Tool] Connected!");

      // List available tools
      const tools = await client.listTools();
      const availableToolNames = tools.tools.map((t: any) => t.name);
      options.context.log(`[MCP Tool] Available tools: ${availableToolNames.join(", ")}`);

      // Handle list_tools special case
      if (toolName === "list_tools") {
        await client.close();
        const result = {
          success: true,
          data: JSON.stringify(tools.tools),
          toolNames: availableToolNames
        };
        variables.set(resultVar, result);
        return result;
      }

      // Validate tool exists
      if (!availableToolNames.includes(toolName)) {
        await client.close();
        const result = {
          success: false,
          error: `Tool '${toolName}' not found. Available tools: ${availableToolNames.join(", ")}`,
          data: null
        };
        variables.set(resultVar, result);
        return result;
      }

      // Call the tool with timeout
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error("MCP Tool Timeout (30s)")), 30000)
      );

      const callPromise = client.callTool({
        name: toolName,
        arguments: toolArguments,
      });

      const callResult: any = await Promise.race([callPromise, timeoutPromise]);
      await client.close();

      // Parse result content
      const textContent = callResult.content
        .filter((c: any) => c.type === "text")
        .map((c: any) => c.text)
        .join("\n") || "No text content returned";

      const result = { success: true, data: textContent };
      variables.set(resultVar, result);
      return result;

    } catch (error: any) {
      options.context.log(`[MCP Tool] Error: ${error.message}`);
      const result = { success: false, error: error.message, data: null };
      variables.set(resultVar, result);
      return result;
    }
  }

  /**
   * Execute Gemini Vectorize step - generates embeddings using Gemini
   */
  private async executeGeminiVectorize(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const action = step.action?.action || "embedSingle";
    const resultVar = step.action?.result || "vectorizeResult";

    this.ensureGeminiApiKey(options.props);

    try {
      if (action === "embedSingle") {
        const text = this.resolveInputValue(step.action?.text, options.input, variables);
        if (!text) {
          throw new Error("Text input is required for embedSingle");
        }

        options.context.log(`[Gemini Vectorize] Embedding single text (${text.length} chars)...`);

        const { embedding } = await embed({
          model: google.textEmbeddingModel(this.GEMINI_EMBEDDING_MODEL),
          value: text,
        });

        const result = { success: true, vector: embedding };
        variables.set(resultVar, result);
        return result;

      } else if (action === "embedBatch") {
        const texts = this.resolveInputValue(step.action?.texts, options.input, variables);
        if (!texts || !Array.isArray(texts)) {
          throw new Error("Texts array input is required for embedBatch");
        }

        options.context.log(`[Gemini Vectorize] Embedding batch of ${texts.length} texts...`);

        const { embeddings } = await embedMany({
          model: google.textEmbeddingModel(this.GEMINI_EMBEDDING_MODEL),
          values: texts,
        });

        const result = { success: true, vectors: embeddings };
        variables.set(resultVar, result);
        return result;

      } else {
        throw new Error(`Unknown vectorize action: ${action}`);
      }
    } catch (error: any) {
      options.context.log(`[Gemini Vectorize] Error: ${error.message}`);
      const result = { success: false, error: error.message };
      variables.set(resultVar, result);
      return result;
    }
  }

  /**
   * Execute ChromaDB step - vector storage and retrieval
   */
  private async executeChromaDB(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const action = this.resolveInputValue(step.action?.action, options.input, variables);
    const collectionName = this.resolveInputValue(step.action?.collection_name, options.input, variables);
    const resultVar = step.action?.result || "chromaResult";

    if (!collectionName) {
      throw new Error("Missing required ChromaDB input: collection_name");
    }

    try {
      // Lazy load ChromaDB
      if (!chromaClient) {
        const chromaModule = await import("chromadb");
        
        if (process.env.CHROMADB_API_KEY) {
          options.context.log("[ChromaDB] Initializing CloudClient...");
          chromaClient = new chromaModule.CloudClient({
            apiKey: process.env.CHROMADB_API_KEY,
            tenant: process.env.CHROMADB_TENANT || "default_tenant",
            database: process.env.CHROMADB_DATABASE || "dev",
          });
        } else {
          options.context.log("[ChromaDB] Initializing Local ChromaClient...");
          chromaClient = new chromaModule.ChromaClient({
            path: process.env.CHROMADB_URL || "http://localhost:8000"
          });
        }
      }

      if (action === "hasData") {
        const minCount = this.resolveInputValue(step.action?.min_count, options.input, variables) || 1;
        options.context.log(`[ChromaDB] Checking data for collection: ${collectionName}`);

        try {
          const collection = await chromaClient.getCollection({
            name: collectionName,
            embeddingFunction: undefined
          });
          const count = await collection.count();
          const hasEnoughData = count >= minCount;

          const result = { success: true, has_data: hasEnoughData, count };
          variables.set(resultVar, result);
          return result;
        } catch (e) {
          const result = { success: true, has_data: false, count: 0 };
          variables.set(resultVar, result);
          return result;
        }

      } else if (action === "store") {
        const ids = this.resolveInputValue(step.action?.ids, options.input, variables);
        const vectors = this.resolveInputValue(step.action?.vectors, options.input, variables);
        const documents = this.resolveInputValue(step.action?.documents, options.input, variables);
        const metadatas = this.resolveInputValue(step.action?.metadatas, options.input, variables);

        options.context.log(`[ChromaDB] Storing ${ids?.length || 0} items in ${collectionName}...`);

        const collection = await chromaClient.getOrCreateCollection({
          name: collectionName,
          embeddingFunction: undefined
        });

        await collection.add({
          ids,
          embeddings: vectors,
          documents,
          metadatas
        });

        const result = { success: true, stored_count: ids?.length || 0 };
        variables.set(resultVar, result);
        return result;

      } else if (action === "search") {
        const queryVector = this.resolveInputValue(step.action?.query_vector, options.input, variables);
        const limit = this.resolveInputValue(step.action?.limit, options.input, variables) || 5;

        options.context.log(`[ChromaDB] Searching ${collectionName}...`);

        const collection = await chromaClient.getCollection({
          name: collectionName,
          embeddingFunction: undefined
        });

        const results = await collection.query({
          queryEmbeddings: [queryVector],
          nResults: limit
        });

        const flatResults = (results.documents[0] || []).map((doc: string | null, idx: number) => ({
          text: doc,
          metadata: results.metadatas[0]?.[idx],
          distance: results.distances?.[0]?.[idx]
        }));

        const documentsString = flatResults.map((r: { text: string | null }) => r.text).join("\n\n---\n\n");

        const result = { success: true, results: flatResults, documents: documentsString };
        variables.set(resultVar, result);
        return result;

      } else {
        throw new Error(`Unknown ChromaDB action: ${action}`);
      }
    } catch (error: any) {
      options.context.log(`[ChromaDB] Error: ${error.message}`);
      const result = { success: false, error: error.message };
      variables.set(resultVar, result);
      return result;
    }
  }

  /**
   * Execute GitMCP step - fetches documentation from GitHub repos via GitMCP
   */
  private async executeGitMcp(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const gitmcpUrl = this.resolveInputValue(step.action?.gitmcp_url, options.input, variables);
    const resultVar = step.action?.result || "gitmcpResult";

    if (!gitmcpUrl) {
      throw new Error("Missing required GitMCP input: gitmcp_url");
    }

    options.context.log(`[GitMCP] Fetching content from ${gitmcpUrl}...`);

    try {
      const sseUrl = `${gitmcpUrl}/sse`;

      // Use MCP tool to list available tools
      const listStep = {
        action: {
          server_url: sseUrl,
          tool_name: "list_tools",
          tool_arguments: {},
          result: "_gitmcp_tools"
        }
      };
      await this.executeMcpTool(listStep, variables, options);
      const toolListResult = variables.get("_gitmcp_tools");

      let selectedToolName = "";
      let selectedToolArgs: any = {};

      if (toolListResult?.success && toolListResult?.toolNames) {
        const availableTools = toolListResult.toolNames as string[];
        options.context.log(`[GitMCP] Discovered tools: ${availableTools.join(", ")}`);

        // Heuristic tool selection
        if (availableTools.includes("fetch_beddel_alpha_documentation")) {
          selectedToolName = "fetch_beddel_alpha_documentation";
          selectedToolArgs = { path: "/" };
        } else if (availableTools.includes("read_file")) {
          selectedToolName = "read_file";
          selectedToolArgs = { path: "README.md" };
        } else if (availableTools.includes("fetch_generic_url_content")) {
          selectedToolName = "fetch_generic_url_content";
          selectedToolArgs = { url: gitmcpUrl };
        } else {
          selectedToolName = availableTools.find(t => t !== "list_tools" && !t.includes("search")) || availableTools[0];
          selectedToolArgs = { path: "/" };
        }
      } else {
        selectedToolName = "fetch_beddel_alpha_documentation";
        selectedToolArgs = { path: "/" };
      }

      options.context.log(`[GitMCP] Selected tool: ${selectedToolName}`);

      // Fetch content
      const fetchStep = {
        action: {
          server_url: sseUrl,
          tool_name: selectedToolName,
          tool_arguments: selectedToolArgs,
          result: "_gitmcp_content"
        }
      };
      await this.executeMcpTool(fetchStep, variables, options);
      const mcpResult = variables.get("_gitmcp_content");

      if (!mcpResult?.success) {
        throw new Error(`Failed to fetch docs via MCP: ${mcpResult?.error}`);
      }

      const textContent = mcpResult.data;
      if (!textContent) {
        throw new Error("No content returned from MCP tool");
      }

      // Chunking
      const chunks = this.splitIntoChunks(textContent, 800);
      options.context.log(`[GitMCP] Content split into ${chunks.length} chunks`);

      const result = { success: true, chunks, source: gitmcpUrl };
      variables.set(resultVar, result);
      return result;

    } catch (error: any) {
      options.context.log(`[GitMCP] Error: ${error.message}`);
      const result = { success: false, chunks: [], error: error.message };
      variables.set(resultVar, result);
      return result;
    }
  }

  /**
   * Execute RAG step - generates answers based on context using Gemini
   */
  private async executeRag(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const query = this.resolveInputValue(step.action?.query, options.input, variables);
    const context = this.resolveInputValue(step.action?.context, options.input, variables) 
                 || this.resolveInputValue(step.action?.documents, options.input, variables);
    const history = this.resolveInputValue(step.action?.history, options.input, variables);
    const resultVar = step.action?.result || "ragResult";

    if (!query) {
      throw new Error("Missing required RAG input: query");
    }
    if (!context) {
      throw new Error("Missing required RAG input: context or documents");
    }

    const apiKey = this.ensureGeminiApiKey(options.props);
    const googleAI = createGoogleGenerativeAI({ apiKey });
    const model = googleAI(this.GEMINI_RAG_MODEL);

    // Build conversation history context
    const conversationContext = history?.length
      ? `CONVERSATION HISTORY:\n${history.map((m: any) => `${m.role.toUpperCase()}: ${m.content}`).join("\n")}\n\n`
      : "";

    const prompt = `You are a helpful and expert assistant for the Beddel Protocol.

${conversationContext}CONTEXT INFORMATION:
${context}

USER QUESTION:
${query}

INSTRUCTIONS:
1. Answer the user's question based on the CONTEXT INFORMATION provided above.
2. Consider the CONVERSATION HISTORY for context continuity if available.
3. If the context does not contain the answer, politely state that you don't have enough information in the documentation to answer.
4. Your answer must be in Portuguese.
5. Be concise but comprehensive.

ANSWER:`;

    try {
      options.context.log(`[RAG] Generating answer for query: "${query.substring(0, 50)}..."`);

      const { text } = await generateText({
        model,
        prompt,
        temperature: 0.3
      });

      const result = {
        response: text,
        answer: text,
        timestamp: new Date().toISOString()
      };
      variables.set(resultVar, result);
      return result;

    } catch (error: any) {
      options.context.log(`[RAG] Error: ${error.message}`);
      const result = { success: false, error: error.message };
      variables.set(resultVar, result);
      return result;
    }
  }

  /**
   * Execute builtin-agent step - invokes another builtin agent
   */
  private async executeBuiltinAgent(
    step: any,
    variables: Map<string, any>,
    options: YamlAgentInterpreterOptions
  ): Promise<any> {
    const agentName = step.action?.agent;
    const agentInput = this.resolveInputValue(step.action?.input, options.input, variables) || options.input;
    const agentProps = step.action?.props || options.props;
    const resultVar = step.action?.result || "builtinResult";

    if (!agentName) {
      throw new Error("Missing required builtin-agent input: agent");
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

    } catch (error: any) {
      options.context.log(`[Builtin Agent] Error: ${error.message}`);
      throw new Error(`Builtin agent '${agentName}' execution failed: ${error.message}`);
    }
  }

  /**
   * Helper: Split text into chunks preserving paragraphs
   */
  private splitIntoChunks(text: string, chunkSize: number): string[] {
    const paragraphs = text.split(/\n\s*\n/);
    const chunks: string[] = [];
    let currentChunk = "";

    for (const para of paragraphs) {
      if (currentChunk.length + para.length > chunkSize && currentChunk) {
        chunks.push(currentChunk.trim());
        currentChunk = para;
      } else {
        currentChunk += (currentChunk ? "\n\n" : "") + para;
      }
    }

    if (currentChunk) chunks.push(currentChunk.trim());
    return chunks;
  }

  /**
   * Helper: Resolve input value from step action, input or variables
   */
  private resolveInputValue(
    value: any,
    input: Record<string, any>,
    variables: Map<string, any>
  ): any {
    if (value === undefined || value === null) return undefined;

    // Handle variable references
    if (typeof value === "string" && value.startsWith("$")) {
      const ref = value.substring(1);
      // Check if it's a reference to input
      if (ref.startsWith("input.")) {
        const inputKey = ref.substring(6);
        return this.getNestedValue(input, inputKey);
      }
      // Otherwise resolve from variables
      return this.resolveReference(ref, variables);
    }

    // Handle direct input field references
    if (typeof value === "string" && input[value] !== undefined) {
      return input[value];
    }

    return value;
  }

  /**
   * Helper: Get nested value from object using dot notation
   */
  private getNestedValue(obj: any, path: string): any {
    const parts = path.split(".");
    let current = obj;
    for (const part of parts) {
      if (current == null) return undefined;
      current = current[part];
    }
    return current;
  }


  /**
   * Evaluate value expression
   */
  private evaluateValue(expr: string, variables: Map<string, any>): any {
    // Handle string literals
    if (expr.startsWith('"') && expr.endsWith('"')) {
      if (expr.length - 2 > this.MAX_VARIABLE_SIZE) {
        throw new Error("Variable initialization exceeds maximum size");
      }
      return expr.slice(1, -1);
    }

    if (expr.startsWith("'") && expr.endsWith("'")) {
      if (expr.length - 2 > this.MAX_VARIABLE_SIZE) {
        throw new Error("Variable initialization exceeds maximum size");
      }
      return expr.slice(1, -1);
    }

    if (expr.length > this.MAX_VARIABLE_SIZE) {
      throw new Error("Variable initialization exceeds maximum size");
    }

    // Handle boolean literals
    if (expr === "true") return true;
    if (expr === "false") return false;

    // Handle null literal
    if (expr === "null") return null;

    // Handle variable references
    if (expr.startsWith("$")) {
      return this.resolveReference(expr.substring(1), variables);
    }

    // Handle numbers
    if (/^-?\d+$/.test(expr)) return parseInt(expr, 10);
    if (/^-?\d+\.\d+$/.test(expr)) return parseFloat(expr);

    throw new Error(`Unsupported value expression: ${expr}`);
  }

  /**
   * Validate variable declaration
   */
  private validateVariable(variable: any): void {
    if (!variable.name || !variable.type) {
      throw new Error("Invalid variable declaration: missing name or type");
    }

    if (!["string", "number", "boolean", "object"].includes(variable.type)) {
      throw new Error(`Unsupported variable type: ${variable.type}`);
    }
  }

  /**
   * Resolve variable reference, including nested properties (e.g., foo.bar.baz)
   */
  private resolveReference(
    reference: string,
    variables: Map<string, any>
  ): any {
    const [varName, ...pathSegments] = reference.split(".");
    let value = variables.get(varName);
    if (value === undefined) {
      throw new Error(`Undefined variable referenced: ${varName}`);
    }

    for (const segment of pathSegments) {
      if (value == null || typeof value !== "object") {
        throw new Error(
          `Cannot resolve path '${reference}': segment '${segment}' is invalid`
        );
      }
      value = value[segment];
    }

    return value;
  }

  /**
   * Ensure we have a Gemini API key before calling Genkit helpers
   */
  private ensureGeminiApiKey(props: Record<string, string>): string {
    const apiKey = props?.gemini_api_key?.trim();
    if (!apiKey) {
      throw new Error(
        "Missing required prop: gemini_api_key. Configure a valid Gemini API key before calling this agent."
      );
    }
    return apiKey;
  }

  private createGeminiModel(props: Record<string, string>) {
    const apiKey = this.ensureGeminiApiKey(props);
    const google = createGoogleGenerativeAI({ apiKey });
    const model = google(this.GEMINI_MODEL);
    return model;
  }

  private createGeminiImageModel(props: Record<string, string>) {
    const apiKey = this.ensureGeminiApiKey(props);
    const google = createGoogleGenerativeAI({ apiKey });
    return google.image(this.GEMINI_IMAGE_MODEL);
  }

  private async callGeminiFlashText(
    params: {
      prompt: string;
      temperature?: number;
      maxTokens?: number;
    },
    props: Record<string, string>,
    context: ExecutionContext
  ): Promise<{
    texto: string;
    metadados: {
      modelo_utilizado: string;
      tempo_processamento: number;
      temperature: number;
      max_tokens: number | null;
      prompt_utilizado: string;
    };
  }> {
    const prompt = params.prompt?.trim();
    if (!prompt) {
      throw new Error("Gemini Flash text helper requires a prompt");
    }

    const temperature =
      typeof params.temperature === "number" ? params.temperature : 0.7;
    const maxTokens =
      typeof params.maxTokens === "number" ? params.maxTokens : undefined;

    const model = this.createGeminiModel(props);
    const startTime = Date.now();

    try {
      context.log(
        `Invoking Gemini Flash text helper (temperature=${temperature}, maxTokens=${typeof maxTokens === "number" ? maxTokens : "provider-default"
        })`
      );
      const generationOptions: Record<string, any> = {
        model,
        prompt,
        temperature,
      };
      if (typeof maxTokens === "number") {
        generationOptions.maxOutputTokens = maxTokens;
      }
      const { text, content } = await generateText(
        generationOptions as any
      );
      const contentText = content
        ? content
          .map((part: any) =>
            typeof part?.text === "string" ? part.text : ""
          )
          .join(" ")
          .trim()
        : "";
      const finalText = (text || "").trim() || contentText || "";
      if (!finalText) {
        throw new Error("Gemini Flash text helper returned empty response");
      }

      return {
        texto: finalText,
        metadados: {
          modelo_utilizado: this.GEMINI_MODEL,
          tempo_processamento: Date.now() - startTime,
          temperature,
          max_tokens: typeof maxTokens === "number" ? maxTokens : null,
          prompt_utilizado: prompt,
        },
      };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown Gemini Flash error";
      context.log(`Gemini Flash text helper failed: ${message}`);
      context.setError(message);
      throw error;
    }
  }

  private async callGeminiFlashTranslation(
    params: {
      texto?: string;
      idioma_origem?: string;
      idioma_destino?: string;
      promptTemplate?: string;
    },
    props: Record<string, string>,
    context: ExecutionContext
  ): Promise<{
    texto_traduzido: string;
    metadados: {
      modelo_utilizado: string;
      tempo_processamento: number;
      confianca: number;
      idiomas_suportados: string[];
      idiomas_solicitados: {
        origem: string;
        destino: string;
      };
      prompt_utilizado: string;
    };
  }> {
    const texto = params.texto?.trim();
    const idiomaOrigem = params.idioma_origem?.trim().toLowerCase();
    const idiomaDestino = params.idioma_destino?.trim().toLowerCase();

    if (!texto || !idiomaOrigem || !idiomaDestino) {
      throw new Error(
        "Missing required translation parameters: texto, idioma_origem, idioma_destino"
      );
    }

    if (idiomaOrigem === idiomaDestino) {
      return {
        texto_traduzido: texto,
        metadados: {
          modelo_utilizado: this.GEMINI_MODEL,
          tempo_processamento: 0,
          confianca: 1,
          idiomas_suportados: this.SUPPORTED_TRANSLATION_LANGUAGES,
          idiomas_solicitados: {
            origem: idiomaOrigem,
            destino: idiomaDestino,
          },
          prompt_utilizado: "Bypass: idiomas de origem e destino são iguais",
        },
      };
    }

    const template =
      params.promptTemplate && params.promptTemplate.trim().length > 0
        ? params.promptTemplate
        : `Traduza o texto abaixo de {{idioma_origem}} para {{idioma_destino}}.
Responda somente com o texto traduzido sem comentários adicionais.

Texto:
{{texto}}`;

    const prompt = template
      .replace(/{{texto}}/g, texto)
      .replace(/{{idioma_origem}}/g, idiomaOrigem)
      .replace(/{{idioma_destino}}/g, idiomaDestino)
      .trim();

    const model = this.createGeminiModel(props);
    const startTime = Date.now();

    try {
      context.log(
        `Invoking Gemini Flash translation helper (${idiomaOrigem}->${idiomaDestino})`
      );
      const { text, content } = await generateText({
        model,
        prompt,
        temperature: 0.2,
      });

      const contentText = content
        ? content
          .map((part: any) =>
            typeof part?.text === "string" ? part.text : ""
          )
          .join(" ")
          .trim()
        : "";
      const translatedText = (text || "").trim() || contentText || "";
      if (!translatedText) {
        throw new Error("Gemini Flash translation returned empty response");
      }

      return {
        texto_traduzido: translatedText,
        metadados: {
          modelo_utilizado: this.GEMINI_MODEL,
          tempo_processamento: Date.now() - startTime,
          confianca: 0.85,
          idiomas_suportados: this.SUPPORTED_TRANSLATION_LANGUAGES,
          idiomas_solicitados: {
            origem: idiomaOrigem,
            destino: idiomaDestino,
          },
          prompt_utilizado: prompt,
        },
      };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown translation error";
      context.log(`Gemini Flash translation failed: ${message}`);
      context.setError(message);
      throw error;
    }
  }

  private async callGeminiFlashImage(
    params: { prompt: string; estilo: string; resolucao: string },
    props: Record<string, string>,
    context: ExecutionContext
  ): Promise<{
    image_url: string;
    image_base64: string;
    media_type: string;
    prompt_utilizado: string;
    metadados: {
      modelo_utilizado: string;
      tempo_processamento: number;
      estilo: string;
      resolucao: string;
    };
  }> {
    const prompt = params.prompt?.trim();
    const estilo = params.estilo?.trim();
    const resolucao = params.resolucao?.trim();

    if (!prompt) {
      throw new Error("Gemini Flash image helper requires a prompt");
    }
    if (!estilo) {
      throw new Error("Gemini Flash image helper requires an estilo value");
    }
    if (!resolucao || !/^\d+x\d+$/.test(resolucao)) {
      throw new Error(
        "Gemini Flash image helper requires uma resolução no formato LARGURAxALTURA (ex: 1024x1024)"
      );
    }

    const model = this.createGeminiImageModel(props);
    const startTime = Date.now();

    try {
      context.log(
        `Invoking Gemini Flash image helper (estilo=${estilo}, resolucao=${resolucao})`
      );
      const result = await experimental_generateImage({
        model,
        prompt,
        size: resolucao as `${number}x${number}`,
      });

      const image = result.image;
      if (!image?.base64 || !image.mediaType) {
        throw new Error("Gemini Flash image helper returned an invalid file");
      }

      const normalizedBase64 = image.base64.replace(/\s+/g, "");
      const imageUrl = `data:${image.mediaType};base64,${normalizedBase64}`;

      return {
        image_url: imageUrl,
        image_base64: normalizedBase64,
        media_type: image.mediaType,
        prompt_utilizado: prompt,
        metadados: {
          modelo_utilizado: this.GEMINI_IMAGE_MODEL,
          tempo_processamento: Date.now() - startTime,
          estilo,
          resolucao,
        },
      };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown image error";
      context.log(`Gemini Flash image helper failed: ${message}`);
      context.setError(message);
      throw error;
    }
  }
}

// Singleton instance
export const declarativeInterpreter = new DeclarativeAgentInterpreter();

export default DeclarativeAgentInterpreter;
