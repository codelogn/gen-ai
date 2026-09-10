#!/usr/bin/env bash
# Registers this example as a gen-ai application, issues it an API key, and
# writes both into ./.env — the one manual step docker-compose can't do for
# you, since it requires an admin login. Safe to re-run: if an application
# with this slug already exists, it just issues a fresh key for it instead
# of failing.
#
# Uses a DISTINCT slug from the Python sibling (example-chat-client-java
# vs example-chat-client) so the two examples never share gen-ai data,
# even though both use the same "messages"/"documents" namespace NAMES —
# gen-ai scopes all memories per-application.
#
# Usage: ./scripts/register_app.sh [gen-ai admin email] [gen-ai admin password]
# (prompts for whichever isn't passed as an argument)

set -euo pipefail
cd "$(dirname "$0")/.."   # examples/chat-client-java/

GENAI_URL="${GENAI_URL:-http://127.0.0.1:8020}"
APP_SLUG="${APP_SLUG:-example-chat-client-java}"
APP_DISPLAY_NAME="${APP_DISPLAY_NAME:-Example Chat Client (Java)}"

ADMIN_EMAIL="${1:-}"
ADMIN_PASSWORD="${2:-}"
if [ -z "$ADMIN_EMAIL" ]; then
    read -rp "gen-ai admin email: " ADMIN_EMAIL
fi
if [ -z "$ADMIN_PASSWORD" ]; then
    read -rsp "gen-ai admin password: " ADMIN_PASSWORD
    echo
fi

if ! curl -sf "${GENAI_URL}/health" >/dev/null; then
    echo "ERROR: gen-ai is not reachable at ${GENAI_URL} — start it first." >&2
    exit 1
fi

echo "==> Logging in to gen-ai..."
LOGIN_RESPONSE=$(curl -sf -X POST "${GENAI_URL}/admin/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"${ADMIN_EMAIL}\", \"password\": \"${ADMIN_PASSWORD}\"}")
TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

echo "==> Checking for an existing '${APP_SLUG}' application..."
EXISTING_ID=$(curl -sf "${GENAI_URL}/admin/api/v1/applications" -H "Authorization: Bearer ${TOKEN}" \
    | python3 -c "
import sys, json
apps = json.load(sys.stdin)
for a in apps:
    if a['slug'] == '${APP_SLUG}':
        print(a['id'])
        break
")

if [ -n "$EXISTING_ID" ]; then
    APP_ID="$EXISTING_ID"
    echo "    found existing application: ${APP_ID}"
else
    echo "==> Registering a new application '${APP_SLUG}'..."
    CREATE_RESPONSE=$(curl -sf -X POST "${GENAI_URL}/admin/api/v1/applications" \
        -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
        -d "{
            \"slug\": \"${APP_SLUG}\",
            \"display_name\": \"${APP_DISPLAY_NAME}\",
            \"vector_backend\": \"sqlite_vec\",
            \"retrieval_strategy\": \"native\",
            \"embedding_provider\": \"ollama\",
            \"embedding_model\": \"nomic-embed-text\"
        }")
    APP_ID=$(echo "$CREATE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
    echo "    created: ${APP_ID}"
fi

echo "==> Issuing a new API key..."
KEY_RESPONSE=$(curl -sf -X POST "${GENAI_URL}/admin/api/v1/applications/${APP_ID}/api-keys" \
    -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
    -d "{\"label\": \"registered by register_app.sh on $(date -Iseconds)\"}")
FULL_KEY=$(echo "$KEY_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['full_key'])")

if [ -f .env ]; then
    # Replace an existing GENAI_API_KEY line, or append if missing.
    if grep -q '^GENAI_API_KEY=' .env; then
        sed -i "s#^GENAI_API_KEY=.*#GENAI_API_KEY=${FULL_KEY}#" .env
    else
        echo "GENAI_API_KEY=${FULL_KEY}" >> .env
    fi
else
    cp .env.example .env 2>/dev/null || touch .env
    echo "GENAI_API_KEY=${FULL_KEY}" >> .env
fi

echo ""
echo "Done. GENAI_API_KEY written to .env — this key will not be shown again"
echo "(re-run this script to issue a fresh one if you lose it)."
echo ""
echo "Start the example with: docker compose up --build"
