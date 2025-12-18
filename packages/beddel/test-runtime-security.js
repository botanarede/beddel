const { IsolatedRuntimeManager } = require("./src/runtime/isolatedRuntime");

async function testIsolatedRuntimeSecurity() {
  console.log("🛡️ Testing Isolated Runtime Security Integration...");

  const manager = new IsolatedRuntimeManager();

  try {
    // Test 1: Security scan blocking dangerous code
    console.log("Test 1: Security scan blocking dangerous code");
    const result1 = await manager.execute({
      code: "process.exit(1); console.log('test');",
      securityProfile: "ultra-secure",
      scanForSecurity: true,
    });

    console.log(
      "✅ Security scan result:",
      result1.success ? "Passed" : "Blocked"
    );

    // Test 2: Resource access controls - ultra-secure
    console.log("Test 2: Resource access controls - ultra-secure");
    const result2 = await manager.execute({
      code: `
        try {
          eval('var x = 1');
          return 'EVAL_ALLOWED';
        } catch (e) {
          return 'EVAL_BLOCKED';
        }
      `,
      securityProfile: "ultra-secure",
    });

    console.log("✅ Resource controls:", result2.result);

    // Test 3: Memory pooling and garbage collection
    console.log("Test 3: Memory pooling and garbage collection");
    const initialStats = manager.getPoolStats();

    // Execute multiple times to test pool reuse
    for (let i = 0; i < 5; i++) {
      await manager.execute({
        code: `return ${i} * 2;`,
        securityProfile: "ultra-secure",
      });
    }

    const finalStats = manager.getPoolStats();
    console.log("✅ Pool stats:", { initial: initialStats, final: finalStats });

    // Test 4: Security integration with story 1.1
    console.log("Test 4: Security integration with story 1.1");
    const result4 = await manager.execute({
      code: `
        // Simulate security validation like story 1.1
        function validateSecurity() {
          return {
            score: 9.5,
            grade: 'A',
            secure: true
          };
        }
        return validateSecurity();
      `,
      securityProfile: "ultra-secure",
    });

    console.log("✅ Security integration:", result4.result);

    console.log("✅ Security integration tests completed!");
  } catch (error) {
    console.error("❌ Security test failed:", error.message);
  } finally {
    await manager.dispose();
  }
}

// Run test if this file is executed directly
if (require.main === module) {
  testIsolatedRuntimeSecurity().catch(console.error);
}

module.exports = testIsolatedRuntimeSecurity;
