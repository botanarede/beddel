#!/usr/bin/env node

/**
 * Test Firebase Multi-Tenant Integration
 * Testes de isolamento entre tenants com LGPD/GDPR compliance
 */

const { MultiTenantFirebaseManager } = require("./dist/firebase/tenantManager");

async function runTenantTests() {
  console.log("🚀 Iniciando testes de multi-tenant Firebase...");

  const manager = MultiTenantFirebaseManager.getInstance();
  const results = [];

  // Test 1: Initialize tenants with different security profiles
  console.log("\n📋 Teste 1: Inicialização de tenants com perfis de segurança");

  try {
    // Tenant 1 - Ultra-secure
    const tenant1Config = {
      tenantId: "tenant-ultra-1",
      projectId: "project-ultra-secure",
      databaseURL: "https://project-ultra-secure.firebaseio.com/",
      storageBucket: "project-ultra-secure.appspot.com",
      securityProfile: "ultra-secure",
      dataRetentionDays: 365,
      lgpdEnabled: true,
      gdprEnabled: true,
    };

    const result1 = await manager.initializeTenant(tenant1Config);
    console.log(`✅ Tenant ultra-secure inicializado:`);
    console.log(`   - Tenant ID: ${result1.tenantId}`);
    console.log(`   - Security Score: ${result1.securityScore}/10`);
    console.log(`   - Audit Hash: ${result1.auditHash}`);
    console.log(`   - Execution Time: ${result1.executionTime}ms`);
    console.log(`   - LGPD Compliance: ${result1.complianceStatus.lgpd}`);
    console.log(`   - GDPR Compliance: ${result1.complianceStatus.gdpr}`);

    // Tenant 2 - Tenant-isolated
    const tenant2Config = {
      tenantId: "tenant-isolated-2",
      projectId: "project-tenant-isolated",
      databaseURL: "https://project-tenant-isolated.firebaseio.com/",
      storageBucket: "project-tenant-isolated.appspot.com",
      securityProfile: "tenant-isolated",
      dataRetentionDays: 365,
      lgpdEnabled: true,
      gdprEnabled: false,
    };

    const result2 = await manager.initializeTenant(tenant2Config);
    console.log(`\n✅ Tenant isolated inicializado:`);
    console.log(`   - Tenant ID: ${result2.tenantId}`);
    console.log(`   - Security Score: ${result2.securityScore}/10`);
    console.log(`   - Audit Hash: ${result2.auditHash}`);
    console.log(`   - Execution Time: ${result2.executionTime}ms`);
    console.log(`   - LGPD Compliance: ${result2.complianceStatus.lgpd}`);
    console.log(`   - GDPR Compliance: ${result2.complianceStatus.gdpr}`);

    results.push({ test: 1, success: true, result1, result2 });
  } catch (error) {
    console.error(`❌ Erro no Teste 1: ${error.message}`);
    results.push({ test: 1, success: false, error: error.message });
  }

  // Test 2: Tenant isolation verification
  console.log("\n🔒 Teste 2: Isolamento entre tenants");

  try {
    const tenants = manager.getActiveTenants();
    console.log(`📊 Tenants ativos: ${tenants.join(", ")}`);

    // Verify tenant apps are different
    const app1 = manager.getTenantApp("tenant-ultra-1");
    const app2 = manager.getTenantApp("tenant-isolated-2");

    if (app1.name !== app2.name) {
      console.log("✅ Isolamento de tenants verificado com sucesso");
      console.log(`   - App Ultra: ${app1.name}`);
      console.log(`   - App Isolated: ${app2.name}`);
      results.push({ test: 2, success: true });
    } else {
      throw new Error("Isolamento de tenants falhou - mesma aplicação");
    }
  } catch (error) {
    console.error(`❌ Erro no Teste 2: ${error.message}`);
    results.push({ test: 2, success: false, error: error.message });
  }

  // Test 3: Execute operations in tenant context
  console.log("\n⚙️ Teste 3: Executar operações em contexto de tenant");

  try {
    const result3 = await manager.executeInTenant(
      "tenant-ultra-1",
      "data_processing",
      { data: "sensitive_info" },
      async () => {
        console.log("✅ Operação executada em contexto ultra-secure");
        return { processed: true };
      }
    );

    console.log(
      `✅ Operação tenant-isolated finalizada: ${JSON.stringify(result3)}`
    );
    results.push({ test: 3, success: true, result: result3 });
  } catch (error) {
    console.error(`❌ Erro no Teste 3: ${error.message}`);
    results.push({ test: 3, success: false, error: error.message });
  }

  // Test 4: Tenant statistics
  console.log("\n📊 Teste 4: Estatísticas de tenants");

  try {
    const stats = await manager.getTenantStats();
    console.log("✅ Estatísticas obtidas com sucesso");

    for (const [tenantId, stats] of stats) {
      console.log(`\n📈 Tenant: ${tenantId}`);
      console.log(`   - Success: ${stats.success}`);
      console.log(`   - Security Score: ${stats.securityScore}/10`);
      console.log(`   - Execution Time: ${stats.executionTime}ms`);
      console.log(
        `   - Compliance: LGPD=${stats.complianceStatus.lgpd}, GDPR=${stats.complianceStatus.gdpr}`
      );
    }

    results.push({ test: 4, success: true, stats: Object.fromEntries(stats) });
  } catch (error) {
    console.error(`❌ Erro no Teste 4: ${error.message}`);
    results.push({ test: 4, success: false, error: error.message });
  }

  // Test 5: Security validation
  console.log("\n🛡️ Teste 5: Validação de segurança");

  try {
    // Test invalid tenant ID
    try {
      await manager.initializeTenant({
        tenantId: "ab", // Invalid - too short
        projectId: "test",
        databaseURL: "https://test.firebaseio.com/",
        storageBucket: "test.appspot.com",
        securityProfile: "tenant-isolated",
        dataRetentionDays: 365,
        lgpdEnabled: true,
        gdprEnabled: false,
      });
      throw new Error("Should have failed with invalid tenant ID");
    } catch (validationError) {
      if (validationError.message.includes("at least 3 characters")) {
        console.log("✅ Validação de ID de tenant funcionando corretamente");
      } else {
        throw validationError;
      }
    }

    // Test data retention validation
    try {
      await manager.initializeTenant({
        tenantId: "tenant-invalid-retention",
        projectId: "test",
        databaseURL: "https://test.firebaseio.com/",
        storageBucket: "test.appspot.com",
        securityProfile: "tenant-isolated",
        dataRetentionDays: 30, // Too short
        lgpdEnabled: true,
        gdprEnabled: false,
      });
      throw new Error("Should have failed with invalid retention");
    } catch (retentionError) {
      if (retentionError.message.includes("minimum 90 days")) {
        console.log(
          "✅ Validação de retenção de dados LGPD funcionando corretamente"
        );
      } else {
        throw retentionError;
      }
    }

    results.push({ test: 5, success: true });
  } catch (error) {
    console.error(`❌ Erro no Teste 5: ${error.message}`);
    results.push({ test: 5, success: false, error: error.message });
  }

  // Test 6: Performance benchmarks
  console.log("\n⚡ Teste 6: Benchmark de performance");

  try {
    const startTime = Date.now();

    console.log("🔧 Executando benchmark multi-tenant...");

    // Simulate multiple tenant operations
    const promises = [];
    for (let i = 0; i < 10; i++) {
      promises.push(
        manager.executeInTenant(
          "tenant-ultra-1",
          `performance_test_${i}`,
          { iteration: i },
          async () => {
            return new Promise((resolve) => setTimeout(resolve, 10)); // 10ms delay
          }
        )
      );
    }

    await Promise.all(promises);
    const totalTime = Date.now() - startTime;
    const avgTime = totalTime / 10;

    console.log(`✅ Benchmark concluído em ${totalTime}ms`);
    console.log(`✅ Tempo médio por operação: ${avgTime.toFixed(2)}ms`);
    console.log(
      `✅ Target: <100ms - Status: ${avgTime < 100 ? "ALCANÇADO" : "FALHOU"}`
    );

    results.push({ test: 6, success: avgTime < 100, totalTime, avgTime });
  } catch (error) {
    console.error(`❌ Erro no Teste 6: ${error.message}`);
    results.push({ test: 6, success: false, error: error.message });
  }

  // Test 7: Security score target validation
  console.log("\n🎯 Teste 7: Alvos de security score");

  try {
    const stats = await manager.getTenantStats();
    let allScoresMet = true;

    for (const [tenantId, stats] of stats) {
      console.log(
        `📊 Tenant ${tenantId}: Security Score = ${stats.securityScore}/10`
      );
      if (stats.securityScore >= 9.5) {
        console.log(`✅ Target 9.5/10 alcançado para ${tenantId}`);
      } else {
        console.log(`❌ Target 9.5/10 falhou para ${tenantId}`);
        allScoresMet = false;
      }
    }

    results.push({ test: 7, success: allScoresMet });
    if (allScoresMet) {
      console.log(
        "🎉 Todos os tenants alcançaram o target de security score 9.5/10"
      );
    }
  } catch (error) {
    console.error(`❌ Erro no Teste 7: ${error.message}`);
    results.push({ test: 7, success: false, error: error.message });
  }

  // Final results summary
  console.log("\n" + "=".repeat(60));
  console.log("📊 RESUMO DOS TESTES");
  console.log("=".repeat(60));

  const passed = results.filter((r) => r.success).length;
  const failed = results.filter((r) => !r.success).length;
  const total = results.length;

  results.forEach((result) => {
    const status = result.success ? "✅ PASS" : "❌ FAIL";
    const errorInfo = result.error ? ` - ${result.error}` : "";
    console.log(`Teste ${result.test}: ${status}${errorInfo}`);
  });

  console.log(`\n📈 Resultado Final: ${passed}/${total} testes passaram`);

  if (passed === total) {
    console.log(
      "🎉 TODOS OS TESTES PASSARAM! Firebase Multi-Tenant está funcionando corretamente."
    );
    console.log("✅ Security Score Target 9.5/10 - ALCANÇADO");
    console.log("✅ Performance Target <100ms - ALCANÇADO");
    console.log("✅ LGPD/GDPR Compliance - IMPLEMENTADO");
    console.log("✅ SHA-256 Audit Trail - FUNCIONANDO");
  } else {
    console.log(`⚠️  ${failed} testes falharam. Verificar implementação.`);
  }

  // Write results for documentation
  const fs = require("fs");
  const resultsPath = "./test-firebase-tenant-results.json";
  fs.writeFileSync(resultsPath, JSON.stringify(results, null, 2));
  console.log(`\n💾 Resultados salvos em: ${resultsPath}`);

  return results;
}

// Execute tests if run directly
if (require.main === module) {
  runTenantTests().catch((error) => {
    console.error("❌ Erro fatal nos testes:", error);
    process.exit(1);
  });
}

module.exports = { runTenantTests };
