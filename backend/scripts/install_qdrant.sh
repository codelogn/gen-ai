#!/usr/bin/env bash
# Optional — only needed if you plan to use the "qdrant" vector backend
# (see docs/04-vector-store-adapters.md). Installs Qdrant's official .deb
# package and runs it as its own systemd service, bound to 127.0.0.1 only.
#
# Not run automatically by setup.sh, since not every deployment needs
# Qdrant — sqlite_vec and pgvector need no separate server at all.

set -euo pipefail

QDRANT_VERSION="${QDRANT_VERSION:-1.19.0}"
DEB_URL="https://github.com/qdrant/qdrant/releases/download/v${QDRANT_VERSION}/qdrant_${QDRANT_VERSION}-1_amd64.deb"
RUN_USER="${SUDO_USER:-$USER}"

if command -v qdrant >/dev/null 2>&1; then
    echo "Qdrant is already installed ($(qdrant --version))."
else
    echo "==> Downloading Qdrant v${QDRANT_VERSION}..."
    TMP_DEB=$(mktemp --suffix=.deb)
    curl -fsSL -o "$TMP_DEB" "$DEB_URL"
    sudo dpkg -i "$TMP_DEB"
    rm -f "$TMP_DEB"
fi

echo "==> Configuring (127.0.0.1 only — see docs/10-latest-practices-checklist.md)"
sudo mkdir -p /var/lib/qdrant
sudo chown -R "${RUN_USER}:${RUN_USER}" /var/lib/qdrant

sudo tee /etc/qdrant/config.yaml > /dev/null <<'EOF'
storage:
  storage_path: /var/lib/qdrant/storage
  snapshots_path: /var/lib/qdrant/snapshots

service:
  static_content_dir: /var/lib/qdrant/static
  host: 127.0.0.1
  http_port: 6333
  grpc_port: 6334
EOF

echo "==> Installing systemd service"
sudo tee /etc/systemd/system/qdrant.service > /dev/null <<EOF
[Unit]
Description=Qdrant vector database (gen-ai QdrantAdapter backend)
After=network.target

[Service]
Type=simple
User=${RUN_USER}
ExecStart=/usr/bin/qdrant --config-path /etc/qdrant/config.yaml
Restart=always
RestartSec=5
StandardOutput=append:/var/log/qdrant.log
StandardError=append:/var/log/qdrant.log

[Install]
WantedBy=multi-user.target
EOF

sudo touch /var/log/qdrant.log
sudo chown "${RUN_USER}:${RUN_USER}" /var/log/qdrant.log

sudo systemctl daemon-reload
sudo systemctl enable qdrant
sudo systemctl restart qdrant

sleep 2
curl -sf http://127.0.0.1:6333/ >/dev/null && echo "Qdrant is up at http://127.0.0.1:6333" || echo "WARNING: Qdrant doesn't seem to be responding yet — check: sudo systemctl status qdrant"
