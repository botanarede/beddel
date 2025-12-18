"use strict";
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
exports.StreamingYamlParser = void 0;
exports.parseYamlStreaming = parseYamlStreaming;
exports.benchmarkStreamingComparison = benchmarkStreamingComparison;
exports.parseSecureYaml = parseSecureYaml;
const fs_1 = require("fs");
const js_yaml_1 = require("js-yaml");
const errors_1 = require("../errors");
const secure_yaml_parser_1 = require("../parser/secure-yaml-parser");
/**
 * Parser YAML com suporte a streaming para arquivos grandes
 */
class StreamingYamlParser extends secure_yaml_parser_1.SecureYamlParser {
    constructor(options = {}) {
        super(options.config);
        this.streamingOptions = {
            chunkSize: options.streaming?.chunkSize ?? 64 * 1024, // 64KB default
            maxChunkSize: options.streaming?.maxChunkSize ?? 1024 * 1024, // 1MB max
            validateChunkSize: options.streaming?.validateChunkSize ?? true,
            enableStreaming: options.streaming?.enableStreaming ?? true,
            lazyParsing: options.streaming?.lazyParsing ?? true,
            parallelProcessing: options.streaming?.parallelProcessing ?? false
        };
    }
    /**
     * Parse arquivo YAML via streaming
     */
    async parseFileStreaming(filePath) {
        if (!this.streamingOptions.enableStreaming) {
            throw new Error('Streaming desabilitado nas opções');
        }
        const stream = (0, fs_1.createReadStream)(filePath, {
            encoding: 'utf8',
            highWaterMark: this.streamingOptions.chunkSize
        });
        return this.parseStream(stream);
    }
    /**
     * Parse YAML a partir de stream
     */
    async parseStream(stream) {
        let buffer = '';
        let chunks = 0;
        let totalSize = 0;
        return new Promise((resolve, reject) => {
            const startTime = performance.now();
            stream.on('data', (chunk) => {
                buffer += chunk.toString();
                chunks++;
                totalSize += chunk.length;
                // Validação de tamanho do chunk
                if (this.streamingOptions.validateChunkSize) {
                    if (chunk.length > this.streamingOptions.maxChunkSize) {
                        reject(new errors_1.YAMLSecurityError(`Chunk ${chunks} excedeu tamanho máximo: ${chunk.length} > ${this.streamingOptions.maxChunkSize}`));
                    }
                }
            });
            stream.on('end', () => {
                try {
                    const metrics = {
                        chunks,
                        totalSize,
                        chunkSize: this.streamingOptions.chunkSize,
                        parseTime: performance.now() - startTime
                    };
                    console.log(`[StreamingYamlParser] Processamento via streaming concluído:`, metrics);
                    const result = super.parseSecure(buffer);
                    resolve(result);
                }
                catch (error) {
                    reject(error);
                }
            });
            stream.on('error', (error) => {
                reject(new errors_1.YAMLParseError(`Erro durante streaming: ${error.message}`));
            });
        });
    }
    /**
     * Parse YAML com lazy loading e streaming
     */
    async parseStreamingLazy(yamlContent) {
        if (this.streamingOptions.lazyParsing) {
            // Lazy parsing - criar Promise que só processa quando necessário
            return new Promise((resolve, reject) => {
                setTimeout(() => {
                    try {
                        const result = this.parseSecureChunked(yamlContent);
                        resolve(result);
                    }
                    catch (error) {
                        reject(error);
                    }
                }, 0);
            });
        }
        else {
            return this.parseSecureChunked(yamlContent);
        }
    }
    /**
     * Parse YAML em chunks para não bloquear o event loop
     */
    async parseSecureChunked(yamlContent, chunkSize) {
        const effectiveChunkSize = chunkSize ?? this.streamingOptions.chunkSize;
        const chunks = [];
        let position = 0;
        while (position < yamlContent.length) {
            const endPosition = Math.min(position + effectiveChunkSize, yamlContent.length);
            chunks.push(yamlContent.slice(position, endPosition));
            position = endPosition;
            // Permitir que o event loop processe outros eventos
            if (position < yamlContent.length) {
                await new Promise(resolve => setImmediate(resolve));
            }
        }
        // Juntar todos os chunks e processar como um único documento
        const completeContent = chunks.join('');
        return super.parseSecure(completeContent);
    }
    /**
     * Parser otimizado para streams de entrada com configurações pré-definidas
     */
    async parseStreamOptimized(content) {
        if (typeof content === 'string') {
            return this.parseStreamingLarge(content);
        }
        else {
            return this.parseStream(content);
        }
    }
    /**
     * Otimização para arquivos grandes (> 1MB)
     */
    async parseStreamingLarge(content) {
        const startTime = performance.now();
        if (content.length < 1024 * 1024) {
            // Para arquivos pequenos, usar parsing direto
            return super.parseSecure(content);
        }
        // Para arquivos grandes, usar parsing segmentado
        let segments = this.segmentLargeContent(content);
        const results = [];
        if (this.streamingOptions.parallelProcessing) {
            // Processamento paralelo de segmentos (experimental)
            results.push(...await Promise.all(segments.map(segment => this.parseSegmentAsync(segment))));
        }
        else {
            // Processamento sequencial (mais seguro para YAML)
            for (const segment of segments) {
                results.push(await this.parseSegmentAsync(segment));
            }
        }
        const endTime = performance.now();
        console.log(`[StreamingYamlParser] Arquivo grande processado: ${content.length} bytes em ${endTime - startTime}ms`);
        return this.mergeResults(results);
    }
    /**
     * Segmenta conteúdo grande em partes manejáveis
     */
    segmentLargeContent(content) {
        const segmentSize = Math.floor(content.length / 4); // Dividir em 4 partes
        const segments = [];
        for (let i = 0; i < content.length; i += segmentSize) {
            segments.push(content.slice(i, Math.min(i + segmentSize, content.length)));
        }
        return segments;
    }
    /**
     * Processa segmento de forma assíncrona
     */
    async parseSegmentAsync(segment) {
        return new Promise((resolve, reject) => {
            setTimeout(() => {
                try {
                    const result = (0, js_yaml_1.load)(segment, { schema: js_yaml_1.FAILSAFE_SCHEMA });
                    resolve(result);
                }
                catch (error) {
                    reject(new errors_1.YAMLParseError(`Erro ao processar segmento: ${error}`));
                }
            }, 0);
        });
    }
    /**
     * Merge resultados de múltiplos segmentos (simplificado)
     */
    mergeResults(results) {
        if (results.length === 1)
            return results[0];
        // Para YAML simples, retornar o primeiro resultado completo
        // Isso é uma simplificação - YAML completo requer lógica mais complexa
        return results.find(result => result !== null && result !== undefined) ?? null;
    }
    /**
     * Wrapper com monitoramento de performance para parsing de arquivos grandes
     */
    async parseFileWithMonitoring(filePath) {
        const startTime = performance.now();
        const startMemory = process.memoryUsage();
        try {
            const result = await this.parseFileStreaming(filePath);
            const endTime = performance.now();
            const endMemory = process.memoryUsage();
            const metrics = {
                parseTime: endTime - startTime,
                memoryUsage: endMemory.heapUsed - startMemory.heapUsed,
                fileSize: (await Promise.resolve().then(() => __importStar(require('fs')))).statSync(filePath).size,
                chunksProcessed: Math.ceil((await Promise.resolve().then(() => __importStar(require('fs')))).statSync(filePath).size / this.streamingOptions.chunkSize),
                streaming: true,
                timestamp: Date.now()
            };
            return { result, metrics };
        }
        catch (error) {
            throw error;
        }
    }
}
exports.StreamingYamlParser = StreamingYamlParser;
/**
 * Wrapper para parsing com streaming
 */
async function parseYamlStreaming(content, config) {
    const parser = new StreamingYamlParser(config);
    if (typeof content === 'string') {
        return parser.parseStreamingLazy(content);
    }
    else {
        return parser.parseStream(content);
    }
}
/**
 * Benchmark compartivo entre parsing normal e streaming
 */
async function benchmarkStreamingComparison(content, iterations = 100) {
    const { PerformanceMonitor } = await Promise.resolve().then(() => __importStar(require('./monitor')));
    const monitor = new PerformanceMonitor();
    // Normal parser benchmark
    const normalResult = await monitor.benchmark(() => parseSecureYaml(content), 'Normal Parser', iterations, content.length);
    // Streaming parser benchmark
    const streamingResult = await monitor.benchmark(() => {
        const parser = new StreamingYamlParser({ streaming: { enableStreaming: true } });
        return parser.parseStreamingLazy(content);
    }, 'Streaming Parser', iterations, content.length);
    return { normal: normalResult, streaming: streamingResult };
}
// Import dinâmico para evitar circular dependencies
async function parseSecureYaml(content) {
    const { parseSecureYaml } = await Promise.resolve().then(() => __importStar(require('../parser/secure-yaml-parser')));
    return parseSecureYaml(content);
}
//# sourceMappingURL=streaming.js.map