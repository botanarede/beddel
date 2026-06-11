# agentrq-approval-kit

AgentRQ HOTL (human-in-the-loop) approval gate adapter for Beddel workflows. Implements the `IApprovalGate` port to create approval tasks in AgentRQ and poll for human decisions via MCP.

## What It Does

When a Beddel workflow reaches a high-risk step requiring human approval, this adapter:

1. Creates a task in AgentRQ with structured context (action, risk level, workflow details)
2. Posts enrichment messages to give the reviewer full context
3. Polls for the human's decision (approve, deny, escalate)
4. Maps AgentRQ task statuses back to Beddel's `ApprovalStatus`

## Dependencies

- `mcp>=1.0`
- `httpx-sse>=0.4`

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `python/` directory to your Python path:

```bash
export PYTHONPATH="kits/agentrq-approval-kit/python:$PYTHONPATH"
```

Or install the Beddel SDK with the agentrq extra (when available):

```bash
pip install beddel[agentrq]
```

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `workspace_url` | `str` | (required) | Full AgentRQ MCP endpoint URL including auth token |
| `timeout_seconds` | `int` | `300` | Client-side timeout before marking request as TIMEOUT |
| `policy` | `ApprovalPolicy` | `None` | Optional policy for auto-approve by risk level |

The `workspace_url` should point to your AgentRQ workspace MCP server, e.g.:
```
https://app.agentrq.com/ws/<workspace-id>/mcp?token=<your-token>
```

## Usage

```python
from beddel_agentrq_approval import AgentRQApprovalGate

gate = AgentRQApprovalGate(
    workspace_url="https://app.agentrq.com/ws/my-workspace/mcp?token=secret",
    timeout_seconds=600,
)

# Request approval (blocks until human responds or timeout)
result = await gate.request_approval(
    action="deploy-to-production",
    risk_level="high",
)
print(result.status)  # APPROVED, DENIED, ESCALATED, TIMEOUT, or PENDING

# Async/CIBA pattern (returns immediately with request_id)
request_id = await gate.request_approval_async(
    action="delete-user-data",
    risk_level="critical",
)

# Poll later
status = await gate.check_status(request_id)
```

## Running Tests

```bash
cd kits/agentrq-approval-kit
python -m pytest tests/ -x
```
