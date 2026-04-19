#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${1:-rtpmidid}"
OVERRIDE_DIR="/etc/systemd/system/${SERVICE_NAME}.service.d"
OVERRIDE_FILE="${OVERRIDE_DIR}/override.conf"
NM_CONF_DIR="/etc/NetworkManager/conf.d"
NM_CONF_FILE="${NM_CONF_DIR}/30-wifi-powersave-off.conf"

echo "Configuring systemd override for ${SERVICE_NAME}..."
sudo install -d "${OVERRIDE_DIR}"
cat <<'EOF' | sudo tee "${OVERRIDE_FILE}" >/dev/null
[Unit]
After=network-online.target
Wants=network-online.target

[Service]
Restart=always
RestartSec=2
EOF

echo "Disabling NetworkManager Wi-Fi power save..."
sudo install -d "${NM_CONF_DIR}"
cat <<'EOF' | sudo tee "${NM_CONF_FILE}" >/dev/null
[connection]
wifi.powersave=2
EOF

echo "Reloading services..."
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

if systemctl is-active --quiet NetworkManager; then
  sudo systemctl restart NetworkManager
fi

if command -v iw >/dev/null 2>&1; then
  sudo iw dev wlan0 set power_save off || true
fi

echo "Done."
