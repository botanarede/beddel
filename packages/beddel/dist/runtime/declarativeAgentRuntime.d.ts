/**
 * Declarative Agent Runtime - YAML Interpreter for Beddel Declarative Protocol
 * Safely interprets declarative YAML agent definitions without dynamic code execution
 */
import { ExecutionContext } from "../types/executionContext";
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
export declare class DeclarativeAgentInterpreter {
    private readonly MAX_VARIABLE_SIZE;
    private readonly MAX_WORKFLOW_STEPS;
    private readonly MAX_OUTPUT_SIZE;
    private readonly GEMINI_MODEL;
    private readonly GEMINI_IMAGE_MODEL;
    private readonly SUPPORTED_TRANSLATION_LANGUAGES;
    private readonly schemaCompiler;
    /**
     * Interpret declarative YAML agent definition
     */
    interpret(options: YamlAgentInterpreterOptions): Promise<YamlExecutionResult>;
    /**
     * Parse and validate YAML content
     */
    private parseYaml;
    /**
     * Validate agent definition structure
     */
    private validateAgentDefinition;
    private buildSchemaSet;
    private validateAgainstSchema;
    private enforceOutputSize;
    /**
     * Execute declarative workflow
     */
    private executeWorkflow;
    /**
     * Execute single workflow step
     */
    private executeWorkflowStep;
    /**
     * Execute output generator step
     */
    private executeOutputGenerator;
    /**
     * Execute Gemini Flash text helper for the joke agent
     */
    private executeGenkitJoke;
    /**
     * Execute translation step backed by Gemini Flash
     */
    private executeGenkitTranslation;
    /**
     * Execute image generation step backed by Gemini Flash
     */
    private executeGenkitImage;
    /**
     * Evaluate value expression
     */
    private evaluateValue;
    /**
     * Validate variable declaration
     */
    private validateVariable;
    /**
     * Resolve variable reference, including nested properties (e.g., foo.bar.baz)
     */
    private resolveReference;
    /**
     * Ensure we have a Gemini API key before calling Genkit helpers
     */
    private ensureGeminiApiKey;
    private createGeminiModel;
    private createGeminiImageModel;
    private callGeminiFlashText;
    private callGeminiFlashTranslation;
    private callGeminiFlashImage;
}
export declare const declarativeInterpreter: DeclarativeAgentInterpreter;
export default DeclarativeAgentInterpreter;
//# sourceMappingURL=declarativeAgentRuntime.d.ts.map