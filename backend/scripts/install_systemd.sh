#!/usr/bin/env bash
# Installs gen-ai as a persistent systemd service — Type=simple,
# Restart=always, matching the same shape used for every other Python
# service on this host (see docs/01-architecture.md). Safe to re-run;
# just rewrites the unit file and reloads/restarts.
#
# Requires: ./setup.sh already run (venv + .env must exist).

set -euo pipefail
cd "$(dirname "$0")/.."   # backend/
BACKEND_DIR="$(pwd)"
SERVICE_NAME="${GENAI_SERVICE_NAME:-gen-ai-backend}"
PORT="${GENAI_PORT:-8020}"
RUN_USER="${SUDO_USER:-$USER}"

if [ ! -f venv/bin/uvicorn ] && [ ! -f venv/bin/python ]; then
    echo "ERROR: venv/ not found — run ./scripts/setup.sh first." >&2
    exit 1
fi
if [ ! -f .env ]; then
    echo "ERROR: .env not found — run ./scripts/setup.sh first." >&2
    exit 1
fi

mkdir -p data

sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null <<EOF
[Unit]
Description=gen-ai shared AI memory & RAG service
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${BACKEND_DIR}
EnvironmentFile=${BACKEND_DIR}/.env
ExecStart=${BACKEND_DIR}/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port ${PORT}
Restart=always
RestartSec=5
StandardOutput=append:${BACKEND_DIR}/data/app.log
StandardError=append:${BACKEND_DIR}/data/app.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

sleep 2
sudo systemctl status "${SERVICE_NAME}" --no-pager | head -8

echo ""
echo "Installed and started. Logs: ${BACKEND_DIR}/data/app.log"
echo "Manage it with: sudo systemctl {status|stop|start|restart} ${SERVICE_NAME}"
