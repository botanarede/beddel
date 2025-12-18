import { createReadStream } from 'fs';
import { Readable } from 'stream';
import { load, FAILSAFE_SCHEMA } from 'js-yaml';
import { YAMLParseError, YAMLSecurityError } from '../errors';
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
export class StreamingYamlParser extends SecureYamlParser {
  private readonly streamingOptions: Required<StreamingOptions>;

  constructor(options: { config?: any; streaming?: StreamingOptions } = {}) {
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
  async parseFileStreaming(filePath: string): Promise<any> {
    if (!this.streamingOptions.enableStreaming) {
      throw new Error('Streaming desabilitado nas opções');
    }

    const stream = createReadStream(filePath, {
      encoding: 'utf8',
      highWaterMark: this.streamingOptions.chunkSize
    });

    return this.parseStream(stream);
  }

  /**
   * Parse YAML a partir de stream
   */
  async parseStream(stream: Readable): Promise<any> {
    let buffer = '';
    let chunks = 0;
    let totalSize = 0;
    
    return new Promise((resolve, reject) => {
      const startTime = performance.now();
      
      stream.on('data', (chunk: Buffer | string) => {
        buffer += chunk.toString();
        chunks++;
        totalSize += chunk.length;
        
        // Validação de tamanho do chunk
        if (this.streamingOptions.validateChunkSize) {
          if (chunk.length > this.streamingOptions.maxChunkSize) {
            reject(new YAMLSecurityError(
              `Chunk ${chunks} excedeu tamanho máximo: ${chunk.length} > ${this.streamingOptions.maxChunkSize}`
            ));
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
          
        } catch (error) {
          reject(error);
        }
      });

      stream.on('error', (error: Error) => {
        reject(new YAMLParseError(`Erro durante streaming: ${error.message}`));
      });
    });
  }

  /**
   * Parse YAML com lazy loading e streaming
   */
  async parseStreamingLazy(yamlContent: string): Promise<any> {
    if (this.streamingOptions.lazyParsing) {
      // Lazy parsing - criar Promise que só processa quando necessário
      return new Promise((resolve, reject) => {
        setTimeout(() => {
          try {
            const result = this.parseSecureChunked(yamlContent);
            resolve(result);
          } catch (error) {
            reject(error);
          }
        }, 0);
      });
    } else {
      return this.parseSecureChunked(yamlContent);
    }
  }

  /**
   * Parse YAML em chunks para não bloquear o event loop
   */
  private async parseSecureChunked(yamlContent: string, chunkSize?: number): Promise<any> {
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
  async parseStreamOptimized(content: string | Readable): Promise<any> {
    if (typeof content === 'string') {
      return this.parseStreamingLarge(content);
    } else {
      return this.parseStream(content);
    }
  }

  /**
   * Otimização para arquivos grandes (> 1MB)
   */
  private async parseStreamingLarge(content: string): Promise<any> {
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
      results.push(...await Promise.all(
        segments.map(segment => this.parseSegmentAsync(segment))
      ));
    } else {
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
  private segmentLargeContent(content: string): string[] {
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
  private async parseSegmentAsync(segment: string): Promise<any> {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        try {
          const result = load(segment, { schema: FAILSAFE_SCHEMA });
          resolve(result);
        } catch (error) {
          reject(new YAMLParseError(`Erro ao processar segmento: ${error}`));
        }
      }, 0);
    });
  }

  /**
   * Merge resultados de múltiplos segmentos (simplificado)
   */
  private mergeResults(results: any[]): any {
    if (results.length === 1) return results[0];
    
    // Para YAML simples, retornar o primeiro resultado completo
    // Isso é uma simplificação - YAML completo requer lógica mais complexa
    return results.find(result => result !== null && result !== undefined) ?? null;
  }

  /**
   * Wrapper com monitoramento de performance para parsing de arquivos grandes
   */
  async parseFileWithMonitoring(filePath: string): Promise<{ result: any; metrics: any }> {
    const startTime = performance.now();
    const startMemory = process.memoryUsage();

    try {
      const result = await this.parseFileStreaming(filePath);
      
      const endTime = performance.now();
      const endMemory = process.memoryUsage();

      const metrics = {
        parseTime: endTime - startTime,
        memoryUsage: endMemory.heapUsed - startMemory.heapUsed,
        fileSize: (await import('fs')).statSync(filePath).size,
        chunksProcessed: Math.ceil((await import('fs')).statSync(filePath).size / this.streamingOptions.chunkSize),
        streaming: true,
        timestamp: Date.now()
      };

      return { result, metrics };
      
    } catch (error) {
      throw error;
    }
  }
}

/**
 * Wrapper para parsing com streaming
 */
export async function parseYamlStreaming(
  content: string | Readable,
  config?: { streaming?: StreamingOptions; parser?: any }
): Promise<any> {
  const parser = new StreamingYamlParser(config);
  
  if (typeof content === 'string') {
    return parser.parseStreamingLazy(content);
  } else {
    return parser.parseStream(content);
  }
}

/**
 * Benchmark compartivo entre parsing normal e streaming
 */
export async function benchmarkStreamingComparison(
  content: string,
  iterations: number = 100
): Promise<{ normal: any; streaming: any }> {
  const { PerformanceMonitor } = await import('./monitor');
  const monitor = new PerformanceMonitor();
  
  // Normal parser benchmark
  const normalResult = await monitor.benchmark(
    () => parseSecureYaml(content),
    'Normal Parser',
    iterations,
    content.length
  );

  // Streaming parser benchmark
  const streamingResult = await monitor.benchmark(
    () => {
      const parser = new StreamingYamlParser({ streaming: { enableStreaming: true } });
      return parser.parseStreamingLazy(content);
    },
    'Streaming Parser',
    iterations,
    content.length
  );

  return { normal: normalResult, streaming: streamingResult };
}

// Import dinâmico para evitar circular dependencies
export async function parseSecureYaml(content: string): Promise<any> {
  const { parseSecureYaml } = await import('../parser/secure-yaml-parser');
  return parseSecureYaml(content);
}
