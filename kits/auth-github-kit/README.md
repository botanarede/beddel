# auth-github-kit

GitHub OAuth Device Flow credential provider for the Beddel SDK. Manages reading, writing, and deleting locally-stored GitHub OAuth credentials at an XDG-compliant path.

## Dependencies

- `httpx>=0.27`

## Install

The kit is part of the Beddel monorepo. To use it standalone, add the kit's `src/` directory to your Python path:

```bash
export PYTHONPATH="kits/auth-github-kit/src:$PYTHONPATH"
```

## Usage

```python
from beddel_auth_github.provider import load_credentials, save_credentials, delete_credentials

# Save credentials
save_credentials({
    "access_token": "gho_abc123",
    "github_user": "octocat",
    "server_url": "https://dash.example.com",
    "created_at": "2026-03-27T00:00:00Z",
})

# Load credentials
creds = load_credentials()
if creds:
    print(creds["github_user"])

# Delete credentials
deleted = delete_credentials()
```

## Running Tests

```bash
cd kits/auth-github-kit
python -m pytest tests/ -x
```
