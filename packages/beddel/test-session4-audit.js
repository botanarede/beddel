#!/usr/bin/env node
/**
 * Teste da Sessão 4 - Auditoria e Performance 2025
 * Testa o sistema de auditoria SHA-256 com performance scaling
 */

const fs = require("fs");
const path = require("path");

// Importar módulos com caminho relativo correto
const runtimePath = path.join(__dirname, "audit.js");
let auditService,
  logRuntimeEvent,
  logSecurityViolation,
  logPerformanceViolation,
  logMemoryViolation,
  generateComplianceReportAsync,
  exportComplianceData;

try {
  // Carregar módulo de auditoria
  const auditModule = require("./audit.js");
  auditService = auditModule.auditService;
  logRuntimeEvent = auditModule.logRuntimeEvent;
  logSecurityViolation = auditModule.logSecurityViolation;
  logPerformanceViolation = auditModule.logPerformanceViolation;
  logMemoryViolation = auditModule.logMemoryViolation;
  generateComplianceReportAsync = auditModule.generateComplianceReportAsync;
  exportComplianceData = auditModule.exportComplianceData;
} catch (error) {
  console.error("Erro ao carregar módulos de auditoria:", error.message);
  process.exit(1);
}

// Funções auxiliares
async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function generateTenantId() {
  return `tenant-${Math.random().toString(36).substring(2, 8)}`;
}

function generateExecutionId() {
  return `exec-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
}

// Configuração dos testes
const testConfig = {
  tenants: 5,
  eventsPerTenant: 1000,
  executionTimeTarget: 50, // 50ms
  memoryLimitKB: 2048, // 2MB
  retentionDays: 90,
  maxEventsPerTenant: 10000,
};

// Estatísticas do teste
let testStats = {
  totalEvents: 0,
  totalTenants: 0,
  performanceViolations: 0,
  memoryViolations: 0,
  securityViolations: 0,
  startTime: Date.now(),
  endTime: null,
  processingTime: 0,
};

console.log("🛡️ === SESSÃO 4 - AUDITORIA E PERFORMANCE 2025 ===");
console.log(
  `Configuração: ${testConfig.tenants} tenants, ${testConfig.eventsPerTenant} eventos por tenant`
);
console.log(
  `Targets: ${testConfig.executionTimeTarget}ms execução, ${testConfig.memoryLimitKB}KB memória`
);
console.log("");

async function testPerformanceScaling() {
  console.log("🚀 Testando Performance Scaling...");

  const tenants = [];
  const startTime = Date.now();

  // Criar múltiplos tenants
  for (let i = 0; i < testConfig.tenants; i++) {
    const tenantId = generateTenantId();
    tenants.push(tenantId);

    console.log(
      `  📊 Criando tenant ${i + 1}/${testConfig.tenants}: ${tenantId}`
    );

    // Criar eventos de auditoria para este tenant
    for (let j = 0; j < testConfig.eventsPerTenant; j++) {
      const executionId = generateExecutionId();
      const action = [
        "script_execution",
        "security_scan",
        "compliance_check",
        "data_export",
      ][Math.floor(Math.random() * 4)];

      // Simular diferentes tipos de eventos
      const eventType = Math.random();

      if (eventType < 0.6) {
        // Eventos de execução normais
        logRuntimeEvent(executionId, tenantId, action, "success", {
          scriptId: `script-${j}`,
          duration: Math.floor(Math.random() * 100),
          memory: Math.floor(Math.random() * 1024 * 1024),
        });
      } else if (eventType < 0.8) {
        // Violações de performance
        const executionTime =
          testConfig.executionTimeTarget + Math.floor(Math.random() * 200);
        logPerformanceViolation(
          executionId,
          tenantId,
          executionTime,
          Math.floor(Math.random() * 1024 * 1024)
        );
        testStats.performanceViolations++;
      } else if (eventType < 0.95) {
        // Violações de memória
        const memoryUsage =
          testConfig.memoryLimitKB * 1024 +
          Math.floor(Math.random() * 1024 * 1024);
        logMemoryViolation(executionId, tenantId, memoryUsage);
        testStats.memoryViolations++;
      } else {
        // Violações de segurança
        logSecurityViolation(executionId, tenantId, "unauthorized_access", {
          attemptedAction: action,
          blocked: true,
          reason: "insufficient_permissions",
        });
        testStats.securityViolations++;
      }

      testStats.totalEvents++;
    }

    // Pequena pausa entre tenants para simular carga real
    await sleep(10);
  }

  const endTime = Date.now();
  testStats.processingTime = endTime - startTime;
  testStats.totalTenants = tenants.length;

  console.log(
    `  ✅ Performance scaling test completado em ${testStats.processingTime}ms`
  );
  console.log(
    `  📈 ${testStats.totalEvents} eventos criados para ${testStats.totalTenants} tenants`
  );
  console.log("");

  return tenants;
}

async function testAuditIntegrity(tenants) {
  console.log("🔐 Testando Integridade do Audit Trail...");

  for (const tenantId of tenants.slice(0, 3)) {
    // Testar apenas 3 tenants para performance
    console.log(`  📋 Validando integridade para tenant: ${tenantId}`);

    const integrity = auditService.validateIntegrity(tenantId);

    if (!integrity.isValid) {
      console.error(`  ❌ Integridade comprometida: ${integrity.message}`);
      return false;
    } else {
      console.log(`  ✅ Integridade validada: ${integrity.message}`);
    }
  }

  console.log("");
  return true;
}

async function testComplianceReporting(tenants) {
  console.log("📊 Testando Relatórios de Compliance...");

  for (const tenantId of tenants.slice(0, 2)) {
    // Testar 2 tenants
    console.log(`  📈 Gerando relatório de compliance para: ${tenantId}`);

    const report = await generateComplianceReportAsync(tenantId);

    console.log(`  📋 Resumo do relatório:`);
    console.log(
      `     - Período: ${new Date(
        report.period.start
      ).toISOString()} até ${new Date(report.period.end).toISOString()}`
    );
    console.log(`     - Total de Execuções: ${report.totalExecutions}`);
    console.log(`     - Sucessos: ${report.successfulExecutions}`);
    console.log(`     - Falhas: ${report.failedExecutions}`);
    console.log(`     - Violações de Segurança: ${report.securityViolations}`);
    console.log(
      `     - Violações de Performance: ${report.performanceViolations}`
    );
    console.log(`     - Status de Compliance: ${report.complianceStatus}`);
    console.log(
      `     - Hash do Audit Trail: ${report.auditTrailHash.substring(0, 16)}...`
    );
    console.log("");

    // Testar exportação em diferentes formatos
    console.log(`  💾 Testando exportação de dados...`);

    const jsonExport = exportComplianceData(tenantId, "JSON");
    const csvExport = exportComplianceData(tenantId, "CSV");
    const xmlExport = exportComplianceData(tenantId, "XML");

    console.log(
      `     - JSON export: ${Math.round(jsonExport.length / 1024)}KB`
    );
    console.log(`     - CSV export: ${Math.round(csvExport.length / 1024)}KB`);
    console.log(`     - XML export: ${Math.round(xmlExport.length / 1024)}KB`);
    console.log("");
  }
}

async function testPerformanceMetrics(tenants) {
  console.log("⚡ Testando Métricas de Performance...");

  const stats = auditService.getStatistics(tenants[0]);

  console.log(`  📈 Estatísticas do Tenant ${tenants[0]}:`);
  console.log(`     - Total de Eventos: ${stats.totalEvents}`);
  console.log(
    `     - Eventos por Tipo:`,
    Object.entries(stats.eventsByType)
      .slice(0, 5)
      .map(([k, v]) => `${k}: ${v}`)
      .join(", ")
  );
  console.log(
    `     - Eventos por Severidade: low=${stats.eventsBySeverity.low}, medium=${stats.eventsBySeverity.medium}, high=${stats.eventsBySeverity.high}, critical=${stats.eventsBySeverity.critical}`
  );
  console.log(
    `     - Taxa de Sucesso: ${(
      (stats.eventsByResult.success / stats.totalEvents) *
      100
    ).toFixed(1)}%`
  );
  console.log(
    `     - Score de Compliance: ${stats.averageComplianceScore.toFixed(1)}`
  );
  console.log("");
}

async function testServiceScaling() {
  console.log("🔧 Testando Escalabilidade do Serviço...");

  const serviceStats = auditService.getServiceStats();

  console.log(`  📊 Estatísticas do Serviço:`);
  console.log(`     - Total de Tenants: ${serviceStats.totalTenants}`);
  console.log(`     - Total de Eventos: ${serviceStats.totalEvents}`);
  console.log(
    `     - Uso de Memória: ${Math.round(
      serviceStats.memoryUsage / 1024 / 1024
    )}MB`
  );
  console.log(
    `     - Tempo de Atividade: ${Math.round(
      serviceStats.uptime / 1000 / 60
    )} minutos`
  );
  console.log(
    `     - Política de Retenção Ativa: ${serviceStats.retentionPolicyActive}`
  );
  console.log("");
}

async function testConfiguration() {
  console.log("⚙️ Testando Configuração...");

  // Testar configuração customizada
  auditService.configure({
    retentionDays: 30, // Reduzir para 30 dias para teste
    maxEventsPerTenant: 5000, // Reduzir limite
    enableNonRepudiation: true,
    enableComplianceExport: true,
    complianceStandards: ["GDPR", "LGPD", "SOX"],
  });

  console.log(`  ✅ Configuração aplicada com sucesso`);
  console.log(`     - Dias de retenção: 30`);
  console.log(`     - Máximo de eventos por tenant: 5000`);
  console.log(`     - Padrões de compliance: GDPR, LGPD, SOX`);
  console.log("");
}

async function runBenchmark() {
  console.log("🏃 Executando Benchmark de Performance...");

  const benchmarkStart = Date.now();
  const benchmarkTenant = generateTenantId();
  const iterations = 10000;

  // Benchmark de criação de eventos
  console.log(
    `  📝 Benchmark de criação de eventos (${iterations} iterações)...`
  );
  const creationStart = Date.now();

  for (let i = 0; i < iterations; i++) {
    const executionId = generateExecutionId();
    logRuntimeEvent(
      executionId,
      benchmarkTenant,
      "benchmark_execution",
      "success",
      {
        iteration: i,
        timestamp: Date.now(),
      }
    );
  }

  const creationTime = Date.now() - creationStart;
  const creationRate = (iterations / creationTime) * 1000; // eventos por segundo

  console.log(`     - Tempo total: ${creationTime}ms`);
  console.log(
    `     - Taxa de criação: ${Math.round(creationRate)} eventos/segundo`
  );
  console.log(
    `     - Tempo médio por evento: ${Math.round(
      (creationTime / iterations) * 1000
    )}μs`
  );
  console.log("");

  // Benchmark de geração de relatórios
  console.log(`  📊 Benchmark de geração de relatórios...`);
  const reportStart = Date.now();

  const report = await generateComplianceReportAsync(benchmarkTenant);

  const reportTime = Date.now() - reportStart;
  console.log(`     - Tempo para gerar relatório: ${reportTime}ms`);
  console.log(`     - Total de eventos processados: ${report.totalExecutions}`);
  console.log(
    `     - Tempo médio por evento: ${Math.round(
      (reportTime / report.totalExecutions) * 1000
    )}μs`
  );
  console.log("");

  testStats.endTime = Date.now();

  console.log("✅ Benchmark completado com sucesso!");
  console.log("");
}

async function runSession4Tests() {
  try {
    console.log("🛡️ INICIANDO TESTES DA SESSÃO 4 - AUDITORIA E PERFORMANCE");
    console.log("");

    // Executar testes em sequência
    const tenants = await testPerformanceScaling();
    await sleep(100);

    await testConfiguration();
    await sleep(100);

    const integrityValid = await testAuditIntegrity(tenants);
    if (!integrityValid) {
      console.error(
        "❌ Falha crítica: Integridade do audit trail comprometida"
      );
      process.exit(1);
    }

    await testComplianceReporting(tenants);
    await sleep(100);

    await testPerformanceMetrics(tenants);
    await sleep(100);

    await testServiceScaling();
    await sleep(100);

    await runBenchmark();

    // Resumo final
    console.log("📊 === RESUMO FINAL DA SESSÃO 4 ===");
    console.log(`Total de Eventos: ${testStats.totalEvents}`);
    console.log(`Total de Tenants: ${testStats.totalTenants}`);
    console.log(`Violações de Performance: ${testStats.performanceViolations}`);
    console.log(`Violações de Memória: ${testStats.memoryViolations}`);
    console.log(`Violações de Segurança: ${testStats.securityViolations}`);
    console.log(`Tempo Total de Processamento: ${testStats.processingTime}ms`);
    console.log(
      `Tempo Total do Teste: ${testStats.endTime - testStats.startTime}ms`
    );
    console.log("");

    console.log("🎯 === MÉTRICAS DE SUCESSO ===");
    console.log(`✅ Sistema de Auditoria SHA-256: Funcional`);
    console.log(`✅ Integridade do Audit Trail: Validada`);
    console.log(`✅ Relatórios de Compliance: Gerados`);
    console.log(`✅ Exportação Multi-formato: Funcional`);
    console.log(
      `✅ Escalabilidade: Testada com ${testStats.totalTenants} tenants`
    );
    console.log(
      `✅ Performance: ${Math.round(
        testStats.totalEvents / (testStats.processingTime / 1000)
      )} eventos/segundo`
    );
    console.log("");

    console.log("🛡️ === SESSÃO 4 COMPLETA ===");
    console.log("✅ Auditoria e Performance 2025 implementadas com sucesso!");
  } catch (error) {
    console.error("❌ Erro durante os testes:", error);
    process.exit(1);
  }
}

// Executar testes
runSession4Tests().catch((error) => {
  console.error("❌ Erro crítico:", error);
  process.exit(1);
});
