# tools-docker-kit

Docker Compose operations for containerized agent sessions.

## Tools

| Tool | Description |
|------|-------------|
| `docker_compose_build` | Build a Docker Compose service image |
| `docker_compose_run` | Run a one-off command in a Compose service container |
| `docker_compose_up` | Start Compose services |
| `docker_compose_down` | Stop and remove Compose services |

## Prerequisites

- Docker CLI with Compose plugin (`docker compose`) on PATH
- No Python dependencies beyond stdlib

## Example docker-compose.yml

```yaml
services:
  kiro-story:
    build: .
    volumes:
      - ./workspace:/workspace
    working_dir: /workspace
```

## Usage in Workflows

```yaml
steps:
  - name: build-agent-image
    tool: docker_compose_build
    params:
      compose_file: docker/dev/docker-compose.yml
      service: kiro-story

  - name: run-tests
    tool: docker_compose_run
    params:
      compose_file: docker/dev/docker-compose.yml
      service: kiro-story
      command: pytest tests/ -v
      timeout: 600

  - name: cleanup
    tool: docker_compose_down
    params:
      compose_file: docker/dev/docker-compose.yml
```
