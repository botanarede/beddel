# Source Scout MCP Server

Discover, validate, and rank RSS/API/blog sources for any theme via MCP.

## How It Works

```
User asks: "Find sources about gastronomia africana"
    ↓
MCP tool call: scout_sources(theme="gastronomia africana")
    ↓
Beddel workflow executes 4 steps:
  1. discover — LLM finds sources + outputs JSON (single call, saves tokens)
  2. validate — HTTP smoke test on a known feed
  3. rank    — LLM scores and sorts by quality
  4. output  — returns final JSON array
    ↓
Returns: JSON array of ranked sources with feed URLs, scores, priorities
```

## Token Budget

~3k tokens per run (Groq free tier: 12k TPM, so ~4 runs/minute).

| Step | Input tokens | Output tokens |
|------|-------------|---------------|
| discover | ~200 | ~1000 |
| validate | 0 (HTTP) | 0 |
| rank | ~1200 | ~1000 |
| **Total** | **~1400** | **~2000** |

## Setup

```bash
# 1. Ensure beddel is installed (slim core + on-demand kits via `beddel init`)
pip install beddel && beddel init

# 2. Set Groq API key
export GROQ_API_KEY="gsk_..."

# 3. Test standalone
python server.py --test "samba e pagode"

# 4. Add to MCP config (~/.kiro/settings/mcp.json)
```

## MCP Configuration

```json
{
  "source-scout": {
    "command": "python",
    "args": ["/full/path/to/spec/fixtures/dogfooding/source-scout-mcp/server.py"],
    "env": {
      "GROQ_API_KEY": "gsk_..."
    },
    "autoApprove": ["scout_sources"]
  }
}
```

## Tool: scout_sources

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| theme | string | yes | Topic (e.g. "cultura negra", "jazz", "receitas africanas") |
| max_sources | string | no | Max results (default: "8") |
| lang | string | no | Language: "pt-br", "en", "any" (default: "any") |

## Example Output

```json
[
  {
    "name": "Notícia Preta",
    "url": "https://noticiapreta.com.br",
    "feed_url": "https://noticiapreta.com.br/feed/",
    "type": "news",
    "lang": "pt-br",
    "desc": "Black journalism outlet, daily updates",
    "score": 0.9,
    "priority": "high"
  }
]
```
