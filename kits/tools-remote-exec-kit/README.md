# tools-remote-exec-kit

Remote/VM execution tools for Beddel workflows. V1 backend: Multipass.

## Tools

| Tool | Description |
|------|-------------|
| `remote_exec` | Execute a command on a remote VM |
| `remote_health_check` | Check VM reachability and test file existence |
| `remote_file_read` | Read a file from a remote VM (size-capped) |

## Prerequisites

- `multipass` CLI on PATH
- A running Multipass VM (e.g., `multipass launch --name my-vm`)

## Backend Parameter

All tools accept a `backend` parameter. V1 supports only `"multipass"`. Passing `"ssh"` or `"docker"` raises `NotImplementedError`.

## Security Note

Commands are passed as a single string to `bash -c` inside the VM. The command string is NOT escaped. Callers must not construct commands from untrusted user input without sanitization.
