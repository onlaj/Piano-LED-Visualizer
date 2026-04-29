#!/usr/bin/env bash
set -euo pipefail

PLV_DIR="${PLV_DIR:-/home/Piano-LED-Visualizer}"
STAMP="$(date +%Y%m%d-%H%M%S)"

run() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo -n "$@"
  fi
}

unit_exists() {
  systemctl list-unit-files "$1" --no-legend --no-pager 2>/dev/null | grep -q .
}

backup_file() {
  local path="$1"
  if [ -e "$path" ]; then
    run cp -a "$path" "${path}.bak-lowlatency-${STAMP}"
  fi
}

echo "Applying PLV low-latency runtime tuning..."

run install -m 0755 /dev/stdin /usr/local/sbin/plv-lowlatency-apply.sh <<'EOF'
#!/usr/bin/env bash
set -u

for governor in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
  [ -e "$governor" ] || continue
  if grep -qw performance "$(dirname "$governor")/scaling_available_governors" 2>/dev/null; then
    echo performance > "$governor" 2>/dev/null || true
  fi
done

if command -v iw >/dev/null 2>&1; then
  for iface in $(iw dev 2>/dev/null | awk '$1 == "Interface" {print $2}'); do
    iw dev "$iface" set power_save off 2>/dev/null || true
  done
fi

if command -v vcgencmd >/dev/null 2>&1; then
  vcgencmd get_throttled || true
fi
EOF

run install -d /etc/systemd/system
run install -m 0644 /dev/stdin /etc/systemd/system/plv-lowlatency.service <<'EOF'
[Unit]
Description=Piano LED Visualizer low-latency tuning
After=NetworkManager.service wpa_supplicant.service
Before=visualizer.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/plv-lowlatency-apply.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

echo "Configuring visualizer.service override..."
OVERRIDE_DIR="/etc/systemd/system/visualizer.service.d"
OVERRIDE_FILE="${OVERRIDE_DIR}/override.conf"
run install -d "$OVERRIDE_DIR"
backup_file "$OVERRIDE_FILE"
run install -m 0644 /dev/stdin "$OVERRIDE_FILE" <<EOF
[Unit]
After=network-online.target plv-lowlatency.service
Wants=network-online.target plv-lowlatency.service

[Service]
WorkingDirectory=${PLV_DIR}/
ExecStart=
ExecStart=/usr/bin/python3 ${PLV_DIR}/visualizer.py
Restart=always
RestartSec=1
User=root
Group=root
SupplementaryGroups=audio gpio spi i2c video input render
UMask=0002
Nice=-10
IOSchedulingClass=realtime
IOSchedulingPriority=0
CPUSchedulingPolicy=rr
CPUSchedulingPriority=5
LimitRTPRIO=10
LimitNICE=-10
LimitMEMLOCK=64M
EOF

echo "Disabling reversible background services..."
for unit in bluetooth.service ModemManager.service triggerhappy.service triggerhappy.socket apt-daily.timer apt-daily-upgrade.timer; do
  if unit_exists "$unit"; then
    run systemctl disable --now "$unit" || true
  fi
done

echo "Disabling NetworkManager Wi-Fi power save..."
run install -d /etc/NetworkManager/conf.d
run install -m 0644 /dev/stdin /etc/NetworkManager/conf.d/30-wifi-powersave-off.conf <<'EOF'
[connection]
wifi.powersave=2
EOF

echo "Removing obsolete reliable_midi enable/required flags from PLV XML config..."
if [ -d "${PLV_DIR}/config" ]; then
  for xml in "${PLV_DIR}/config/settings.xml" "${PLV_DIR}/config/default_settings.xml"; do
    [ -f "$xml" ] || continue
    backup_file "$xml"
    run python3 - "$xml" <<'PY'
import sys
import xml.etree.ElementTree as ET

path = sys.argv[1]
tree = ET.parse(path)
root = tree.getroot()
for tag in ("reliable_midi_enabled", "reliable_midi_required"):
    elem = root.find(tag)
    if elem is not None:
        root.remove(elem)
for tag, value in (("reliable_midi_host", "oscmidi-rtp.local"), ("reliable_midi_port", "5056")):
    elem = root.find(tag)
    if elem is None:
        elem = ET.SubElement(root, tag)
    if not (elem.text or "").strip():
        elem.text = value
tree.write(path)
PY
  done
fi

echo "Cleaning safe caches..."
run apt-get clean || true
run journalctl --vacuum-size=16M || true
run find /tmp -mindepth 1 -maxdepth 1 -mtime +1 -exec rm -rf -- {} + 2>/dev/null || true

echo "Reloading systemd and applying boot tuning..."
run systemctl daemon-reload
run systemctl enable plv-lowlatency.service
run systemctl start plv-lowlatency.service

echo "Restarting visualizer.service with validation..."
run systemctl restart visualizer.service
sleep 3
if ! systemctl is-active --quiet visualizer.service; then
  echo "visualizer.service failed after low-latency override; leaving backups in place and printing status." >&2
  systemctl status visualizer.service --no-pager >&2 || true
  exit 1
fi

echo "Low-latency configuration applied."
systemctl is-active visualizer.service
systemctl is-enabled plv-lowlatency.service
for governor in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
  [ -e "$governor" ] && printf '%s=%s\n' "$governor" "$(cat "$governor")"
done
command -v vcgencmd >/dev/null 2>&1 && vcgencmd get_throttled || true
