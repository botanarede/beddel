#!/usr/bin/env node

import { runPerformanceBenchmark, generatePerformanceReport } from './src/performance/benchmark';

/**
 * Demonstração de performance do SecureYamlParser
 * 
 * Executa benchmarks comparativos e gera relatórios detalhados
 */

async function main() {
  console.log('🚀 Beddel Secure YAML Parser - Performance Demo');
  console.log('=' .repeat(60) + '\n');

  try {
    // 1. Benchmark padrão com configurações básicas
    console.log('📊 Executando benchmark padrão com 100 iterações...');
    const standardResults = await runPerformanceBenchmark({
      iterations: 100,
      scenarios: ['all'],
      enableStreaming: true,
      enableLazyLoading: true,
      parallelProcessing: false
    });

    console.log(`\n✅ Benchmark concluído - ${Object.keys(standardResults).length} cenários executados`);

    // 2. Comparação entre configuracões
    console.log('\n🔍 Comparando configurações de performance...');
    
    const comparisons = await compareConfigurations({
      content: generateTestContent(),
      configs: ['normal', 'streaming', 'lazy'],
      iterations: 50
    });

    console.log('\n📈 Resultados da comparação de configurações:');
    for (const [config, result] of Object.entries(comparisons)) {
      console.log(`   ${config.toUpperCase()}: ${result.avgTime.toFixed(2)}ms média - ${result.pass ? '✅ PASS' : '❌ FAIL'}`);
    }

    // 3. Gerar relatório detalhado
    console.log('\n📝 Gerando relatório de performance detalhado...');
    const report = await generatePerformanceReport('complex_doc', 100);
    console.log('\n📋 Relatório JSON gerado (excerto):');
    console.log(report.substring(0, 500) + '...\n');

    // 4. Teste de performance com diferentes tamanhos
    console.log('⚡ Executando testes de performance com diferentes tamanhos...');
    const sizeResults = await benchmarkBySize();

    console.table(sizeResults);

    // 5. Verificação final
    console.log('\n🎯 Resumo final de performance:');
    const summary = generateSummary(standardResults, comparisons, sizeResults);
    console.log(summary);

    console.log('\n🎉 Demo de performance concluído com sucesso!');
    console.log('📊 Para exportar relatórios completos, use os comandos:');
    console.log('   - Gerar JSON: NODE_ENV=prod node dist/benchmark-demo.js --format json');
    console.log('   - Gerar CSV: NODE_ENV=prod node dist/benchmark-demo.js --format csv');

  } catch (error) {
    console.error('❌ Erro durante benchmark:', error);
    process.exit(1);
  }
}

/**
 * Compara diferentes configurações de performance
 */
async function compareConfigurations(options: {
  content: string;
  configs: string[];
  iterations: number;
}): Promise<{ [key: string]: any }> {
  const { BenchmarkRunner } = await import('./src/performance/benchmark');
  
  const results: { [key: string]: any } = {};

  for (const config of options.configs) {
    const runner = new BenchmarkRunner({
      iterations: options.iterations,
      scenarios: ['performance_stress'],
      enableStreaming: config === 'streaming' || config === 'lazy',
      enableLazyLoading: config === 'lazy',
      parallelProcessing: config === 'parallel',
      outputFormat: 'console'
    });

    const result = await runner.runBenchmark();
    results[config] = result['performance_stress'];
  }

  return results;
}

/**
 * Benchmark por tamanho de conteúdo
 */
async function benchmarkBySize(): Promise<any[]> {
  const sizes = [
    { name: 'small', size: 1000, content: smallContent() },
    { name: 'medium', size: 10000, content: mediumContent() },
    { name: 'large', size: 50000, content: largeContent() }
  ];

  const results: any[] = [];

  for (const size of sizes) {
    const start = Date.now();
    const { PerformanceMonitor } = await import('./src/performance/monitor');
    const monitor = new PerformanceMonitor();

    const result = await monitor.benchmark(
      async () => {
        const { parseSecureYaml } = await import('./src/parser/secure-yaml-parser');
        return parseSecureYaml(size.content);
      },
      `${size.name}_size`,
      50,
      size.size
    );

    results.push({
      Tamanho: size.name,
      'Conteúdo (bytes)': size.size,
      'Tempo médio (ms)': result.avgTime.toFixed(2),
      'Memória (KB)': (Math.abs(result.memoryAvg) / 1024).toFixed(2),
      'Throughput (bytes/ms)': result.throughput.toFixed(2),
      'Status': result.pass ? '✅ PASS' : '❌ FAIL'
    });
  }

  return results;
}

/**
 * Gera conteúdo de teste
 */
function generateTestContent(): string {
  return `benchmark:
  iterations: 500
  metrics:
    cpu: 65.3
    memory: 78.9
    disk: 42.1
  configuration:
    enabled: true
    mode: "performance"
    target: "100ms"`;
}

function smallContent(): string {
  return `test: true`;
}

function mediumContent(): string {
  return `data:
  users:
    - id: 1
      name: "User 1"
      active: true
    - id: 2
      name: "User 2"
      active: false
  settings:
    theme: "dark"
    notifications: enabled`;
}

function largeContent(): string {
  return `application:
  name: "Large App"
  version: "1.0.0"
  modules:
    - name: "user"
      enabled: true
      features: [login, register, profile]
    - name: "admin"
      enabled: true
      features: [dashboard, users, reports]
    - name: "api"
      enabled: true
      features: [graphql, rest, websocket]
  configuration:
    database:
      host: "localhost"
      port: 5432
      name: "appdb"
    cache:
      enabled: true
      type: "redis"
      ttl: 3600
    security:
      cors: true
      rates:
        limit: 100
        window: "15m"
      auth:
        method: "jwt"
        expiry: "24h"`;
}

/**
 * Gera resumo dos resultados
 */
function generateSummary(
  standardResults: any,
  comparisons: any,
  sizeResults: any[]
): string {
  const passedTests = Object.values(standardResults).filter((r: any) => r.pass).length;
  const totalTests = Object.keys(standardResults).length;
  const passRate = (passedTests / totalTests * 100).toFixed(1);
  
  const configComparison = Object.entries(comparisons).map(([name, result]: [string, any]) => 
    `${name.toUpperCase()}: ${result.avgTime.toFixed(1)}ms`
  ).join(', ');

  return `
Total de testes: ${totalTests}
Testes aprovados: ${passedTests} (${passRate}%)
Configurações comparadas: ${configComparison}
Média de tempos por tamanho:
- Pequeno: ${sizeResults.find(r => r.Tamanho === 'small')?.['Tempo médio (ms)']}ms
- Médio: ${sizeResults.find(r => r.Tamanho === 'medium')?.['Tempo médio (ms)']}ms  
- Grande: ${sizeResults.find(r => r.Tamanho === 'large')?.['Tempo médio (ms)']}ms
  `.trim();
}

// Executar se chamado diretamente
if (require.main === module) {
  main().catch(console.error);
}
