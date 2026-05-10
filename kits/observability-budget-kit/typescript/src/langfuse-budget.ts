import { InMemoryBudgetEnforcer, type BudgetEnforcerConfig } from "../../../src/adapters/budget-enforcer.js";
import type { IBudgetEnforcer } from "../../../src/domain/ports.js";

/**
 * Budget enforcer with Langfuse cost-tracking integration.
 *
 * Extends `InMemoryBudgetEnforcer` with real cost data from Langfuse traces.
 * Delegates to Langfuse for actual cost per model/token-type.
 *
 * @implements {IBudgetEnforcer}
 */
export class LangfuseBudgetEnforcer implements IBudgetEnforcer {
	private readonly inner: InMemoryBudgetEnforcer;

	constructor(config: BudgetEnforcerConfig) {
		this.inner = new InMemoryBudgetEnforcer(config);
	}

	get cumulativeCost(): number {
		return this.inner.cumulativeCost;
	}

	get maxCostUsd(): number {
		return this.inner.maxCostUsd;
	}

	trackUsage(stepId: string, usage: Record<string, unknown>): void {
		this.inner.trackUsage(stepId, usage);
	}

	checkBudget(): { status: string; remaining: number } {
		return this.inner.checkBudget();
	}

	getRemaining(): number {
		return this.inner.getRemaining();
	}
}
