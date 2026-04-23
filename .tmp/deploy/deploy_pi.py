import pathlib
import sys
import time

import paramiko


HOST = "pianoledvisualizer.local"
USER = "plv"
PASSWORD = "visualizer"

LOCAL_ZIP = pathlib.Path(".tmp/deploy/plv-deploy.zip")
REMOTE_ZIP = "/home/plv/plv-deploy.zip"
REMOTE_SETTINGS_BACKUP = "/home/plv/settings.xml.backup"
APP_DIR = "/home/Piano-LED-Visualizer"
OLD_DIR = "/home/Piano-LED-Visualizer.__old__"
SERVICE = "visualizer"


REMOTE_SCRIPT = r"""
set -euo pipefail

APP_DIR="/home/Piano-LED-Visualizer"
OLD_DIR="/home/Piano-LED-Visualizer.__old__"
ZIP_PATH="/home/plv/plv-deploy.zip"
SETTINGS_BACKUP="/home/plv/settings.xml.backup"
SERVICE="visualizer"
ROLLED_BACK=0

rollback() {
    if [ "$ROLLED_BACK" -eq 1 ]; then
        return 0
    fi
    ROLLED_BACK=1
    echo "[rollback] restoring previous project"
    sudo systemctl stop "$SERVICE" || true
    sudo rm -rf "$APP_DIR"
    if [ -d "$OLD_DIR" ]; then
        sudo mv "$OLD_DIR" "$APP_DIR"
        sudo chown -R plv:plv "$APP_DIR"
    fi
    sudo systemctl start "$SERVICE" || true
}

trap 'rc=$?; echo "[error] deployment failed with code $rc"; rollback; exit $rc' ERR

echo "[step] capture current settings"
if [ -f "$APP_DIR/config/settings.xml" ]; then
    cp "$APP_DIR/config/settings.xml" "$SETTINGS_BACKUP"
elif [ ! -f "$SETTINGS_BACKUP" ]; then
    echo "[warn] no existing settings.xml found"
fi

echo "[step] stop service"
sudo systemctl stop "$SERVICE" || true

echo "[step] rotate old app"
sudo rm -rf "$OLD_DIR"
if [ -d "$APP_DIR" ]; then
    sudo mv "$APP_DIR" "$OLD_DIR"
fi
sudo mkdir -p "$APP_DIR"

echo "[step] extract new app"
sudo python3 - <<'PY'
import os
import stat
import zipfile

zip_path = "/home/plv/plv-deploy.zip"
dest = "/home/Piano-LED-Visualizer"

with zipfile.ZipFile(zip_path) as archive:
    for info in archive.infolist():
        target = os.path.join(dest, info.filename)
        normalized = os.path.normpath(target)
        if not normalized.startswith(dest):
            raise RuntimeError(f"Refusing to extract outside target: {info.filename}")
        if info.is_dir():
            os.makedirs(normalized, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(normalized), exist_ok=True)
        with archive.open(info) as src, open(normalized, "wb") as dst:
            dst.write(src.read())
        mode = info.external_attr >> 16
        if mode:
            os.chmod(normalized, mode)
PY

echo "[step] restore settings"
if [ -f "$SETTINGS_BACKUP" ]; then
    sudo mkdir -p "$APP_DIR/config"
    sudo cp "$SETTINGS_BACKUP" "$APP_DIR/config/settings.xml"
fi

echo "[step] fix ownership"
sudo chown -R plv:plv "$APP_DIR"
sudo chmod -R u+rwX,go+rX "$APP_DIR"

echo "[step] install requirements"
cd "$APP_DIR"
sudo python3 -m pip install -r requirements.txt

echo "[step] start service"
sudo systemctl start "$SERVICE"
sleep 3

echo "[step] verify service"
sudo systemctl is-active "$SERVICE"
sudo systemctl --no-pager --full status "$SERVICE" -n 25

echo "[step] cleanup old app"
sudo rm -rf "$OLD_DIR"
rm -f "$ZIP_PATH"
echo "[done] deployment complete"
"""


def run_remote(ssh_client, command, timeout=1200):
    stdin, stdout, stderr = ssh_client.exec_command(command, get_pty=True, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def main():
    if not LOCAL_ZIP.exists():
        raise SystemExit(f"Missing deployment bundle: {LOCAL_ZIP}")

    print(f"[local] using bundle {LOCAL_ZIP} ({LOCAL_ZIP.stat().st_size} bytes)")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, username=USER, password=PASSWORD, timeout=20)

    try:
        with client.open_sftp() as sftp:
            print("[local] uploading bundle")
            sftp.put(str(LOCAL_ZIP), REMOTE_ZIP)

        print("[remote] starting deployment")
        transport = client.get_transport()
        channel = transport.open_session()
        channel.get_pty()
        channel.exec_command("bash -s")
        channel.sendall(REMOTE_SCRIPT.encode("ascii"))
        channel.shutdown_write()

        chunks = []
        while True:
            if channel.recv_ready():
                data = channel.recv(4096).decode("utf-8", "replace")
                sys.stdout.write(data)
                sys.stdout.flush()
                chunks.append(data)
            if channel.recv_stderr_ready():
                data = channel.recv_stderr(4096).decode("utf-8", "replace")
                sys.stderr.write(data)
                sys.stderr.flush()
            if channel.exit_status_ready():
                while channel.recv_ready():
                    data = channel.recv(4096).decode("utf-8", "replace")
                    sys.stdout.write(data)
                    sys.stdout.flush()
                    chunks.append(data)
                while channel.recv_stderr_ready():
                    data = channel.recv_stderr(4096).decode("utf-8", "replace")
                    sys.stderr.write(data)
                    sys.stderr.flush()
                break
            time.sleep(0.2)

        exit_code = channel.recv_exit_status()
        print(f"[remote] exit code: {exit_code}")
        if exit_code != 0:
            raise SystemExit(exit_code)

        code, out, err = run_remote(
            client,
            "systemctl is-active visualizer && "
            "readlink -f /home/Piano-LED-Visualizer && "
            "test -f /home/Piano-LED-Visualizer/config/settings.xml && echo SETTINGS_OK",
            timeout=60,
        )
        sys.stdout.write(out)
        sys.stderr.write(err)
        if code != 0:
            raise SystemExit(code)
    finally:
        client.close()


if __name__ == "__main__":
    main()
