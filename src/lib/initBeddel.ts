/**
 * Beddel Initialization
 * Loads custom agents from the /agents directory
 */

import { agentRegistry } from "beddel";

/**
 * Initialize Beddel and load custom agents
 * Call this once during application startup
 */
export function initBeddel() {
    try {
        // Load custom agents from /agents directory
        agentRegistry.loadCustomAgents();
    } catch (error) {
        console.error("Failed to initialize Beddel:", error);
    }
}
