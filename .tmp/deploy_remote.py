import paramiko
import sys


HOST = "pianoledvisualizer.local"
USER = "plv"
PASSWORD = "visualizer"


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=HOST, username=USER, password=PASSWORD, timeout=20)
    try:
        deploy_script = """#!/usr/bin/env bash
set -euo pipefail
rollback() {
  echo "ROLLBACK"
  sudo rm -rf /home/Piano-LED-Visualizer
  if [ -d /home/Piano-LED-Visualizer.__old__ ]; then
    sudo mv /home/Piano-LED-Visualizer.__old__ /home/Piano-LED-Visualizer
  fi
  sudo systemctl start visualizer || true
}
trap rollback ERR

sudo systemctl stop visualizer
sudo rm -rf /home/Piano-LED-Visualizer.__old__
sudo mv /home/Piano-LED-Visualizer /home/Piano-LED-Visualizer.__old__
sudo mkdir -p /home/Piano-LED-Visualizer
sudo python3 - <<'PY'
import zipfile
src = '/home/plv/plv-deploy.zip'
dst = '/home/Piano-LED-Visualizer'
with zipfile.ZipFile(src) as zf:
    zf.extractall(dst)
    print('extracted', len(zf.infolist()))
PY
sudo cp /home/plv/settings.xml.backup /home/Piano-LED-Visualizer/config/settings.xml
sudo chown -R plv:plv /home/Piano-LED-Visualizer
sudo chmod -R u+rwX,go+rX /home/Piano-LED-Visualizer
python3 -m pip install -r /home/Piano-LED-Visualizer/requirements.txt >/tmp/plv-pip.log 2>&1 || { cat /tmp/plv-pip.log; exit 1; }
sudo systemctl start visualizer
sleep 4
systemctl is-active visualizer
systemctl status visualizer --no-pager -n 25
sudo rm -rf /home/Piano-LED-Visualizer.__old__
"""

        transport = ssh.get_transport()
        channel = transport.open_session(timeout=240)
        channel.exec_command("bash -s")
        channel.sendall(deploy_script.encode("utf-8"))
        channel.shutdown_write()

        stdout_chunks = []
        stderr_chunks = []

        while True:
            if channel.recv_ready():
                stdout_chunks.append(channel.recv(4096))
            if channel.recv_stderr_ready():
                stderr_chunks.append(channel.recv_stderr(4096))
            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                break

        rc = channel.recv_exit_status()
        out = b"".join(stdout_chunks).decode("utf-8", errors="replace")
        err = b"".join(stderr_chunks).decode("utf-8", errors="replace")

        if out:
            print(out, end="")
        if err:
            print(err, end="", file=sys.stderr)
        if rc != 0:
            raise RuntimeError(f"Deploy failed with exit code {rc}")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
