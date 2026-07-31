---
name: Bug report
about: Create a report to help us improve
title: ''
labels: bug
assignees: ''

---

**Describe the bug**
Please provide a clear and concise description of the bug you encountered.

**Installation Method**
How did you install Piano LED Visualizer?
- System image (include the [release](https://github.com/onlaj/Piano-LED-Visualizer/releases) version)
- Autoinstall (`autoinstall.sh` for Trixie, or `autoinstall_bookworm.sh` for Bookworm)
- Manual install

**Steps to Reproduce**
Please provide detailed steps to reproduce the behavior you encountered.

**Error Messages**
If possible, SSH into your Raspberry Pi and run the visualizer manually.

Trixie (venv-based) installs:

```bash
sudo /home/Piano-LED-Visualizer/.venv/bin/python /home/Piano-LED-Visualizer/visualizer.py
```

Bookworm or older release-image installs that still use system Python:

```bash
sudo python3 /home/Piano-LED-Visualizer/visualizer.py
```

Copy-paste or screenshot any error messages you see.

**Expected behavior**
A clear and concise description of what you expected to happen.

**Environment**
- Raspberry Pi OS codename: [e.g. `trixie` or `bookworm` from `cat /etc/os-release`]
- Architecture: [e.g. `armhf` or `arm64` from `dpkg --print-architecture`]
- Raspberry Pi model: [e.g. Pi Zero W, Pi Zero 2 W]
- Python version: [e.g. Python 3.13]
- Any other relevant hardware or configuration details

**Additional Context**
Add any other context about the problem here.
