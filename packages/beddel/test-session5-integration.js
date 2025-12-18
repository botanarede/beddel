/**
 * Sessão 5 - Testes de Integração e Validação
 *
 * Testes para validar:
 * - Integração entre SecureYamlParser e IsolatedRuntime
 * - Isolamento multi-inquilino
 * - Performance targets (<50ms, <2MB)
 * - Segurança em ambientes multi-inquilino
 */

const { SecureYamlRuntime, runtimeManager } = require("./dist/index.js");
const crypto = require("crypto");

console.log("🎯 [Sessão 5] Iniciando testes de integração e validação...\n");

// Helper para gerar YAML de teste
function generateTestYaml(tenantId, complexity = "simple") {
  const configs = {
    simple: `
config:
  tenant: ${tenantId}
  version: "1.0"
  enabled: true
  timeout: 5000
user:
  name: user_${tenantId}
  role: admin
  lastLogin: 2023-01-01T00:00:00Z
settings:
  theme: dark
  language: pt-BR
  notifications: true
`,
    complex: `
system:
  tenant: ${tenantId}
  version: "2.0"
  features:
    - analytics
    - reporting
    - automation
    - multi_region
  regions:
    - sa-east-1
    - us-east-1
    - eu-west-1
  limits:
    users: 1000
    storage: 1073741824
    requests_per_minute: 60000
security:
  encryption: AES-256-GCM
  authentication: OAuth2.0
  multi_factor: true
  session_timeout: 3600
database:
  type: postgresql
  version: "14"
  pool_size: 50
  timeout: 30000
  backup:
    enabled: true
    frequency: daily
    retention: 30
cache:
  type: redis
  cluster: enabled
  memory: 1073741824
monitoring:
  metrics: enabled
  logs: enabled
  alerts: enabled
api:
  version: v3
  rate_limit: 1000/hour
  auth: Bearer
  cors:
    enabled: true
    origins:
      - "https://app.${tenantId}.com"
      - "https://admin.${tenantId}.com"
`,
  };

  return configs[complexity] || configs.simple;
}

// Test 1: Integração básica Runtime + YAML Parser
async function testBasicIntegration() {
  console.log(
    "🧪 Teste 1: Integração básica entre Runtime Isolado e YAML Parser"
  );

  try {
    const secureYamlRuntime = new SecureYamlRuntime(runtimeManager);
    const testYaml = generateTestYaml("tenant_test");

    const result = await secureYamlRuntime.parseYamlSecureRuntime(testYaml, {
      securityProfile: "ultra-secure",
      validateSecurity: true,
      auditEnabled: true,
    });

    console.log("✅ Integração básica executada com sucesso");
    console.log(`   - Sucesso: ${result.success}`);
    console.log(`   - Tempo de execução: ${result.executionTime.toFixed(2)}ms`);
    console.log(`   - Memória usada: ${result.memoryUsed.toFixed(2)}MB`);
    console.log(`   - Pontuação de segurança: ${result.securityScore}/10`);
    console.log(`   - Resultado: ${JSON.stringify(result.result, null, 2)}`);

    // Validações
    if (result.executionTime > 50) {
      console.log(
        `⚠️  Warning: Tempo de execução (${result.executionTime.toFixed(
          2
        )}ms) excede o target de 50ms`
      );
    }

    if (result.memoryUsed > 2) {
      console.log(
        `⚠️  Warning: Uso de memória (${result.memoryUsed.toFixed(
          2
        )}MB) excede o target de 2MB`
      );
    }

    if (result.securityScore < 9.5) {
      console.log(
        `⚠️  Warning: Pontuação de segurança (${result.securityScore}) abaixo do target de 9.5`
      );
    }

    return {
      success: result.success,
      executionTime: result.executionTime,
      memoryUsed: result.memoryUsed,
      securityScore: result.securityScore,
    };
  } catch (error) {
    console.log("❌ Falha no teste de integração:", error.message);
    return { success: false, error: error.message };
  }
  console.log("");
}

// Test 2: Teste de isolamento multi-inquilino
async function testMultiTenantIsolation() {
  console.log("🧪 Teste 2: Isolamento multi-inquilino");

  try {
    const secureYamlRuntime = new SecureYamlRuntime(runtimeManager);
    const tenantIds = ["tenant_a", "tenant_b", "tenant_c"];

    // Testar cada tenant
    const results = {};

    for (const tenantId of tenantIds) {
      const testYaml = generateTestYaml(tenantId);

      const result = await secureYamlRuntime.parseYamlMultiTenant(
        testYaml,
        tenantId,
        {
          securityProfile: "tenant-isolated",
          validateSecurity: true,
        }
      );

      results[tenantId] = {
        success: result.success,
        executionTime: result.executionTime,
        memoryUsed: result.memoryUsed,
        result: result.result,
      };

      console.log(`✅ Tenant ${tenantId} processado: ${result.success}`);
    }

    // Verificar isolamento
    const isolationResults = await secureYamlRuntime.testTenantIsolation(
      tenantIds
    );

    console.log("📊 Resultados de isolamento:");
    for (const [tenant, isolated] of Object.entries(isolationResults)) {
      console.log(`   - ${tenant}: ${isolated ? "ISOLADO" : "NÃO ISOLADO"}`);
    }

    console.log("✅ Teste de isolamento multi-inquilino concluído");
    return results;
  } catch (error) {
    console.log("❌ Falha no teste de isolamento:", error.message);
    return { success: false, error: error.message };
  }
  console.log("");
}

// Test 3: Processamento em lote multi-inquilino
async function testBatchProcessing() {
  console.log("🧪 Teste 3: Processamento em lote multi-inquilino");

  try {
    const secureYamlRuntime = new SecureYamlRuntime(runtimeManager);
    const tenantData = [];

    // Gerar dados para múltiplos tenants
    for (let i = 1; i <= 10; i++) {
      tenantData.push({
        content: generateTestYaml(
          `tenant_${i}`,
          i % 2 === 0 ? "complex" : "simple"
        ),
        tenantId: `tenant_${i}`,
      });
    }

    const startTime = Date.now();
    const results = await secureYamlRuntime.parseYamlBatch(tenantData, {
      validateSecurity: true,
    });
    const endTime = Date.now();
    const totalTime = endTime - startTime;

    console.log(`✅ Processamento em lote concluído em ${totalTime}ms`);
    console.log(`   - Total de tenants processados: ${results.size}`);
    console.log(
      `   - Tempo médio por tenant: ${(totalTime / results.size).toFixed(2)}ms`
    );

    // Analisar resultados
    let successCount = 0;
    let totalExecutionTime = 0;
    let totalMemoryUsed = 0;

    for (const [tenantId, result] of results) {
      if (result.success) {
        successCount++;
        totalExecutionTime += result.executionTime;
        totalMemoryUsed += result.memoryUsed;
      }
      console.log(
        `   - ${tenantId}: ${
          result.success ? "✅" : "❌"
        } (${result.executionTime.toFixed(2)}ms, ${result.memoryUsed.toFixed(
          2
        )}MB)`
      );
    }

    const avgExecutionTime = totalExecutionTime / successCount;
    const avgMemoryUsed = totalMemoryUsed / successCount;

    console.log(`📊 Estatísticas gerais:`);
    console.log(
      `   - Taxa de sucesso: ${((successCount / results.size) * 100).toFixed(
        1
      )}%`
    );
    console.log(
      `   - Tempo médio de execução: ${avgExecutionTime.toFixed(2)}ms`
    );
    console.log(`   - Memória média usada: ${avgMemoryUsed.toFixed(2)}MB`);

    return {
      success: true,
      totalTenants: results.size,
      successCount,
      totalTime,
      avgExecutionTime,
      avgMemoryUsed,
    };
  } catch (error) {
    console.log("❌ Falha no teste de processamento em lote:", error.message);
    return { success: false, error: error.message };
  }
  console.log("");
}

// Test 4: Validação de performance targets
async function testPerformanceTargets() {
  console.log("🧪 Teste 4: Validação de performance targets (<50ms, <2MB)");

  const targets = {
    executionTime: { target: 50, unit: "ms" },
    memoryUsage: { target: 2, unit: "MB" },
  };

  let testsPassed = 0;
  let totalTests = 100; // Executar 100 testes para ter uma amostra estatística

  const stats = {
    executionTimes: [],
    memoryUsages: [],
  };

  try {
    const secureYamlRuntime = new SecureYamlRuntime(runtimeManager);

    for (let i = 0; i < totalTests; i++) {
      const tenantId = `tenant_perf_${i}`;
      const testYaml = generateTestYaml(
        tenantId,
        i % 3 === 0 ? "complex" : "simple"
      );

      const result = await secureYamlRuntime.parseYamlSecureRuntime(testYaml, {
        securityProfile: "ultra-secure",
        timeout: 5000, // Garantir que o timeout não afete o resultado
      });

      if (result.success) {
        stats.executionTimes.push(result.executionTime);
        stats.memoryUsages.push(result.memoryUsed);
      }
    }

    // Calcular estatísticas
    const avgExecutionTime =
      stats.executionTimes.reduce((a, b) => a + b, 0) /
      stats.executionTimes.length;
    const maxExecutionTime = Math.max(...stats.executionTimes);
    const minExecutionTime = Math.min(...stats.executionTimes);

    const avgMemoryUsage =
      stats.memoryUsages.reduce((a, b) => a + b, 0) / stats.memoryUsages.length;
    const maxMemoryUsage = Math.max(...stats.memoryUsages);

    console.log(
      `📊 Estatísticas de performance (${stats.executionTimes.length} testes válidos):`
    );
    console.log(`   Execution Time:`);
    console.log(
      `     - Média: ${avgExecutionTime.toFixed(2)}ms (target: ${
        targets.executionTime.target
      }ms)`
    );
    console.log(`     - Máximo: ${maxExecutionTime.toFixed(2)}ms`);
    console.log(`     - Mínimo: ${minExecutionTime.toFixed(2)}ms`);
    console.log(`   Memory Usage:`);
    console.log(
      `     - Média: ${avgMemoryUsage.toFixed(2)}MB (target: ${
        targets.memoryUsage.target
      }MB)`
    );
    console.log(`     - Máximo: ${maxMemoryUsage.toFixed(2)}MB`);

    // Validar targets
    if (avgExecutionTime <= targets.executionTime.target) {
      console.log(`✅ Target de execution time atingido!`);
      testsPassed++;
    } else {
      console.log(`⚠️  Target de execution time NÃO atingido!`);
    }

    if (avgMemoryUsage <= targets.memoryUsage.target) {
      console.log(`✅ Target de memory usage atingido!`);
      testsPassed++;
    } else {
      console.log(`⚠️  Target de memory usage NÃO atingido!`);
    }

    console.log(
      `✅ Teste de performance targets concluído: ${testsPassed}/${
        Object.keys(targets).length
      } targets atingidos`
    );

    return {
      stats,
      targets,
      testsPassed,
      targetsMet: testsPassed === Object.keys(targets).length,
    };
  } catch (error) {
    console.log("❌ Falha no teste de performance targets:", error.message);
    return { success: false, error: error.message };
  }
  console.log("");
}

// Test 5: Teste de segurança completa
async function testSecurityValidation() {
  console.log("🧪 Teste 5: Validação completa de segurança (Score 9.5/10)");

  let securityScore = 0;
  const maxScore = 10;

  const secureYamlRuntime = new SecureYamlRuntime(runtimeManager);

  // 1. Testar injeção de código malicioso
  console.log("   Testando injeção de código malicioso...");
  const maliciousYaml = `
    name: test
    value: injected'; console.log('hacked');
  `;

  try {
    await secureYamlRuntime.parseYamlSecureRuntime(maliciousYaml);
    console.log("   ⚠️  Código malicioso foi aceito (perigo!)");
  } catch (error) {
    console.log("   ✅ Código malicioso bloqueado");
    securityScore += 2;
  }

  // 2. Testar memory exhaustion
  console.log("   Testando proteção contra memory exhaustion...");
  const hugeYaml = "key: " + "x".repeat(10 * 1024 * 1024); // 10MB

  try {
    await secureYamlRuntime.parseYamlSecureRuntime(hugeYaml);
    console.log("   ⚠️  Memory exhaustion não foi bloqueada");
  } catch (error) {
    console.log("   ✅ Memory exhaustion bloqueada");
    securityScore += 2;
  }

  // 3. Testar profundidade máxima
  console.log("   Testando limite de profundidade...");
  const deepYaml = Array(1000).fill("level: {").join("");

  try {
    await secureYamlRuntime.parseYamlSecureRuntime(deepYaml);
    console.log("   ⚠️  Profundidade não foi limitada");
  } catch (error) {
    console.log("   ✅ Profundidade limitada corretamente");
    securityScore += 1.5;
  }

  // 4. Testar integridade de dados
  console.log("   Testando integridade de dados...");
  const testData = { test: true, value: 42, text: "secure" };
  const testYaml = `
    test: true
    value: 42
    text: secure
  `;

  const result = await secureYamlRuntime.parseYamlSecureRuntime(testYaml);
  if (
    result.success &&
    result.result &&
    JSON.stringify(result.result).includes("true") &&
    JSON.stringify(result.result).includes("42")
  ) {
    console.log("   ✅ Dados mantiveram integridade");
    securityScore += 2;
  } else {
    console.log("   ⚠️  Dados perderam integridade");
  }

  // 5. Testar auditoria
  console.log("   Testando sistema de auditoria...");
  const auditTestYaml = "audit: test";
  const auditResult = await secureYamlRuntime.parseYamlSecureRuntime(
    auditTestYaml,
    {
      auditEnabled: true,
      tenantId: "audit_tenant",
    }
  );

  if (auditResult.success && auditResult.auditHash) {
    console.log("   ✅ Auditoria funcionando corretamente");
    securityScore += 1.5;
  } else {
    console.log("   ⚠️  Auditoria não funcionando");
  }

  // Calcular score final
  const finalScore = Math.min(maxScore, securityScore);
  const passed = finalScore >= 9.5;

  console.log(`📊 Pontuação de segurança: ${finalScore}/${maxScore}`);
  console.log(`   Target: 9.5/10 → ${passed ? "✅ APROVADO" : "❌ REPROVADO"}`);

  return {
    score: finalScore,
    maxScore,
    passed,
    percentage: (finalScore / maxScore) * 100,
  };
}

// Função principal para executar todos os testes
async function runAllTests() {
  console.log("🎯 ===== INICIANDO TESTES DA SESSÃO 5 =====");
  console.log("🔄 Testes de integração, segurança e performance\n");

  const startTime = Date.now();
  const results = {};

  try {
    // Executar todos os testes
    results.basicIntegration = await testBasicIntegration();
    results.multiTenantIsolation = await testMultiTenantIsolation();
    results.batchProcessing = await testBatchProcessing();
    results.performanceTargets = await testPerformanceTargets();
    results.securityValidation = await testSecurityValidation();

    const endTime = Date.now();
    const totalTime = ((endTime - startTime) / 1000).toFixed(2);

    console.log("🎯 ===== RELATÓRIO FINAL DA SESSÃO 5 =====");
    console.log(`Tempo total de execução: ${totalTime}s`);

    // Resumo dos resultados
    const summary = {
      basicIntegration: results.basicIntegration.success !== false,
      multiTenantIsolation:
        typeof results.multiTenantIsolation === "object" &&
        !results.multiTenantIsolation.success !== false,
      batchProcessing: results.batchProcessing.success === true,
      performanceTargets: results.performanceTargets.targetsMet === true,
      securityValidation: results.securityValidation.passed === true,
    };

    const allPassed = Object.values(summary).every((passed) => passed === true);
    const passedCount = Object.values(summary).filter(
      (passed) => passed === true
    ).length;
    const totalTests = Object.keys(summary).length;

    console.log(
      `\n✅ Resultados: ${passedCount}/${totalTests} testes passados`
    );
    console.log(
      `🏆 Status geral: ${
        allPassed ? "✅ TODOS OS TESTES PASSARAM" : "⚠️  ALGUNS TESTES FALHARAM"
      }`
    );

    if (allPassed) {
      console.log("\n🎉 🎉 🎉 SESSÃO 5 CONCLUÍDA COM SUCESSO! 🎉 🎉 🎉");
      console.log("✅ Integração Runtime+YAML implementada");
      console.log("✅ Isolamento multi-inquilino validado");
      console.log("✅ Performance targets atingidos");
      console.log("✅ Segurança validada (Score 9.5/10)");
    } else {
      console.log("\n⚠️  Alguns testes falharam. Verifique os detalhes acima.");
    }

    return {
      success: allPassed,
      results,
      summary,
      totalTime: `${totalTime}s`,
    };
  } catch (error) {
    console.log("❌ Erro fatal durante os testes:", error.message);
    return {
      success: false,
      error: error.message,
      results,
      totalTime: `${((Date.now() - startTime) / 1000).toFixed(2)}s`,
    };
  } finally {
    // Limpar recursos
    if (runtimeManager && typeof runtimeManager.dispose === "function") {
      await runtimeManager.dispose();
    }
  }
}

// Executar os testes se este arquivo for executado diretamente
if (require.main === module) {
  runAllTests()
    .then((results) => {
      process.exit(results.success ? 0 : 1);
    })
    .catch((error) => {
      console.error("Fatal error:", error);
      process.exit(1);
    });
}

module.exports = { runAllTests };
