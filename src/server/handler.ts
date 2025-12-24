import { NextRequest } from 'next/server';
import { loadYaml } from '../core/parser';
import { WorkflowExecutor } from '../core/workflow';
import { join } from 'path';

export interface BeddelHandlerOptions {
    agentsPath?: string;
}

export type BeddelHandler = (request: NextRequest) => Promise<Response>;

export function createBeddelHandler(options: BeddelHandlerOptions = {}): BeddelHandler {
    const agentsPath = options.agentsPath || 'src/agents';

    return async function POST(request: NextRequest): Promise<Response> {
        try {
            const body = await request.json() as any;
            const { agentId, ...input } = body;

            if (!agentId) {
                return Response.json({ error: 'agentId is required' }, { status: 400 });
            }

            // Resolve path relative to CWD (usually project root)
            const fullPath = join(process.cwd(), agentsPath, `${agentId}.yaml`);
            const yaml = await loadYaml(fullPath);

            const executor = new WorkflowExecutor(yaml);
            // Pass the entire body (minus agentId) as input ($input)
            const result = await executor.execute(input);

            if (result instanceof Response) {
                return result;
            }

            return Response.json(result);
        } catch (error) {
            console.error('[Beddel] Handler Error:', error);
            return Response.json(
                { error: error instanceof Error ? error.message : 'Internal Server Error' },
                { status: 500 }
            );
        }
    };
}
