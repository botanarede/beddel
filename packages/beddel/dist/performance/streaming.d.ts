import { Readable } from 'stream';
import { SecureYamlParser } from '../parser/secure-yaml-parser';
/**
 * Interface para opções de streaming
 */
export interface StreamingOptions {
    chunkSize?: number;
    maxChunkSize?: number;
    validateChunkSize?: boolean;
    enableStreaming?: boolean;
    lazyParsing?: boolean;
    parallelProcessing?: boolean;
}
/**
 * Parser YAML com suporte a streaming para arquivos grandes
 */
export declare class StreamingYamlParser extends SecureYamlParser {
    private readonly streamingOptions;
    constructor(options?: {
        config?: any;
        streaming?: StreamingOptions;
    });
    /**
     * Parse arquivo YAML via streaming
     */
    parseFileStreaming(filePath: string): Promise<any>;
    /**
     * Parse YAML a partir de stream
     */
    parseStream(stream: Readable): Promise<any>;
    /**
     * Parse YAML com lazy loading e streaming
     */
    parseStreamingLazy(yamlContent: string): Promise<any>;
    /**
     * Parse YAML em chunks para não bloquear o event loop
     */
    private parseSecureChunked;
    /**
     * Parser otimizado para streams de entrada com configurações pré-definidas
     */
    parseStreamOptimized(content: string | Readable): Promise<any>;
    /**
     * Otimização para arquivos grandes (> 1MB)
     */
    private parseStreamingLarge;
    /**
     * Segmenta conteúdo grande em partes manejáveis
     */
    private segmentLargeContent;
    /**
     * Processa segmento de forma assíncrona
     */
    private parseSegmentAsync;
    /**
     * Merge resultados de múltiplos segmentos (simplificado)
     */
    private mergeResults;
    /**
     * Wrapper com monitoramento de performance para parsing de arquivos grandes
     */
    parseFileWithMonitoring(filePath: string): Promise<{
        result: any;
        metrics: any;
    }>;
}
/**
 * Wrapper para parsing com streaming
 */
export declare function parseYamlStreaming(content: string | Readable, config?: {
    streaming?: StreamingOptions;
    parser?: any;
}): Promise<any>;
/**
 * Benchmark compartivo entre parsing normal e streaming
 */
export declare function benchmarkStreamingComparison(content: string, iterations?: number): Promise<{
    normal: any;
    streaming: any;
}>;
export declare function parseSecureYaml(content: string): Promise<any>;
//# sourceMappingURL=streaming.d.ts.map