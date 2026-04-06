# software-development-kit

A reference Solution Kit bundling validation gate tools and a `create-epic` workflow.

## What is a Solution Kit?

A Solution Kit is a distributable package that bundles tools, workflows, adapters,
and contracts into a single unit. Kits are discovered automatically from configured
directories and their tools are registered in the Beddel tool registry.

## How kit.yaml Works

Every kit has a `kit.yaml` manifest at its root. The manifest declares:

- **name** — unique identifier in kebab-case (e.g. `software-development-kit`)
- **version** — semver string (e.g. `0.1.0`)
- **description** — human-readable summary
- **author** — optional attribution
- **tools** — list of tool declarations with `name`, `target`, `description`, `category`
- **workflows** — list of workflow YAML assets with `name`, `path`, `description`

Tool targets use `module.path:function_name` format. The module path is resolved
via `importlib.import_module()`, so the kit package must be importable.

## How to Add Tools

1. Create a Python module under `tools/` (or any sub-package).
2. Define a function that accepts typed arguments and returns a structured dict.
3. Add a tool entry to `kit.yaml`:

```yaml
tools:
  - name: my_tool
    target: "kits.my_kit.tools.module:my_tool"
    description: "What it does"
    category: general
```

## How to Add Workflows

1. Create a YAML file under `workflows/`.
2. Define steps following the Beddel workflow schema.
3. Add a workflow entry to `kit.yaml`:

```yaml
workflows:
  - name: my-workflow
    path: workflows/my-workflow.yaml
    description: "What it does"
```

## How to Test Your Kit

```python
from pathlib import Path
from beddel.domain.kit import parse_kit_manifest
from beddel.tools.kits import load_kit

manifest = parse_kit_manifest(Path("kits/my-kit/kit.yaml"))
tools = load_kit(manifest)
result = tools["my_tool"](project_path=".")
assert result["passed"] is True
```
