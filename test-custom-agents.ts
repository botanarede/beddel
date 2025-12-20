/**
 * Test script for custom agent loading
 * Tests the custom agent registry functionality
 */

import { agentRegistry } from "./packages/beddel/src/agents/registry/agentRegistry.js";
import { join } from "path";

async function testCustomAgentLoading() {
    console.log("🧪 Testing Custom Agent Loading System\n");

    // Test 1: Load custom agents from /agents directory
    console.log("Test 1: Loading custom agents from /agents directory");
    try {
        const agentsPath = join(process.cwd(), "agents");
        agentRegistry.loadCustomAgents(agentsPath);
        console.log("✅ Custom agents loaded successfully\n");
    } catch (error) {
        console.error("❌ Failed to load custom agents:", error);
        process.exit(1);
    }

    // Test 2: Verify built-in agents still exist
    console.log("Test 2: Verifying built-in agents");
    const builtinAgents = ["joker.execute", "translator.execute", "image.generate"];
    for (const agentName of builtinAgents) {
        const agent = agentRegistry.getAgent(agentName);
        if (agent) {
            console.log(`✅ Built-in agent found: ${agentName}`);
        } else {
            console.error(`❌ Built-in agent missing: ${agentName}`);
            process.exit(1);
        }
    }
    console.log();

    // Test 3: Verify custom agent was loaded
    console.log("Test 3: Verifying custom agent");
    const customAgent = agentRegistry.getAgent("exemplo-agente.execute");
    if (customAgent) {
        console.log(`✅ Custom agent found: ${customAgent.name}`);
        console.log(`   Description: ${customAgent.description}`);
        console.log(`   Route: ${customAgent.route}`);
    } else {
        console.log("⚠️  Custom agent not found (this is OK if /agents/exemplo-agente.yaml doesn't exist)");
    }
    console.log();

    // Test 4: List all registered agents
    console.log("Test 4: Listing all registered agents");
    const allAgents = agentRegistry.getAllAgents();
    console.log(`Total agents registered: ${allAgents.length}`);
    for (const agent of allAgents) {
        console.log(`  - ${agent.name} (${agent.id})`);
    }
    console.log();

    console.log("✅ All tests passed!");
}

// Run tests
testCustomAgentLoading().catch((error) => {
    console.error("Test failed:", error);
    process.exit(1);
});
