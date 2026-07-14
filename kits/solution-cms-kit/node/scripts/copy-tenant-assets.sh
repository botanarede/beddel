#!/usr/bin/env bash
# Copies tenant-specific assets into the app's public/ directory before build.
# Reads EXPORT_TENANT_ID to determine which tenant assets to copy.
# Adapted for kit-internal paths (bonar-cms-kit/node/).
#
# Structure:
#   tenants-assets/{tenantId}/
#     images/         → copied to public/images/
#     favicon.ico     → copied to public/favicon.ico
#     robots.txt      → copied to public/robots.txt
#     (any file/dir)  → copied to public/

set -euo pipefail

# Resolve node/ root (this script lives at node/scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TENANT_ID="${EXPORT_TENANT_ID:-}"
APP_PUBLIC="$ROOT/apps/bonar-creator-studio/public"

# Clean entire public directory (all assets are tenant-specific)
rm -rf "$APP_PUBLIC"
mkdir -p "$APP_PUBLIC"

if [ -z "$TENANT_ID" ]; then
  echo "[copy-tenant-assets] No EXPORT_TENANT_ID set, skipping."
  exit 0
fi

SOURCE="$ROOT/tenants-assets/$TENANT_ID"

if [ ! -d "$SOURCE" ]; then
  echo "[copy-tenant-assets] No assets at $SOURCE, skipping."
  exit 0
fi

# Copy entire tenant asset tree into public/ (preserves internal structure)
cp -r "$SOURCE/"* "$APP_PUBLIC/"
echo "[copy-tenant-assets] Copied tenants-assets/$TENANT_ID/* → public/"
