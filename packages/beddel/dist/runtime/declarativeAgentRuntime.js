"use strict";
/**
 * Declarative Agent Runtime - YAML Interpreter for Beddel Declarative Protocol
 * Safely interprets declarative YAML agent definitions without dynamic code execution
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.declarativeInterpreter = exports.DeclarativeAgentInterpreter = void 0;
const yaml = __importStar(require("js-yaml"));
const ai_1 = require("ai");
const google_1 = require("@ai-sdk/google");
const schemaCompiler_1 = require("./schemaCompiler");
/**
 * Safe declarative YAML interpreter - no dynamic code execution
 */
class DeclarativeAgentInterpreter {
    constructor() {
        this.MAX_VARIABLE_SIZE = 1024; // 1KB max variable size
        this.MAX_WORKFLOW_STEPS = 100; // Prevent infinite loops
        this.MAX_OUTPUT_SIZE = 5 * 1024 * 1024; // 5MB max output to accommodate image payloads
        this.GEMINI_MODEL = "models/gemini-2.5-flash";
        this.GEMINI_IMAGE_MODEL = "imagen-4.0-fast-generate-001";
        this.SUPPORTED_TRANSLATION_LANGUAGES = ["pt", "en", "es", "fr"];
        this.schemaCompiler = new schemaCompiler_1.DeclarativeSchemaCompiler();
    }
    /**
     * Interpret declarative YAML agent definition
     */
    async interpret(options) {
        const startTime = Date.now();
        try {
            // Parse and validate YAML
            const agent = this.parseYaml(options.yamlContent);
            this.validateAgentDefinition(agent);
            // Compile schemas and validate input up front
            const schemas = this.buildSchemaSet(agent);
            const validatedInput = this.validateAgainstSchema(options.input, schemas.input, "input", options.context);
            const executionOptions = {
                ...options,
                input: validatedInput,
            };
            // Execute declarative logic
            const result = await this.executeWorkflow(agent, executionOptions);
            // Validate output
            const validatedOutput = this.validateAgainstSchema(result, schemas.output, "output", options.context);
            this.enforceOutputSize(validatedOutput);
            const executionTime = Date.now() - startTime;
            options.context.log(`Declarative agent executed in ${executionTime}ms`);
            return validatedOutput;
        }
        catch (error) {
            const executionTime = Date.now() - startTime;
            options.context.log(`Declarative agent execution failed: ${error}`);
            options.context.setError(error instanceof Error
                ? error.message
                : "Unknown declarative agent error");
            throw error;
        }
    }
    /**
     * Parse and validate YAML content
     */
    parseYaml(yamlContent) {
        try {
            const parsed = yaml.load(yamlContent);
            if (!parsed || typeof parsed !== "object") {
                throw new Error("Invalid YAML: expected object");
            }
            if (!parsed.agent || !parsed.logic || !parsed.schema) {
                throw new Error("Invalid agent definition: missing required sections");
            }
            return parsed;
        }
        catch (error) {
            throw new Error(`YAML parsing failed: ${error}`);
        }
    }
    /**
     * Validate agent definition structure
     */
    validateAgentDefinition(agent) {
        // Validate protocol version
        if (agent.agent.protocol !== "beddel-declarative-protocol/v2.0") {
            throw new Error(`Unsupported protocol: ${agent.agent.protocol}`);
        }
        // Validate schema
        if (!agent.schema.input || !agent.schema.output) {
            throw new Error("Invalid schema: missing input or output definition");
        }
        // Validate workflow
        if (!Array.isArray(agent.logic.workflow) ||
            agent.logic.workflow.length === 0) {
            throw new Error("Invalid workflow: must be non-empty array");
        }
        if (agent.logic.workflow.length > this.MAX_WORKFLOW_STEPS) {
            throw new Error(`Workflow too complex: max ${this.MAX_WORKFLOW_STEPS} steps allowed`);
        }
    }
    buildSchemaSet(agent) {
        return {
            input: this.schemaCompiler.compile(agent.schema.input, "schema.input"),
            output: this.schemaCompiler.compile(agent.schema.output, "schema.output"),
        };
    }
    validateAgainstSchema(data, schema, phase, context) {
        const validationResult = schema.safeParse(data);
        if (!validationResult.success) {
            const issues = validationResult.error.issues;
            const issueSummary = issues
                .map((issue) => `${issue.path.join(".") || "root"}: ${issue.message}`)
                .join("; ");
            const label = phase === "input" ? "Input" : "Output";
            const message = `${label} validation failed: ${issueSummary}`;
            context.setError(message);
            throw new schemaCompiler_1.DeclarativeSchemaValidationError(message, phase, issues);
        }
        return validationResult.data;
    }
    enforceOutputSize(output) {
        const outputSize = JSON.stringify(output).length;
        if (outputSize > this.MAX_OUTPUT_SIZE) {
            throw new Error(`Output size exceeds maximum allowed: ${outputSize} > ${this.MAX_OUTPUT_SIZE}`);
        }
    }
    /**
     * Execute declarative workflow
     */
    async executeWorkflow(agent, options) {
        const variables = new Map();
        let output = undefined;
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
    async executeWorkflowStep(step, variables, options) {
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
            default:
                throw new Error(`Unsupported workflow step type: ${step.type}`);
        }
    }
    /**
     * Execute output generator step
     */
    executeOutputGenerator(step, variables, options) {
        if (step.action?.type !== "generate" || !step.action.output) {
            throw new Error("Invalid output generator configuration");
        }
        // Build output object
        const output = {};
        // Debug: Log available variables
        options.context.log(`Output generator: Available variables: ${Array.from(variables.keys()).join(", ")}`);
        for (const [key, valueExpr] of Object.entries(step.action.output)) {
            if (typeof valueExpr === "string" && valueExpr.startsWith("$")) {
                try {
                    const reference = valueExpr.substring(1);
                    options.context.log(`Output generator: Resolving reference ${valueExpr} -> ${reference}`);
                    const resolved = this.resolveReference(reference, variables);
                    output[key] = resolved;
                    options.context.log(`Output generator: Resolved ${key} = ${typeof resolved === "string" ? resolved.substring(0, 50) + "..." : JSON.stringify(resolved).substring(0, 100)}`);
                }
                catch (error) {
                    options.context.log(`Output generator: Failed to resolve ${valueExpr}: ${error instanceof Error ? error.message : String(error)}`);
                    throw error;
                }
            }
            else {
                output[key] = valueExpr;
            }
        }
        options.context.log(`Output generator: Final output keys: ${Object.keys(output).join(", ")}`);
        return output;
    }
    /**
     * Execute Gemini Flash text helper for the joke agent
     */
    async executeGenkitJoke(step, variables, options) {
        const prompt = typeof step.action?.prompt === "string" && step.action.prompt.trim().length
            ? step.action.prompt.trim()
            : "Conte uma piada curta e original em português.";
        const temperature = typeof step.action?.temperature === "number"
            ? step.action.temperature
            : 0.8;
        const maxTokens = typeof step.action?.maxTokens === "number"
            ? step.action.maxTokens
            : undefined;
        const resultVar = typeof step.action?.result === "string" && step.action.result.length > 0
            ? step.action.result
            : "jokerResult";
        const joke = await this.callGeminiFlashText({ prompt, temperature, maxTokens }, options.props, options.context);
        variables.set(resultVar, joke);
        return joke;
    }
    /**
     * Execute translation step backed by Gemini Flash
     */
    async executeGenkitTranslation(step, variables, options) {
        const texto = options.input?.texto;
        const idiomaOrigem = options.input?.idioma_origem;
        const idiomaDestino = options.input?.idioma_destino;
        const resultVar = typeof step.action?.result === "string" && step.action.result.length > 0
            ? step.action.result
            : "translationResult";
        const translation = await this.callGeminiFlashTranslation({
            texto,
            idioma_origem: idiomaOrigem,
            idioma_destino: idiomaDestino,
            promptTemplate: typeof step.action?.promptTemplate === "string"
                ? step.action.promptTemplate
                : undefined,
        }, options.props, options.context);
        variables.set(resultVar, translation);
        return translation;
    }
    /**
     * Execute image generation step backed by Gemini Flash
     */
    async executeGenkitImage(step, variables, options) {
        const descricao = typeof options.input?.descricao === "string"
            ? options.input.descricao.trim()
            : "";
        const estilo = typeof options.input?.estilo === "string"
            ? options.input.estilo.trim()
            : "";
        const resolucaoInput = typeof options.input?.resolucao === "string"
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
        const promptTemplate = typeof step.action?.promptTemplate === "string" &&
            step.action.promptTemplate.trim().length > 0
            ? step.action.promptTemplate
            : "Gere uma imagem detalhada no estilo {{estilo}} baseada na descrição: {{descricao}}";
        const prompt = promptTemplate
            .replace(/{{descricao}}/g, descricao)
            .replace(/{{estilo}}/g, estilo)
            .trim();
        const resultVar = typeof step.action?.result === "string" && step.action.result.length > 0
            ? step.action.result
            : "imageResult";
        const imageResult = await this.callGeminiFlashImage({
            prompt,
            estilo,
            resolucao: resolucaoInput,
        }, options.props, options.context);
        variables.set(resultVar, imageResult);
        options.context.log(`Image generator: Saved result in variable '${resultVar}' with keys: ${Object.keys(imageResult).join(", ")}`);
        options.context.log(`Image generator: imageResult.image_url exists: ${!!imageResult?.image_url}`);
        return imageResult;
    }
    /**
     * Evaluate value expression
     */
    evaluateValue(expr, variables) {
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
        if (expr === "true")
            return true;
        if (expr === "false")
            return false;
        // Handle null literal
        if (expr === "null")
            return null;
        // Handle variable references
        if (expr.startsWith("$")) {
            return this.resolveReference(expr.substring(1), variables);
        }
        // Handle numbers
        if (/^-?\d+$/.test(expr))
            return parseInt(expr, 10);
        if (/^-?\d+\.\d+$/.test(expr))
            return parseFloat(expr);
        throw new Error(`Unsupported value expression: ${expr}`);
    }
    /**
     * Validate variable declaration
     */
    validateVariable(variable) {
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
    resolveReference(reference, variables) {
        const [varName, ...pathSegments] = reference.split(".");
        let value = variables.get(varName);
        if (value === undefined) {
            throw new Error(`Undefined variable referenced: ${varName}`);
        }
        for (const segment of pathSegments) {
            if (value == null || typeof value !== "object") {
                throw new Error(`Cannot resolve path '${reference}': segment '${segment}' is invalid`);
            }
            value = value[segment];
        }
        return value;
    }
    /**
     * Ensure we have a Gemini API key before calling Genkit helpers
     */
    ensureGeminiApiKey(props) {
        const apiKey = props?.gemini_api_key?.trim();
        if (!apiKey) {
            throw new Error("Missing required prop: gemini_api_key. Configure a valid Gemini API key before calling this agent.");
        }
        return apiKey;
    }
    createGeminiModel(props) {
        const apiKey = this.ensureGeminiApiKey(props);
        const google = (0, google_1.createGoogleGenerativeAI)({ apiKey });
        const model = google(this.GEMINI_MODEL);
        return model;
    }
    createGeminiImageModel(props) {
        const apiKey = this.ensureGeminiApiKey(props);
        const google = (0, google_1.createGoogleGenerativeAI)({ apiKey });
        return google.image(this.GEMINI_IMAGE_MODEL);
    }
    async callGeminiFlashText(params, props, context) {
        const prompt = params.prompt?.trim();
        if (!prompt) {
            throw new Error("Gemini Flash text helper requires a prompt");
        }
        const temperature = typeof params.temperature === "number" ? params.temperature : 0.7;
        const maxTokens = typeof params.maxTokens === "number" ? params.maxTokens : undefined;
        const model = this.createGeminiModel(props);
        const startTime = Date.now();
        try {
            context.log(`Invoking Gemini Flash text helper (temperature=${temperature}, maxTokens=${typeof maxTokens === "number" ? maxTokens : "provider-default"})`);
            const generationOptions = {
                model,
                prompt,
                temperature,
            };
            if (typeof maxTokens === "number") {
                generationOptions.maxOutputTokens = maxTokens;
            }
            const { text, content } = await (0, ai_1.generateText)(generationOptions);
            const contentText = content
                ? content
                    .map((part) => typeof part?.text === "string" ? part.text : "")
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
        }
        catch (error) {
            const message = error instanceof Error ? error.message : "Unknown Gemini Flash error";
            context.log(`Gemini Flash text helper failed: ${message}`);
            context.setError(message);
            throw error;
        }
    }
    async callGeminiFlashTranslation(params, props, context) {
        const texto = params.texto?.trim();
        const idiomaOrigem = params.idioma_origem?.trim().toLowerCase();
        const idiomaDestino = params.idioma_destino?.trim().toLowerCase();
        if (!texto || !idiomaOrigem || !idiomaDestino) {
            throw new Error("Missing required translation parameters: texto, idioma_origem, idioma_destino");
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
        const template = params.promptTemplate && params.promptTemplate.trim().length > 0
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
            context.log(`Invoking Gemini Flash translation helper (${idiomaOrigem}->${idiomaDestino})`);
            const { text, content } = await (0, ai_1.generateText)({
                model,
                prompt,
                temperature: 0.2,
            });
            const contentText = content
                ? content
                    .map((part) => typeof part?.text === "string" ? part.text : "")
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
        }
        catch (error) {
            const message = error instanceof Error ? error.message : "Unknown translation error";
            context.log(`Gemini Flash translation failed: ${message}`);
            context.setError(message);
            throw error;
        }
    }
    async callGeminiFlashImage(params, props, context) {
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
            throw new Error("Gemini Flash image helper requires uma resolução no formato LARGURAxALTURA (ex: 1024x1024)");
        }
        const model = this.createGeminiImageModel(props);
        const startTime = Date.now();
        try {
            context.log(`Invoking Gemini Flash image helper (estilo=${estilo}, resolucao=${resolucao})`);
            const result = await (0, ai_1.experimental_generateImage)({
                model,
                prompt,
                size: resolucao,
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
        }
        catch (error) {
            const message = error instanceof Error ? error.message : "Unknown image error";
            context.log(`Gemini Flash image helper failed: ${message}`);
            context.setError(message);
            throw error;
        }
    }
}
exports.DeclarativeAgentInterpreter = DeclarativeAgentInterpreter;
// Singleton instance
exports.declarativeInterpreter = new DeclarativeAgentInterpreter();
exports.default = DeclarativeAgentInterpreter;
//# sourceMappingURL=declarativeAgentRuntime.js.map