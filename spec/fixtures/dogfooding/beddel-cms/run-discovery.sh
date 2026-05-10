#!/usr/bin/env bash
# =============================================================================
# Beddel CMS — Discovery Runner
# =============================================================================
#
# Runs the discovery assistant with different backends:
#
#   ./run-discovery.sh --beddel "question here"
#     → Uses Beddel workflow engine (Gemini Flash, cheapest)
#
#   ./run-discovery.sh --kiro-sonnet "question here"
#     → Uses Kiro CLI with Claude Sonnet 4.6 (good balance)
#
#   ./run-discovery.sh --kiro-opus "question here"
#     → Uses Kiro CLI with Claude Opus 4.6 (highest quality)
#
#   ./run-discovery.sh --architect "question here"
#     → Uses OpenClaw architect (GPT-5.4, design oracle)
#
#   ./run-discovery.sh --groq "question here"
#     → Uses Beddel llm primitive with Groq (fast, free tier)
#
# All modes read DISCOVERY.md + memory.json for context continuity.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BEDDEL_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
MEMORY_FILE="$SCRIPT_DIR/memory.json"
DISCOVERY_FILE="$SCRIPT_DIR/DISCOVERY.md"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
  echo "Usage: $0 <mode> \"question\""
  echo ""
  echo "Modes:"
  echo "  --beddel       Beddel workflow (Gemini Flash)"
  echo "  --kiro-sonnet  Kiro CLI (Claude Sonnet 4.6)"
  echo "  --kiro-opus    Kiro CLI (Claude Opus 4.6)"
  echo "  --architect    OpenClaw architect (GPT-5.4)"
  echo "  --groq         Beddel llm primitive (Groq)"
  echo ""
  echo "Example:"
  echo "  $0 --beddel \"Should we use Firebase or Cloudflare for hosting?\""
  exit 1
}

[[ $# -lt 2 ]] && usage

MODE="$1"
QUESTION="$2"
CONTEXT="${3:-}"

# Load memory summary (last 3 entries)
MEMORY_SUMMARY=""
if [[ -f "$MEMORY_FILE" ]]; then
  MEMORY_SUMMARY=$(python3 -c "
import json, sys
with open('$MEMORY_FILE') as f:
    data = json.load(f)
entries = data.get('entries', [])[-3:]
for e in entries:
    print(f\"[{e['timestamp']}] {e['topic']}\")
    for d in e.get('decisions', []):
        print(f\"  - Decision: {d}\")
    for q in e.get('open_questions', [])[:2]:
        print(f\"  - Open: {q}\")
    print()
" 2>/dev/null || echo "(no memory loaded)")
fi

echo -e "${GREEN}=== Beddel CMS Discovery ===${NC}"
echo -e "Mode: ${YELLOW}$MODE${NC}"
echo -e "Question: $QUESTION"
echo ""

case "$MODE" in
  --beddel)
    echo -e "${GREEN}Running Beddel workflow...${NC}"
    source "$BEDDEL_ROOT/src/beddel-py/.venv/bin/activate" 2>/dev/null || true
    beddel run "$SCRIPT_DIR/cms-discovery-assistant.yaml" \
      -i question="$QUESTION" \
      -i context="${CONTEXT:-No additional context}"
    ;;

  --kiro-sonnet)
    echo -e "${GREEN}Running via Kiro CLI (Sonnet 4.6)...${NC}"
    PROMPT="You are helping design Beddel CMS. Read these files for context:
- $DISCOVERY_FILE (architecture analysis)
- $MEMORY_FILE (prior decisions)

Recent memory:
$MEMORY_SUMMARY

Question: $QUESTION
${CONTEXT:+Context: $CONTEXT}

Provide: 1) Recommendation with rationale 2) Trade-offs 3) Impact on migration phases 4) Next steps"

    kiro-cli chat --no-interactive -a --model claude-sonnet-4.6 "$PROMPT"
    ;;

  --kiro-opus)
    echo -e "${GREEN}Running via Kiro CLI (Opus 4.6)...${NC}"
    PROMPT="You are a senior architect helping design Beddel CMS. Read these files:
- $DISCOVERY_FILE
- $MEMORY_FILE

Recent memory:
$MEMORY_SUMMARY

Question: $QUESTION
${CONTEXT:+Context: $CONTEXT}

Provide deep analysis with: 1) Recommendation 2) Trade-offs 3) Migration impact 4) Next steps"

    kiro-cli chat --no-interactive -a --model claude-opus-4.6 "$PROMPT"
    ;;

  --architect)
    echo -e "${GREEN}Running via OpenClaw architect (GPT-5.4)...${NC}"
    PROMPT="You are reviewing the architecture for Beddel CMS — a multi-tenant static site CMS.

Existing system: Next.js monorepo + Firebase (Firestore multi-tenant, Hosting SSG, Auth+AppCheck).
New system: Beddel workflow engine wrapping the existing system, adding AI content management, billing.

Prior decisions:
$MEMORY_SUMMARY

Question: $QUESTION
${CONTEXT:+Context: $CONTEXT}

Provide architectural recommendation with trade-offs and migration impact."

    bash "$BEDDEL_ROOT/scripts/openclaw-agent.sh" --architect "$PROMPT"
    ;;

  --groq)
    echo -e "${GREEN}Running Beddel llm primitive (Groq)...${NC}"
    source "$BEDDEL_ROOT/src/beddel-py/.venv/bin/activate" 2>/dev/null || true
    # Single-step workflow using Groq for fast inference
    beddel run - <<YAML
id: cms_quick_query
name: CMS Quick Query
version: "1.0"
input_schema:
  type: object
  properties:
    question: { type: string }
  required: [question]
steps:
  - id: answer
    primitive: llm
    config:
      model: groq/llama-3.3-70b-versatile
      prompt: >
        You are helping design Beddel CMS (multi-tenant static site CMS on Beddel workflow engine).
        Prior decisions: $MEMORY_SUMMARY
        Question: $input.question
        Be concise and actionable.
      temperature: 0.3
      max_tokens: 800
YAML
    ;;

  *)
    echo -e "${RED}Unknown mode: $MODE${NC}"
    usage
    ;;
esac

echo ""
echo -e "${YELLOW}Remember to update memory.json with decisions from this session.${NC}"
