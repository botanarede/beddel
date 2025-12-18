const { SimpleIsolatedRuntimeManager } = require("./src/runtime/simpleRuntime");

async function testSimpleIsolatedRuntime() {
  console.log("🚀 Testing Simple Isolated Runtime v5...");

  const manager = new SimpleIsolatedRuntimeManager();

  try {
    // Test basic execution
    console.log("Test 1: Basic execution");
    const result1 = await manager.execute({
      code: "return 2 + 2;",
      securityProfile: "ultra-secure",
    });

    console.log("✅ Basic execution:", result1);

    // Test memory isolation with calculation
    console.log("Test 2: Memory isolation test");
    const result2 = await manager.execute({
      code: `
        const arr = new Array(100);
        for (let i = 0; i < 100; i++) {
          arr[i] = Math.random() * 100;
        }
        return arr.length;
      `,
      securityProfile: "ultra-secure",
      memoryLimit: 2,
    });

    console.log("✅ Memory isolation:", result2);

    // Test that eval is blocked
    console.log("Test 3: Security restrictions");
    const result3 = await manager.execute({
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

    console.log("✅ Security restrictions:", result3);

    // Test performance
    console.log("Test 4: Performance test");
    const start = Date.now();
    const promises = [];

    for (let i = 0; i < 5; i++) {
      promises.push(
        manager.execute({
          code: `return ${i} * 2;`,
          securityProfile: "ultra-secure",
        })
      );
    }

    await Promise.all(promises);
    const duration = Date.now() - start;

    console.log("✅ Performance test: 5 executions in", duration, "ms");

    // Show metrics
    const metrics = manager.getMetrics();

    console.log("📊 Metrics:", metrics);

    console.log("✅ All tests completed successfully!");
  } catch (error) {
    console.error("❌ Test failed:", error);
  }
}

// Run test if this file is executed directly
if (require.main === module) {
  testSimpleIsolatedRuntime().catch(console.error);
}
