# auth-firebase-kit

Firebase Auth token verification, App Check attestation, and Firestore tenant
resolution for Beddel backends (beddel-gateway, FastAPI apps). Enables a Python
backend to authenticate requests coming from Firebase-native frontend apps.

## What it does

- **`verify_id_token`** — verifies a Firebase Auth ID token (JWT) and returns the
  decoded claims (`uid`, `email`, ...).
- **`verify_app_check`** — verifies a Firebase App Check attestation token.
- **`resolve_tenant`** — resolves a user's tenant membership and role from
  Firestore (`tenants/{tenantId}/members/{uid}`).
- **`firebase_auth_dependency`** — a FastAPI dependency that wires the three calls
  together: extracts headers, verifies the token + App Check, and scopes the
  request to a tenant.

## Dependencies

- `firebase-admin>=6.5.0`
- `google-cloud-firestore>=2.16.0`
- `pydantic>=2.0`
- `fastapi>=0.100` (only required for `middleware.py`)

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's
`python/` directory to your Python path:

```bash
export PYTHONPATH="kits/auth-firebase-kit/python:$PYTHONPATH"
```

## Usage

```python
from beddel_auth_firebase import (
    verify_id_token,
    verify_app_check,
    resolve_tenant,
    firebase_auth_dependency,
)

# 1. Verify a Firebase Auth ID token (project_id defaults to GOOGLE_CLOUD_PROJECT)
decoded = verify_id_token(id_token)
print(decoded.uid, decoded.email)

# 2. Verify a Firebase App Check token
claims = verify_app_check(app_check_token)
print(claims.app_id)

# 3. Resolve tenant membership from Firestore (async)
from google.cloud.firestore_v1 import AsyncClient

db = AsyncClient(project="my-project")
membership = await resolve_tenant(decoded.uid, db, tenant_id="acme")
print(membership.role)
```

### FastAPI integration

```python
from fastapi import Depends, FastAPI
from google.cloud.firestore_v1 import AsyncClient
from beddel_auth_firebase import AuthContext, firebase_auth_dependency

app = FastAPI()
app.state.firestore_db = AsyncClient(project="my-project")


@app.get("/workflows")
async def list_workflows(ctx: AuthContext = Depends(firebase_auth_dependency)):
    return {"uid": ctx.uid, "tenant": ctx.tenant_id, "role": ctx.role}
```

The dependency reads these request headers:

| Header | Required | Purpose |
|--------|----------|---------|
| `Authorization: Bearer <id_token>` | yes | Firebase Auth ID token |
| `X-Firebase-AppCheck: <token>` | no | App Check attestation |
| `X-Tenant-Id: <tenant_id>` | no | Target tenant (multi-tenant routing) |

## Configuration

`project_id` is resolved in this order:

1. Explicit `project_id` argument.
2. `GOOGLE_CLOUD_PROJECT` environment variable.
3. The default initialized `firebase_admin` app.

No secrets are stored in code — credentials use Application Default Credentials
(ADC) and the project id comes from the environment.

## Running tests

```bash
cd kits/auth-firebase-kit
python -m pytest tests/ -x
```
