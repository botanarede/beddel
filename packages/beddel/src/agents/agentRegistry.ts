/**
 * Agent Registry Service
 * Manages registration and execution of declarative YAML agents
 */

import { existsSync, readFileSync, readdirSync, statSync } from "fs";
import { join } from "path";
import { declarativeInterpreter } from "../runtime/declarativeAgentRuntime";
import { ExecutionContext } from "../types/executionContext";

export interface AgentRegistration {
  id: string;
  name: string;
  description: string;
  protocol: string;
  route: string;
  requiredProps: string[];
  yamlContent: string;
}

/**
 * Agent Registry - Manages declarative agent registration and execution
 */
export class AgentRegistry {
  private readonly agents: Map<string, AgentRegistration> = new Map();
  private readonly customFunctions: Map<string, Function> = new Map();

  constructor() {
    // Register built-in agents on initialization
    this.registerBuiltinAgents();

    // Automatically load custom agents if running in Node.js environment
    // This runs asynchronously in the background
    if (typeof process !== 'undefined' && typeof process.cwd === 'function') {
      this.loadCustomAgents().catch((error) => {
        // Silently fail if custom agents can't be loaded
        // This allows the registry to work even without custom agents
        console.error('Failed to load custom agents during initialization:', error);
      });
    }
  }

  /**
   * Register an agent
   */
  public registerAgent(agent: AgentRegistration, allowOverwrite = false): void {
    // Validate agent
    this.validateAgent(agent);

    // Check if agent already exists
    if (this.agents.has(agent.name) && allowOverwrite) {
      console.warn(`⚠️  Overwriting existing agent: ${agent.name}`);
    }

    // Register the agent
    this.agents.set(agent.name, agent);
    console.log(`Agent registered: ${agent.name} (${agent.protocol})`);
  }

  /**
   * Execute registered agent
   */
  public async executeAgent(
    agentName: string,
    input: Record<string, any>,
    props: Record<string, string>,
    context: ExecutionContext
  ): Promise<any> {
    // Find agent
    const agent = this.agents.get(agentName);
    if (!agent) {
      throw new Error(`Agent not found: ${agentName}`);
    }

    // Execute using declarative interpreter
    const result = await declarativeInterpreter.interpret({
      yamlContent: agent.yamlContent,
      input,
      props,
      context,
    });

    return result;
  }

  /**
   * Get registered agent
   */
  public getAgent(agentName: string): AgentRegistration | undefined {
    return this.agents.get(agentName);
  }

  /**
   * Get all registered agents
   */
  public getAllAgents(): AgentRegistration[] {
    return Array.from(this.agents.values());
  }

  /**
   * Load custom agents from a specified directory
   * @param customAgentsPath - Optional path to custom agents directory. Defaults to process.cwd()/agents
   */
  public async loadCustomAgents(customAgentsPath?: string): Promise<void> {
    try {
      // Determine the agents directory path
      const agentsPath = customAgentsPath || join(process.cwd(), "agents");

      // Check if directory exists
      if (!existsSync(agentsPath)) {
        console.log(`No custom agents directory found at: ${agentsPath}`);
        return;
      }

      console.log(`🔍 Loading custom agents from: ${agentsPath}`);

      // Discover all YAML files in the agents directory
      const agentFiles = this.discoverCustomAgentFiles(agentsPath);

      if (agentFiles.length === 0) {
        console.log(`No custom agent YAML files found in: ${agentsPath}`);
      }

      // Register each custom agent
      let successCount = 0;
      for (const yamlPath of agentFiles) {
        try {
          this.registerCustomAgent(yamlPath);
          successCount++;
        } catch (error) {
          console.error(`Failed to register custom agent from ${yamlPath}:`, error);
        }
      }

      if (agentFiles.length > 0) {
        console.log(`✅ Successfully loaded ${successCount}/${agentFiles.length} custom agents`);
      }

      // Load TypeScript implementations
      await this.loadCustomFunctions(agentsPath);
    } catch (error) {
      console.error("Failed to load custom agents:", error);
    }
  }

  /**
   * Register a custom agent from a YAML file
   */
  private registerCustomAgent(yamlPath: string): void {
    // Read YAML file
    const yamlContent = readFileSync(yamlPath, "utf-8");

    // Parse agent metadata
    const agent = this.parseAgentYaml(yamlContent);

    // Determine agent name from metadata or filename
    const agentName = agent.metadata.route
      ? agent.metadata.route.replace("/agents/", "") + ".execute"
      : agent.agent.id + ".execute";

    // Register the agent (allow overwriting built-ins)
    this.registerAgent(
      {
        id: agent.agent.id,
        name: agentName,
        description: agent.metadata.description,
        protocol: agent.agent.protocol,
        route: agent.metadata.route || `/agents/${agent.agent.id}`,
        requiredProps: agent.schema.required || ["gemini_api_key"],
        yamlContent,
      },
      true // Allow overwriting
    );
  }

  /**
   * Discover all YAML files in the custom agents directory
   */
  private discoverCustomAgentFiles(agentsPath: string): string[] {
    const yamlFiles: string[] = [];

    const scanDirectory = (dirPath: string) => {
      const entries = readdirSync(dirPath);

      for (const entry of entries) {
        const fullPath = join(dirPath, entry);
        const stat = statSync(fullPath);

        if (stat.isDirectory()) {
          // Recursively scan subdirectories
          scanDirectory(fullPath);
        } else if (stat.isFile() && (entry.endsWith(".yaml") || entry.endsWith(".yml"))) {
          yamlFiles.push(fullPath);
        }
      }
    };

    scanDirectory(agentsPath);
    return yamlFiles;
  }

  /**
   * Register built-in agents
   */
  private registerBuiltinAgents(): void {
    try {
      // Register Joker Agent
      this.registerJokerAgent();
      // Register Translator Agent
      this.registerTranslatorAgent();
      // Register Image Generator Agent
      this.registerImageAgent();
      // Register MCP Tool Agent
      this.registerMcpToolAgent();
      // Register Gemini Vectorize Agent
      this.registerGeminiVectorizeAgent();
      // Register ChromaDB Agent
      this.registerChromaDBAgent();
      // Register GitMCP Agent
      this.registerGitMcpAgent();
      // Register RAG Agent
      this.registerRagAgent();
      // Register Chat Agent (Orchestrator)
      this.registerChatAgent();
    } catch (error) {
      console.error("Failed to register built-in agents:", error);
    }
  }

  /**
   * Register Joker Agent
   */
  private registerJokerAgent(): void {
    try {
      // Get the Joker Agent YAML content
      const jokerYamlPath = this.resolveAgentPath("joker-agent.yaml");
      const yamlContent = readFileSync(jokerYamlPath, "utf-8");

      // Parse YAML to extract metadata
      const agent = this.parseAgentYaml(yamlContent);

      this.registerAgent({
        id: agent.agent.id,
        name: "joker.execute",
        description: agent.metadata.description,
        protocol: agent.agent.protocol,
        route: agent.metadata.route || "/agents/joker",
        requiredProps: ["gemini_api_key"],
        yamlContent,
      });
    } catch (error) {
      console.error("Failed to register Joker Agent:", error);
      throw error;
    }
  }

  /**
   * Register Translator Agent
   */
  private registerTranslatorAgent(): void {
    try {
      const translatorYamlPath = this.resolveAgentPath("translator-agent.yaml");
      const yamlContent = readFileSync(translatorYamlPath, "utf-8");
      const agent = this.parseAgentYaml(yamlContent);

      this.registerAgent({
        id: agent.agent.id,
        name: "translator.execute",
        description: agent.metadata.description,
        protocol: agent.agent.protocol,
        route: agent.metadata.route || "/agents/translator",
        requiredProps: ["gemini_api_key"],
        yamlContent,
      });
    } catch (error) {
      console.error("Failed to register Translator Agent:", error);
      throw error;
    }
  }

  /**
   * Register Image Generator Agent
   */
  private registerImageAgent(): void {
    try {
      const imageYamlPath = this.resolveAgentPath("image-agent.yaml");
      const yamlContent = readFileSync(imageYamlPath, "utf-8");
      const agent = this.parseAgentYaml(yamlContent);

      this.registerAgent({
        id: agent.agent.id,
        name: "image.generate",
        description: agent.metadata.description,
        protocol: agent.agent.protocol,
        route: agent.metadata.route || "/agents/image",
        requiredProps: ["gemini_api_key"],
        yamlContent,
      });
    } catch (error) {
      console.error("Failed to register Image Agent:", error);
      throw error;
    }
  }

  /**
   * Register MCP Tool Agent
   */
  private registerMcpToolAgent(): void {
    try {
      const yamlPath = this.resolveAgentPath("mcp-tool-agent.yaml");
      const yamlContent = readFileSync(yamlPath, "utf-8");
      const agent = this.parseAgentYaml(yamlContent);

      this.registerAgent({
        id: agent.agent.id,
        name: "mcp-tool.execute",
        description: agent.metadata.description,
        protocol: agent.agent.protocol,
        route: agent.metadata.route || "/agents/mcp-tool",
        requiredProps: [],
        yamlContent,
      });
    } catch (error) {
      console.error("Failed to register MCP Tool Agent:", error);
      throw error;
    }
  }

  /**
   * Register Gemini Vectorize Agent
   */
  private registerGeminiVectorizeAgent(): void {
    try {
      const yamlPath = this.resolveAgentPath("gemini-vectorize-agent.yaml");
      const yamlContent = readFileSync(yamlPath, "utf-8");
      const agent = this.parseAgentYaml(yamlContent);

      this.registerAgent({
        id: agent.agent.id,
        name: "gemini-vectorize.execute",
        description: agent.metadata.description,
        protocol: agent.agent.protocol,
        route: agent.metadata.route || "/agents/gemini-vectorize",
        requiredProps: ["gemini_api_key"],
        yamlContent,
      });
    } catch (error) {
      console.error("Failed to register Gemini Vectorize Agent:", error);
      throw error;
    }
  }

  /**
   * Register ChromaDB Agent
   */
  private registerChromaDBAgent(): void {
    try {
      const yamlPath = this.resolveAgentPath("chromadb-agent.yaml");
      const yamlContent = readFileSync(yamlPath, "utf-8");
      const agent = this.parseAgentYaml(yamlContent);

      this.registerAgent({
        id: agent.agent.id,
        name: "chromadb.execute",
        description: agent.metadata.description,
        protocol: agent.agent.protocol,
        route: agent.metadata.route || "/agents/chromadb",
        requiredProps: [],
        yamlContent,
      });
    } catch (error) {
      console.error("Failed to register ChromaDB Agent:", error);
      throw error;
    }
  }

  /**
   * Register GitMCP Agent
   */
  private registerGitMcpAgent(): void {
    try {
      const yamlPath = this.resolveAgentPath("gitmcp-agent.yaml");
      const yamlContent = readFileSync(yamlPath, "utf-8");
      const agent = this.parseAgentYaml(yamlContent);

      this.registerAgent({
        id: agent.agent.id,
        name: "gitmcp.execute",
        description: agent.metadata.description,
        protocol: agent.agent.protocol,
        route: agent.metadata.route || "/agents/gitmcp",
        requiredProps: [],
        yamlContent,
      });
    } catch (error) {
      console.error("Failed to register GitMCP Agent:", error);
      throw error;
    }
  }

  /**
   * Register RAG Agent
   */
  private registerRagAgent(): void {
    try {
      const yamlPath = this.resolveAgentPath("rag-agent.yaml");
      const yamlContent = readFileSync(yamlPath, "utf-8");
      const agent = this.parseAgentYaml(yamlContent);

      this.registerAgent({
        id: agent.agent.id,
        name: "rag.execute",
        description: agent.metadata.description,
        protocol: agent.agent.protocol,
        route: agent.metadata.route || "/agents/rag",
        requiredProps: ["gemini_api_key"],
        yamlContent,
      });
    } catch (error) {
      console.error("Failed to register RAG Agent:", error);
      throw error;
    }
  }

  /**
   * Register Chat Agent (Orchestrator)
   */
  private registerChatAgent(): void {
    try {
      const yamlPath = this.resolveAgentPath("chat-agent.yaml");
      const yamlContent = readFileSync(yamlPath, "utf-8");
      const agent = this.parseAgentYaml(yamlContent);

      this.registerAgent({
        id: agent.agent.id,
        name: "chat.execute",
        description: agent.metadata.description,
        protocol: agent.agent.protocol,
        route: agent.metadata.route || "/agents/chat",
        requiredProps: ["gemini_api_key"],
        yamlContent,
      });
    } catch (error) {
      console.error("Failed to register Chat Agent:", error);
      throw error;
    }
  }

  /**
   * Parse agent YAML content
   */
  private parseAgentYaml(yamlContent: string): any {
    // Simple validation - full parsing will be done by interpreter
    if (!yamlContent.includes("agent:") || !yamlContent.includes("logic:")) {
      throw new Error("Invalid agent YAML: missing required sections");
    }

    // Basic YAML parsing for metadata extraction
    const lines = yamlContent.split("\n");
    const metadata: any = {
      agent: { id: "", protocol: "" },
      metadata: { description: "", route: "" },
      schema: { required: [] },
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      if (line.startsWith("id:") && metadata.agent.id === "") {
        metadata.agent.id = line.split(":")[1].trim();
      }

      if (line.startsWith("protocol:") && metadata.agent.protocol === "") {
        metadata.agent.protocol = line.split(":")[1].trim();
      }

      if (
        line.startsWith("description:") &&
        metadata.metadata.description === ""
      ) {
        metadata.metadata.description = line
          .substring(line.indexOf(":") + 1)
          .trim();
      }

      if (line.startsWith("route:") && metadata.metadata.route === "") {
        metadata.metadata.route = line.split(":")[1].trim();
      }

      if (
        line.startsWith("required:") &&
        metadata.schema.required.length === 0
      ) {
        // Parse required array
        const requiredStr = line.substring(line.indexOf(":") + 1).trim();
        metadata.schema.required = JSON.parse(requiredStr);
      }
    }

    return metadata;
  }

  /**
   * Validate agent registration
   */
  private validateAgent(agent: AgentRegistration): void {
    if (!agent.id || !agent.name || !agent.protocol) {
      throw new Error("Invalid agent: missing required fields");
    }

    if (!agent.yamlContent || agent.yamlContent.length === 0) {
      throw new Error("Invalid agent: missing YAML content");
    }

    if (!agent.protocol.startsWith("beddel-declarative-protocol")) {
      throw new Error(`Unsupported protocol: ${agent.protocol}`);
    }
  }

  /**
   * Resolve agent asset path when running in bundled runtimes
   */
  private resolveAgentPath(filename: string): string {
    const candidatePaths = [
      join(__dirname, filename),
      join(process.cwd(), "packages", "beddel", "src", "agents", filename),
    ];

    for (const path of candidatePaths) {
      if (existsSync(path)) {
        return path;
      }
    }

    throw new Error(
      `Unable to locate agent asset '${filename}' in paths: ${candidatePaths.join(
        ", "
      )}`
    );
  }

  /**
   * Load custom TypeScript function implementations from /agents directory
   * @param agentsPath - Path to the agents directory
   */
  private async loadCustomFunctions(agentsPath: string): Promise<void> {
    try {
      const files = readdirSync(agentsPath);
      let functionCount = 0;

      for (const file of files) {
        if (file.endsWith(".ts")) {
          const modulePath = join(agentsPath, file);
          try {
            // Dynamic import of the custom agent module
            const module = await import(modulePath);

            // Register all exported functions with a namespaced key
            // e.g., "my-agent/myFunction"
            Object.keys(module).forEach((funcName) => {
              if (typeof module[funcName] === "function") {
                const key = `${file.replace(".ts", "")}/${funcName}`;
                this.customFunctions.set(key, module[funcName]);
                functionCount++;
                console.log(`📦 Registered custom function: ${key}`);
              }
            });
          } catch (err) {
            console.error(
              `Failed to load custom agent implementation ${file}:`,
              err
            );
          }
        }
      }

      if (functionCount > 0) {
        console.log(`✅ Successfully loaded ${functionCount} custom function(s)`);
      }
    } catch (error) {
      console.error("Failed to load custom functions:", error);
    }
  }

  /**
   * Get a custom function by its namespaced key
   * @param name - Function name in format "agent-name/functionName"
   * @returns The registered function or undefined
   */
  public getCustomFunction(name: string): Function | undefined {
    return this.customFunctions.get(name);
  }
}

// Singleton instance
export const agentRegistry = new AgentRegistry();

export default AgentRegistry;
