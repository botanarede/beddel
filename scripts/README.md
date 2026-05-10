# Developer Utility Scripts

These scripts are **developer utilities** and are NOT run in CI.

They require the `beddel-py` SDK to be installed:

```bash
pip install beddel
```

## Scripts

### sync_kit_schema.py

Regenerates `spec/kits/kit-manifest.schema.json` from the `SolutionKit` Pydantic model.

```bash
python scripts/sync_kit_schema.py
```

### sync_workflow_schema.py

Regenerates `spec/schemas/workflow.schema.json` from the `Workflow` Pydantic model.

```bash
python scripts/sync_workflow_schema.py
```

Run these scripts after modifying the Pydantic models in `beddel-py` to keep the
committed JSON Schema files in sync with the runtime models.
