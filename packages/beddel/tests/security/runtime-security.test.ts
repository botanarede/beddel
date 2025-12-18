/**
 * Testes de segurança para validar a implementação
 */

import { SecurityScanner } from "../../src/security/scanner";
import { SecurityValidator } from "../../src/security/validation";
import {
  SecurityScore as SecurityScoreImpl,
  calculateSecurityScore,
} from "../../src/security/score";
import { SecurityHardening } from "../../src/security/hardening";
// The helpers below live alongside the runtime modules inside src/security
import {
  SecurityManager,
  ThreatDetectionEngine,
} from "../../src/security";

// Dados de teste - YAML malicioso simulado
const maliciousYaml = `
name: "John Doe"
description: "<script>alert('XSS')</script>"
api_key: "sk-1234567890abcdef"
nested:
  deep:
    more:
      malicious: "javascript:const x = 'injection'"
`;

// Objeto malicioso direto
const maliciousObject = {
  name: "John Doe",
  xss_payload: "<script>alert('XSS')</script>",
  api_key: "sk-1234567890abcdef",
  injection: "javascript:var x = 'test'",
  oversized: "x".repeat(1024 * 1024 * 50), // 50MB
  deep: {}
};

// Criar objeto com profundidade maliciosa
let current: any = maliciousObject.deep;
for (let i = 0; i < 1500; i++) {
  current.nested = {};
  current = current.nested;
}

// Teste de Segurança Simples
export function runSimpleSecurityTest() {
  console.log("🔒 Rodando testes de segurança básicos...\n");
  
  try {
    const scoreCalculator = new SecurityScoreImpl();
    const result = scoreCalculator.calculate(maliciousObject);
    
    console.log("📊 Score de Segurança:", result.score);
    console.log("🎯 Grau:", result.grade);
    console.log("⚠️  Nível de Risco:", result.riskLevel);
    console.log("🔴 Vulnerabilidades:", result.vulnerabilities.length);
    console.log("✅ Features de Hardening:", result.hardeningApplied.length);
    console.log("💡 Recomendações:", result.recommendations.length);
    
    console.log("\n🔍 Detalhes de Vulnerabilidades:");
    result.vulnerabilities.forEach((vuln, index) => {
      console.log(`  ${index + 1}. [${vuln.severity.toUpperCase()}] ${vuln.type}: ${vuln.description}`);
    });
    
    console.log("\n🔧 Features de Hardening Aplicadas:");
    result.hardeningApplied.forEach((feature, index) => {
      console.log(`  ${index + 1}. ${feature.name} (${feature.status}): ${feature.description}`);
    });
    
    return result;
  } catch (error) {
    console.error("❌ Falha no teste de segurança:", error);
    throw error;
  }
}

// Teste de Scanner Completo
export async function runScannerTest() {
  console.log("\n🔍 Rodando teste de Scanner de Segurança...\n");
  
  try {
    const scanner = new SecurityScanner();
    const result = await scanner.scan(maliciousObject);
    
    console.log("📊 Scanner Result:");
    console.log("  - Seguro:", result.secure);
    console.log("  - Score:", result.score);
    console.log("  - Grau:", result.grade);
    console.log("  - Vulnerabilidades:", result.vulnerabilities.length);
    console.log("  - Advertências:", result.warnings.length);
    console.log("  - Recomendações:", result.recommendations.length);
    
    return result;
  } catch (error) {
    console.error("❌ Falha no teste do scanner:", error);
    throw error;
  }
}

// Teste de Validação YAML
export function runYamlValidationTest() {
  console.log("\n📋 Rodando teste de validação YAML...\n");
  
  try {
    const result = validateYamlSecurity(maliciousYaml);
    
    console.log("🔒 Resultado da Validação YAML:");
    console.log("  - Seguro:", result.secure);
    console.log("  - Problemas:", result.issues.join(", "));
    console.log("  - Recomendações:", result.recommendations.length);
    
    return result;
  } catch (error) {
    console.error("❌ Falha no teste de validação YAML:", error);
    throw error;
  }
}

// Teste de Validação Rápida
export function runQuickValidation() {
  console.log("\n⚡ Rodando teste de validação rápida...\n");
  
  try {
    const result = quickSecurityValidation(maliciousObject);
    
    console.log("🚀 Validação Rápida:");
    console.log("  - Válido:", result.isValid);
    console.log("  - Score:", result.score);
    console.log("  - Grau:", result.grade);
    
    return result;
  } catch (error) {
    console.error("❌ Falha no teste de validação rápida:", error);
    throw error;
  }
}

// Função principal executando todos os testes
export async function runAllSecurityTests() {
  console.log("🛡️  INICIANDO BATERIA DE TESTES DE SEGURANÇA");
  console.log("=".repeat(50));
  
  const results = {
    securityScore: runSimpleSecurityTest(),
    scanner: await runScannerTest(),
    yamlValidation: runYamlValidationTest(),
    quickValidation: runQuickValidation()
  };
  
  console.log("\n".repeat(2));
  console.log("🎉 🛡️  BATERIA DE TESTES COMPLETADA COM SUCESSO!");
  console.log("📊 Resumo:", JSON.stringify({
    securityScore: results.securityScore.score,
    scannerSecure: results.scanner.secure,
    yamlSecure: results.yamlValidation.secure,
    quickValid: results.quickValidation.isValid && results.quickValidation.score >= 60
  }, null, 2));
  
  return results;
}

// Executar testes se este arquivo for chamado diretamente
if (require.main === module) {
  runAllSecurityTests().then(() => {
    console.log("✅ Testes finalizados");
  }).catch((error) => {
    console.error("🔥 Falha nos testes:", error);
  });
}

// Exportação dos testes
export default {
  runAllSecurityTests,
  runSimpleSecurityTest,
  runScannerTest,
  runYamlValidationTest,
  runQuickValidation
};
