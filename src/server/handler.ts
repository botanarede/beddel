import { NextRequest } from 'next/server';
import { loadYaml } from '../core/parser';
import { WorkflowExecutor } from '../core/workflow';
import { join, normalize } from 'path';
import { access } from 'fs/promises';
import { getBuiltinAgentsPath } from '../agents';

export interface BeddelHandlerOptions {
    /** Path to user-defined agents (relative to CWD). Default: 'src/agents' */
    agentsPath?: string;
    /** Disable built-in agents bundled with the package. Default: false */
    disableBuiltinAgents?: boolean;
}

export type BeddelHandler = (request: NextRequest) => Promise<Response>;

/**
 * Validate agentId to prevent path traversal attacks.
 * Only allows alphanumeric characters, hyphens, and underscores.
 */
function isValidAgentId(agentId: string): boolean {
    if (typeof agentId !== 'string' || agentId.length === 0) {
        return false;
    }
    const safePattern = /^[a-zA-Z0-9_-]+$/;
    return safePattern.test(agentId);
}

/**
 * Check if a file exists at the given path
 */
async function fileExists(path: string): Promise<boolean> {
    try {
        await access(path);
        return true;
    } catch {
        return false;
    }
}

/**
 * Resolve agent path with fallback chain:
 * 1. User agents (agentsPath) - allows override
 * 2. Built-in agents (package) - fallback
 */
async function resolveAgentPath(
    agentId: string,
    userAgentsPath: string,
    disableBuiltinAgents: boolean
): Promise<string> {
    // 1. First: try user agents (allows override of built-in)
    const basePath = join(process.cwd(), userAgentsPath);
    const userPath = normalize(join(basePath, `${agentId}.yaml`));
    
    // Security: ensure resolved path is within user agents directory
    if (userPath.startsWith(basePath) && await fileExists(userPath)) {
        return userPath;
    }

    // 2. Fallback: built-in agents from package
    if (!disableBuiltinAgents) {
        const builtinPath = join(getBuiltinAgentsPath(), `${agentId}.yaml`);
        if (await fileExists(builtinPath)) {
            return builtinPath;
        }
    }

    throw new Error(`Agent not found: ${agentId}`);
}

export function createBeddelHandler(options: BeddelHandlerOptions = {}): BeddelHandler {
    const agentsPath = options.agentsPath || 'src/agents';
    const disableBuiltinAgents = options.disableBuiltinAgents || false;

    return async function POST(request: NextRequest): Promise<Response> {
        try {
            const body = await request.json() as any;
            const { agentId, ...input } = body;

            if (!agentId) {
                return Response.json({ error: 'agentId is required' }, { status: 400 });
            }

            // Security: Validate agentId to prevent path traversal
            if (!isValidAgentId(agentId)) {
                return Response.json(
                    { error: 'Invalid agentId: only alphanumeric characters, hyphens, and underscores allowed' },
                    { status: 400 }
                );
            }

            // Resolve agent path with fallback chain
            const fullPath = await resolveAgentPath(agentId, agentsPath, disableBuiltinAgents);
            
            const yaml = await loadYaml(fullPath);

            const executor = new WorkflowExecutor(yaml);
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
