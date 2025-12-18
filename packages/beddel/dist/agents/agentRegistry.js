"use strict";
/**
 * Agent Registry Service
 * Manages registration and execution of declarative YAML agents
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.agentRegistry = exports.AgentRegistry = void 0;
const fs_1 = require("fs");
const path_1 = require("path");
const declarativeAgentRuntime_1 = require("../runtime/declarativeAgentRuntime");
/**
 * Agent Registry - Manages declarative agent registration and execution
 */
class AgentRegistry {
    constructor() {
        this.agents = new Map();
        // Register built-in agents on initialization
        this.registerBuiltinAgents();
        // Automatically load custom agents if running in Node.js environment
        if (typeof process !== 'undefined' && typeof process.cwd === 'function') {
            try {
                this.loadCustomAgents();
            }
            catch (error) {
                // Silently fail if custom agents can't be loaded
                // This allows the registry to work even without custom agents
            }
        }
    }
    /**
     * Register an agent
     */
    registerAgent(agent, allowOverwrite = false) {
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
    async executeAgent(agentName, input, props, context) {
        // Find agent
        const agent = this.agents.get(agentName);
        if (!agent) {
            throw new Error(`Agent not found: ${agentName}`);
        }
        // Execute using declarative interpreter
        const result = await declarativeAgentRuntime_1.declarativeInterpreter.interpret({
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
    getAgent(agentName) {
        return this.agents.get(agentName);
    }
    /**
     * Get all registered agents
     */
    getAllAgents() {
        return Array.from(this.agents.values());
    }
    /**
     * Load custom agents from a specified directory
     * @param customAgentsPath - Optional path to custom agents directory. Defaults to process.cwd()/agents
     */
    loadCustomAgents(customAgentsPath) {
        try {
            // Determine the agents directory path
            const agentsPath = customAgentsPath || (0, path_1.join)(process.cwd(), "agents");
            // Check if directory exists
            if (!(0, fs_1.existsSync)(agentsPath)) {
                console.log(`No custom agents directory found at: ${agentsPath}`);
                return;
            }
            console.log(`🔍 Loading custom agents from: ${agentsPath}`);
            // Discover all YAML files in the agents directory
            const agentFiles = this.discoverCustomAgentFiles(agentsPath);
            if (agentFiles.length === 0) {
                console.log(`No custom agent YAML files found in: ${agentsPath}`);
                return;
            }
            // Register each custom agent
            let successCount = 0;
            for (const yamlPath of agentFiles) {
                try {
                    this.registerCustomAgent(yamlPath);
                    successCount++;
                }
                catch (error) {
                    console.error(`Failed to register custom agent from ${yamlPath}:`, error);
                }
            }
            console.log(`✅ Successfully loaded ${successCount}/${agentFiles.length} custom agents`);
        }
        catch (error) {
            console.error("Failed to load custom agents:", error);
        }
    }
    /**
     * Register a custom agent from a YAML file
     */
    registerCustomAgent(yamlPath) {
        // Read YAML file
        const yamlContent = (0, fs_1.readFileSync)(yamlPath, "utf-8");
        // Parse agent metadata
        const agent = this.parseAgentYaml(yamlContent);
        // Determine agent name from metadata or filename
        const agentName = agent.metadata.route
            ? agent.metadata.route.replace("/agents/", "") + ".execute"
            : agent.agent.id + ".execute";
        // Register the agent (allow overwriting built-ins)
        this.registerAgent({
            id: agent.agent.id,
            name: agentName,
            description: agent.metadata.description,
            protocol: agent.agent.protocol,
            route: agent.metadata.route || `/agents/${agent.agent.id}`,
            requiredProps: agent.schema.required || ["gemini_api_key"],
            yamlContent,
        }, true // Allow overwriting
        );
    }
    /**
     * Discover all YAML files in the custom agents directory
     */
    discoverCustomAgentFiles(agentsPath) {
        const yamlFiles = [];
        const scanDirectory = (dirPath) => {
            const entries = (0, fs_1.readdirSync)(dirPath);
            for (const entry of entries) {
                const fullPath = (0, path_1.join)(dirPath, entry);
                const stat = (0, fs_1.statSync)(fullPath);
                if (stat.isDirectory()) {
                    // Recursively scan subdirectories
                    scanDirectory(fullPath);
                }
                else if (stat.isFile() && (entry.endsWith(".yaml") || entry.endsWith(".yml"))) {
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
    registerBuiltinAgents() {
        try {
            // Register Joker Agent
            this.registerJokerAgent();
            // Register Translator Agent
            this.registerTranslatorAgent();
            // Register Image Generator Agent
            this.registerImageAgent();
        }
        catch (error) {
            console.error("Failed to register built-in agents:", error);
        }
    }
    /**
     * Register Joker Agent
     */
    registerJokerAgent() {
        try {
            // Get the Joker Agent YAML content
            const jokerYamlPath = this.resolveAgentPath("joker-agent.yaml");
            const yamlContent = (0, fs_1.readFileSync)(jokerYamlPath, "utf-8");
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
        }
        catch (error) {
            console.error("Failed to register Joker Agent:", error);
            throw error;
        }
    }
    /**
     * Register Translator Agent
     */
    registerTranslatorAgent() {
        try {
            const translatorYamlPath = this.resolveAgentPath("translator-agent.yaml");
            const yamlContent = (0, fs_1.readFileSync)(translatorYamlPath, "utf-8");
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
        }
        catch (error) {
            console.error("Failed to register Translator Agent:", error);
            throw error;
        }
    }
    /**
     * Register Image Generator Agent
     */
    registerImageAgent() {
        try {
            const imageYamlPath = this.resolveAgentPath("image-agent.yaml");
            const yamlContent = (0, fs_1.readFileSync)(imageYamlPath, "utf-8");
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
        }
        catch (error) {
            console.error("Failed to register Image Agent:", error);
            throw error;
        }
    }
    /**
     * Parse agent YAML content
     */
    parseAgentYaml(yamlContent) {
        // Simple validation - full parsing will be done by interpreter
        if (!yamlContent.includes("agent:") || !yamlContent.includes("logic:")) {
            throw new Error("Invalid agent YAML: missing required sections");
        }
        // Basic YAML parsing for metadata extraction
        const lines = yamlContent.split("\n");
        const metadata = {
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
            if (line.startsWith("description:") &&
                metadata.metadata.description === "") {
                metadata.metadata.description = line
                    .substring(line.indexOf(":") + 1)
                    .trim();
            }
            if (line.startsWith("route:") && metadata.metadata.route === "") {
                metadata.metadata.route = line.split(":")[1].trim();
            }
            if (line.startsWith("required:") &&
                metadata.schema.required.length === 0) {
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
    validateAgent(agent) {
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
    resolveAgentPath(filename) {
        const candidatePaths = [
            (0, path_1.join)(__dirname, filename),
            (0, path_1.join)(process.cwd(), "packages", "beddel", "src", "agents", filename),
        ];
        for (const path of candidatePaths) {
            if ((0, fs_1.existsSync)(path)) {
                return path;
            }
        }
        throw new Error(`Unable to locate agent asset '${filename}' in paths: ${candidatePaths.join(", ")}`);
    }
}
exports.AgentRegistry = AgentRegistry;
// Singleton instance
exports.agentRegistry = new AgentRegistry();
exports.default = AgentRegistry;
//# sourceMappingURL=agentRegistry.js.map