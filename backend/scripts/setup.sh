#!/usr/bin/env bash
# One-shot local setup for the gen-ai backend — safe to re-run (every step
# checks for existing state first). Does NOT start the service; see
# install_systemd.sh for that, or run it directly with uvicorn.
#
# What this does, in order:
#   1. Create/verify the Python venv and install dependencies.
#   2. Generate .env (with real, freshly-generated secrets) if missing.
#   3. Create the Postgres role + database this service uses, if missing.
#   4. Enable the pgvector extension, if available and not already enabled.
#   5. Run Alembic migrations.
#   6. Optionally seed the first admin user (only if none exists yet).
#
# What this does NOT do: install Ollama or Qdrant (see
# install_qdrant.sh for Qdrant — Ollama is a one-line `curl -fsSL
# https://ollama.com/install.sh | sh` and isn't gen-ai-specific enough to
# script here), or set up the systemd service (see install_systemd.sh).

set -euo pipefail
cd "$(dirname "$0")/.."   # backend/

DB_NAME="${GENAI_DB_NAME:-genai_dev}"
DB_ROLE="${GENAI_DB_ROLE:-genai}"

echo "==> [1/6] Python virtual environment"
if [ ! -d venv ]; then
    python3 -m venv venv
    echo "    created venv/"
else
    echo "    venv/ already exists"
fi
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
echo "    dependencies installed"

echo "==> [2/6] .env"
if [ ! -f .env ]; then
    if ! ./venv/bin/python -c "import cryptography" 2>/dev/null; then
        echo "    ERROR: cryptography package not yet installed — re-run after step 1 completes." >&2
        exit 1
    fi
    DB_PASS=$(openssl rand -hex 24)
    ENCRYPTION_KEY=$(./venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    JWT_SECRET=$(openssl rand -hex 32)
    cat > .env <<EOF
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://${DB_ROLE}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ALGORITHM=HS256
ENCRYPTION_KEY=${ENCRYPTION_KEY}
VECTOR_DATA_DIR=./data/vectors
DEFAULT_RATE_LIMIT_PER_MINUTE=120
EOF
    echo "    generated .env with fresh secrets (DATABASE_URL password: ${DB_PASS})"
    GENAI_DB_PASS="$DB_PASS"
else
    echo "    .env already exists — leaving it alone"
    GENAI_DB_PASS=$(grep DATABASE_URL .env | sed -E "s#.*${DB_ROLE}:([^@]+)@.*#\1#")
fi

echo "==> [3/6] Postgres role + database"
if ! command -v psql >/dev/null 2>&1 && ! sudo -n -u postgres psql -tAc "SELECT 1;" >/dev/null 2>&1; then
    echo "    WARNING: cannot reach postgres as the 'postgres' superuser (no passwordless sudo, or postgres not installed)." >&2
    echo "    Create the role/database manually, then re-run this script:" >&2
    echo "      sudo -u postgres psql -c \"CREATE ROLE ${DB_ROLE} WITH LOGIN PASSWORD '<password matching .env>';\"" >&2
    echo "      sudo -u postgres psql -c \"CREATE DATABASE ${DB_NAME} OWNER ${DB_ROLE};\"" >&2
    echo "    Alternatively, see ../database/README.md for a Docker-based Postgres option requiring no sudo." >&2
else
    ROLE_EXISTS=$(sudo -n -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_ROLE}';" 2>/dev/null || echo "")
    if [ -z "$ROLE_EXISTS" ]; then
        sudo -n -u postgres psql -c "CREATE ROLE ${DB_ROLE} WITH LOGIN PASSWORD '${GENAI_DB_PASS}';" >/dev/null
        echo "    created role '${DB_ROLE}'"
    else
        echo "    role '${DB_ROLE}' already exists"
    fi

    DB_EXISTS=$(sudo -n -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}';" 2>/dev/null || echo "")
    if [ -z "$DB_EXISTS" ]; then
        sudo -n -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_ROLE};" >/dev/null
        echo "    created database '${DB_NAME}'"
    else
        echo "    database '${DB_NAME}' already exists"
    fi

    echo "==> [4/6] pgvector extension"
    PGVECTOR_AVAILABLE=$(sudo -n -u postgres psql -d "${DB_NAME}" -tAc "SELECT 1 FROM pg_available_extensions WHERE name='vector';" 2>/dev/null || echo "")
    if [ -z "$PGVECTOR_AVAILABLE" ]; then
        echo "    pgvector extension not available on this Postgres install." >&2
        echo "    Install it if you plan to use the pgvector backend: sudo apt install postgresql-16-pgvector" >&2
        echo "    (adjust the version number to match your Postgres major version)" >&2
    else
        sudo -n -u postgres psql -d "${DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null
        sudo -n -u postgres psql -d "${DB_NAME}" -c "GRANT ALL ON SCHEMA public TO ${DB_ROLE};" >/dev/null
        echo "    pgvector extension enabled"
    fi
fi

echo "==> [5/6] Alembic migrations"
./venv/bin/alembic upgrade head
echo "    up to date"

echo "==> [6/6] Admin user"
ADMIN_COUNT=$(sudo -n -u postgres psql -d "${DB_NAME}" -tAc "SELECT count(*) FROM admin_users;" 2>/dev/null || echo "0")
if [ "$ADMIN_COUNT" = "0" ]; then
    echo "    No admin user exists yet."
    read -rp "    Seed one now? [y/N] " SEED_ANSWER
    if [[ "$SEED_ANSWER" =~ ^[Yy]$ ]]; then
        read -rp "    Admin email: " ADMIN_EMAIL
        read -rsp "    Admin password: " ADMIN_PASSWORD
        echo
        ./venv/bin/python scripts/seed_admin.py "$ADMIN_EMAIL" "$ADMIN_PASSWORD"
    else
        echo "    Skipped — run manually later: ./venv/bin/python scripts/seed_admin.py <email> <password>"
    fi
else
    echo "    ${ADMIN_COUNT} admin user(s) already exist — skipping"
fi

echo ""
echo "Setup complete. Start the service with:"
echo "  ./venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8020"
echo "or install it as a persistent systemd service: ./scripts/install_systemd.sh"
