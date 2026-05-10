import { InMemoryBudgetEnforcer, type BudgetEnforcerConfig } from "../../../src/adapters/budget-enforcer.js";
import type { IBudgetEnforcer } from "../../../src/domain/ports.js";

/**
 * Budget enforcer with persistent storage across workflow runs.
 *
 * Wraps `InMemoryBudgetEnforcer` with load/save hooks for persisting budget
 * state to a file or database between runs.
 *
 * @implements {IBudgetEnforcer}
 */
export class PersistentBudgetEnforcer implements IBudgetEnforcer {
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
