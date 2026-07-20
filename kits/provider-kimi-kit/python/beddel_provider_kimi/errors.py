"""Error code constants for provider-kimi-kit.

Error codes BEDDEL-ADAPT-060..065 as defined in architecture §40.6.
"""

# Auth failure (401/403)
ADAPT_KIMI_AUTH: str = "BEDDEL-ADAPT-060"

# Rate limit exceeded (429)
ADAPT_KIMI_RATE_LIMIT: str = "BEDDEL-ADAPT-061"

# Model not found (404)
ADAPT_KIMI_MODEL_UNAVAILABLE: str = "BEDDEL-ADAPT-062"

# Invalid params / K3 policy conflict (400)
ADAPT_KIMI_PARAM_REJECTED: str = "BEDDEL-ADAPT-063"

# Request timeout
ADAPT_TIMEOUT: str = "BEDDEL-ADAPT-064"

# Catch-all provider error (unexpected)
ADAPT_PROVIDER_ERROR: str = "BEDDEL-ADAPT-065"
