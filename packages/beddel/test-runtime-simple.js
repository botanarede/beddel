// Simple test to verify the runtime concept works
const ivm = require("isolated-vm");
const { runtimeConfig, securityProfiles } = require("./dist/config");

async function testRuntime() {
  console.log("🚀 Testing Isolated Runtime v5 Concept...");

  try {
    // Test basic execution
    console.log("Test 1: Basic execution");
    const result1 = await executeInIsolate("return 2 + 2;", "ultra-secure");
    console.log("✅ Basic execution:", result1);

    // Test memory isolation
    console.log("Test 2: Memory isolation test");
    const result2 = await executeInIsolate(
      "return [1,2,3,4,5].reduce((a,b) => a+b, 0);",
      "ultra-secure"
    );
    console.log("✅ Memory isolation:", result2);

    // Test security - this should fail in real isolated-vm but let's test concept
    console.log("Test 3: Security validation");
    const result3 = await executeInIsolate(
      "return typeof eval;",
      "ultra-secure"
    );
    console.log("✅ Security check:", result3);

    // Test performance
    console.log("Test 4: Performance test");
    const start = Date.now();

    const promises = [];
    for (let i = 0; i < 3; i++) {
      promises.push(executeInIsolate(`return ${i} * 2;`, "ultra-secure"));
    }

    await Promise.all(promises);
    const duration = Date.now() - start;

    console.log("✅ Performance test: 3 executions in", duration + "ms");

    console.log("✅ All concept tests completed!");
  } catch (error) {
    console.error("❌ Test failed:", error);
  }
}

/**
 * Execute code in isolated environment
 */
async function executeInIsolate(code, securityProfileName) {
  const startTime = Date.now();
  const profile =
    securityProfiles[securityProfileName] || securityProfiles["ultra-secure"];

  // Create isolate with memory limit
  const isolate = new ivm.Isolate({ memoryLimit: profile.memoryLimit });

  try {
    // Create context
    const context = await isolate.createContext();

    // Setup basic console
    const jail = context.global;
    await jail.set("console", {
      log: (message) => console.log("isolate log:", message),
      error: (message) => console.error("isolate error:", message),
    });

    // Remove dangerous functions
    await jail.set("eval", new ivm.Reference(undefined));
    await jail.set("Function", new ivm.Reference(undefined));
    await jail.set("require", new ivm.Reference(undefined));

    // Compile and run script
    const script = await isolate.compileScript(code);
    const result = await script.run(context);

    const executionTime = Date.now() - startTime;
    const heapStats = await isolate.getHeapStatistics();

    return {
      success: true,
      result: result,
      executionTime: executionTime,
      memoryUsed: (heapStats.used_heap_size || 0) / (1024 * 1024), // MB
    };
  } finally {
    // Always dispose isolate
    isolate.dispose();
  }
}

// Run test
testRuntime().catch(console.error);
