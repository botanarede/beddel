import type { WorkflowExecutor } from "../../../src/domain/executor.js";
import type { Workflow } from "../../../src/domain/models.js";
import type { Request, Response, NextFunction } from "express";

/**
 * Configuration for the Beddel Express server.
 */
export interface BeddelServerConfig {
	executor: WorkflowExecutor;
	workflows: Map<string, Workflow>;
	port?: number;
	basePath?: string;
	cors?: boolean;
}

/**
 * Creates an Express server that exposes Beddel workflow execution via REST API.
 *
 * @param config - Server configuration including executor and workflow registry.
 * @returns An Express application instance.
 *
 * @example
 * ```ts
 * import { createBeddelServer } from '@beddel/serve-express';
 *
 * const app = createBeddelServer({
 *   executor,
 *   workflows: workflowMap,
 *   port: 3000,
 * });
 *
 * app.listen(3000, () => console.log('Beddel server running'));
 * ```
 */
export async function createBeddelServer(config: BeddelServerConfig): Promise<unknown> {
	const { default: express } = await import("express");

	const app = express();
	const basePath = config.basePath ?? "/api/v1";

	app.use(express.json());

	if (config.cors) {
		app.use((req: Request, res: Response, next: NextFunction) => {
			res.setHeader("Access-Control-Allow-Origin", "*");
			res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
			res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
			next();
		});
	}

	// Health check
	app.get(`${basePath}/health`, (_req: unknown, res: { json: (data: unknown) => void }) => {
		res.json({ status: "ok", version: "0.1.0" });
	});

	// List available workflows
	app.get(`${basePath}/workflows`, (_req: unknown, res: { json: (data: unknown) => void }) => {
		const workflows = Array.from(config.workflows.entries()).map(([id, wf]) => ({
			id,
			name: wf.name,
			description: wf.description,
		}));
		res.json({ workflows });
	});

	// Execute a workflow
	app.post(
		`${basePath}/workflows/:workflowId/execute`,
		async (
			req: { params: { workflowId: string }; body: { inputs?: Record<string, unknown> } },
			res: { json: (data: unknown) => void; status: (code: number) => { json: (data: unknown) => void } },
		) => {
			const { workflowId } = req.params;
			const workflow = config.workflows.get(workflowId);

			if (!workflow) {
				res.status(404).json({
					error: "WORKFLOW_NOT_FOUND",
					message: `Workflow '${workflowId}' not found`,
				});
				return;
			}

			try {
				const inputs = req.body?.inputs ?? {};
				const result = await config.executor.execute(workflow, inputs);
				res.json({ workflow_id: workflowId, result, status: "completed" });
			} catch (error) {
				const message = error instanceof Error ? error.message : String(error);
				res.status(500).json({
					error: "EXECUTION_ERROR",
					message,
				});
			}
		},
	);

	// Execute a workflow with streaming (SSE)
	app.post(
		`${basePath}/workflows/:workflowId/stream`,
		async (
			req: { params: { workflowId: string }; body: { inputs?: Record<string, unknown> } },
			res: {
				setHeader: (name: string, value: string) => void;
				write: (data: string) => void;
				end: () => void;
				status: (code: number) => { json: (data: unknown) => void };
			},
		) => {
			const { workflowId } = req.params;
			const workflow = config.workflows.get(workflowId);

			if (!workflow) {
				res.status(404).json({
					error: "WORKFLOW_NOT_FOUND",
					message: `Workflow '${workflowId}' not found`,
				});
				return;
			}

			res.setHeader("Content-Type", "text/event-stream");
			res.setHeader("Cache-Control", "no-cache");
			res.setHeader("Connection", "keep-alive");

			try {
				const inputs = req.body?.inputs ?? {};
				for await (const event of config.executor.executeStream(workflow, inputs)) {
					res.write(`data: ${JSON.stringify(event)}\n\n`);
				}
				res.write("data: [DONE]\n\n");
			} catch (error) {
				const message = error instanceof Error ? error.message : String(error);
				res.write(`data: ${JSON.stringify({ error: message })}\n\n`);
			} finally {
				res.end();
			}
		},
	);

	return app;
}
