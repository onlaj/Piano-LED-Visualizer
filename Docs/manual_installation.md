# Manual installation (Raspberry Pi OS Trixie)

Guide for a **fresh install** of Piano LED Visualizer on **Raspberry Pi OS Lite (Trixie / Debian 13)**.

Validated on Trixie with **rtpmidid v26.01** built from source (`USE_FMT=ON`).

> For the older Bookworm-era notes, see [manual_installation_bookworm.md](manual_installation_bookworm.md).  
> Prefer a one-shot install? Use [`autoinstall.sh`](../autoinstall.sh) after flashing (Trixie).  
> On Bookworm, use [`autoinstall_bookworm.sh`](../autoinstall_bookworm.sh) instead.

---

## 0. Flash the OS

1. Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Choose **Raspberry Pi OS Lite**:
  - **Pi Zero / Zero W:** Lite **32-bit** (Trixie)
  - **Pi Zero 2 W (or newer):** Lite **64-bit** (Trixie) is fine
3. Open **OS customisation**:
  - Hostname: `pianoledvisualizer`
  - Enable SSH
  - Username: `plv`
  - Password: `visualizer`
  - Configure Wi-Fi (recommended)
4. Write the image to the SD card, boot the Pi, then connect:

```bash
ssh plv@pianoledvisualizer.local
```

On new Trixie images, passwordless `sudo` is off by default. Enable it for easier setup:

```bash
echo 'plv ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/010_plv-nopasswd
sudo chmod 440 /etc/sudoers.d/010_plv-nopasswd
```

Optional locale fix (clears `perl: warning: Setting locale failed`). Prefer the noninteractive path:

```bash
sudo sed -i 's/^# *en_GB.UTF-8 UTF-8/en_GB.UTF-8 UTF-8/' /etc/locale.gen
sudo locale-gen en_GB.UTF-8
sudo update-locale LANG=en_GB.UTF-8 LC_ALL=en_GB.UTF-8
unset LC_CTYPE
export LANG=en_GB.UTF-8 LC_ALL=en_GB.UTF-8
```

Use `en_US.UTF-8` instead if you prefer. Then log out of SSH and reconnect.


---



## 1. Update the OS

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

---



## 2. Enable SPI

```bash
sudo raspi-config nonint do_spi 0
```

---



## 3. Install system packages

```bash
sudo apt-get install -y \
  ruby git python3-pip python3-venv \
  autotools-dev libtool autoconf \
  libasound2t64 libavahi-client3 libavahi-common3 \
  libc6 libgcc-s1 libstdc++6 python3 \
  libopenblas-dev libavahi-client-dev libasound2-dev \
  libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev \
  libical-dev libreadline-dev \
  libopenjp2-7 libtiff6 libjack0 libjack-dev \
  fonts-freefont-ttf libfreetype6 gcc make build-essential scons swig abcmidi \
  cmake pkg-config ninja-build libfmt-dev
```

Notes for Trixie:

- Use `libasound2t64` (not `libasound2`)
- Do **not** install `libatlas-base-dev` (removed in Debian 13)
- Do **not** install Bookworm `libfmt9` debs

---



## 4. Disable onboard audio

WS281x LEDs need PWM; onboard audio conflicts with that.

```bash
echo 'blacklist snd_bcm2835' | sudo tee /etc/modprobe.d/snd-blacklist.conf
sudo sed -i 's/dtparam=audio=on/#dtparam=audio=on/' /boot/firmware/config.txt
sudo reboot
```

Reconnect over SSH after reboot.

---



## 5. Install RTP MIDI (optional)


Check architecture:

```bash
dpkg --print-architecture
```

This reports the **OS image** architecture (not the board alone):

| Result | Meaning | Typical devices |
|--------|---------|-----------------|
| `armhf` | 32-bit | Pi Zero / Zero W (always). Also any board flashed with a 32-bit image |
| `arm64` | 64-bit | Pi Zero 2 W, Pi 3 / 4 / 5 (and similar) when running a **64-bit** image |

Follow **5a** for `arm64`, **5b** for `armhf`.

### 5a. `arm64` - official Trixie package

```bash
cd /home
sudo wget https://github.com/davidmoreno/rtpmidid/releases/download/v26.01/rtpmidid-debian-trixie-arm64-26.01.deb
sudo apt-get install -y libasound2t64 libavahi-client3 libavahi-common3
sudo dpkg -i rtpmidid-debian-trixie-arm64-26.01.deb
sudo apt -f install -y
sudo systemctl enable --now rtpmidid
systemctl status rtpmidid --no-pager
```



### 5b. `armhf` (Pi Zero / Zero W) - build from source

There is **no** official Trixie armhf deb. Build v26.01 with **libfmt** (required on GCC 14; default `std::format` fails to compile):

```bash
cd /home
sudo rm -rf rtpmidid-src
sudo git clone --depth 1 --branch v26.01 https://github.com/davidmoreno/rtpmidid.git rtpmidid-src
cd rtpmidid-src

sudo cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_TESTS=OFF \
  -DENABLE_PCH=OFF \
  -DUSE_FMT=ON \
  -DCPP_VERSION=17 \
  -GNinja

sudo cmake --build build
```

Confirm cmake printed `Using fmt library`, then install:

```bash
sudo install -m 755 build/src/rtpmidid /usr/bin/rtpmidid
sudo mkdir -p /etc/rtpmidid
sudo cp default.ini /etc/rtpmidid/default.ini
sudo cp debian/rtpmidid.service /lib/systemd/system/rtpmidid.service
sudo useradd -r -s /usr/sbin/nologin -G audio rtpmidid 2>/dev/null || true
sudo systemctl daemon-reload
sudo systemctl enable --now rtpmidid
systemctl status rtpmidid --no-pager
```

Expected: `Active: active (running)`.

On a Pi Zero the compile can take a long time - do not interrupt it.

---



## 6. Install Piano LED Visualizer

```bash
cd /home
sudo git clone https://github.com/onlaj/Piano-LED-Visualizer
sudo chown -R "$USER:$USER" /home/Piano-LED-Visualizer
cd /home/Piano-LED-Visualizer

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Enable console autologin:

```bash
sudo raspi-config nonint do_boot_behaviour B2
```

Install the systemd unit from the repo. The service runs as **root** with the project venv (needed for LEDs, GPIO, and NetworkManager). SSH login remains `plv`.

```bash
sudo cp /home/Piano-LED-Visualizer/systemd/visualizer.service /lib/systemd/system/visualizer.service
```

Optional flags on `ExecStart` (edit the installed unit, then `sudo systemctl daemon-reload`):

- WaveShare 1.3" 240×240: add `--display 1in3`
- Upside-down mount: add `--rotatescreen true`

Enable and reboot:

```bash
sudo systemctl daemon-reload
sudo systemctl enable visualizer.service
sudo chmod a+rwxX -R /home/Piano-LED-Visualizer/
sudo reboot
```

After 1–3 minutes you should see the Visualizer menu on the LCD.  
Web UI: `http://pianoledvisualizer.local` (same network), or the hotspot setup from the project image docs if you enable that later.

---



## Troubleshooting



### Hotspot: `802.1X supplicant took too long to authenticate`

Known Raspberry Pi OS **Trixie** issue with NetworkManager WPA access points. Disable Protected Management Frames (802.11w) on the Hotspot profile:

```bash
sudo nmcli connection modify Hotspot 802-11-wireless-security.pmf 1
sudo nmcli connection up Hotspot
```

Current app code applies this automatically when creating/updating the profile. If an old broken profile already exists, run the commands above once (or delete and let the app recreate it: `sudo nmcli connection delete Hotspot`).

### Wi-Fi reconnect: `key-mgmt: property is missing`

On Trixie, `nmcli device wifi connect … password …` is broken. The app now creates an explicit connection profile with `wifi-sec.key-mgmt wpa-psk`.

Manual test:

```bash
sudo nmcli connection down Hotspot
sudo nmcli connection add type wifi ifname wlan0 con-name MyWifi ssid "YourSSID" \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "YourPassword"
sudo nmcli connection up MyWifi
```

### Legacy USB MIDI autoconnect (`midi.service` / `connectall.py`)

Older installs created a mesh `aconnect` script (`/usr/local/bin/connectall.py`), udev rule `33-midiusb.rules`, and `midi.service`. That is no longer used: Learning mode links piano ↔ computer inside the Visualizer.

Starting the Visualizer once (without `--skipupdate`) removes those leftovers automatically. To clean up manually:

```bash
sudo systemctl disable --now midi.service 2>/dev/null || true
sudo rm -f /lib/systemd/system/midi.service
sudo systemctl daemon-reload
sudo rm -f /etc/udev/rules.d/33-midiusb.rules /etc/udev/rules.d/33-midiusb.rules.disabled
sudo udevadm control --reload
sudo rm -f /usr/local/bin/connectall.py
```

### Old service unit (`User=plv` / `sudo python3`)

Bookworm-era units used `User=plv` and `ExecStart=sudo python3 …`. On Trixie, replace the unit with the repo file and ensure the venv exists:

```bash
cd /home/Piano-LED-Visualizer
test -x .venv/bin/python || python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
sudo systemctl stop visualizer.service
sudo cp systemd/visualizer.service /lib/systemd/system/visualizer.service
sudo systemctl daemon-reload
sudo systemctl enable visualizer.service
sudo reboot
```

Confirm after reboot: `systemctl cat visualizer` shows `.venv/bin/python` and `User=root` (no nested `sudo` in `ExecStart`).

---



## Quick checklist


| Step       | Command / check                                                 |
| ---------- | --------------------------------------------------------------- |
| OS         | Trixie Lite (`cat /etc/os-release` → `VERSION_CODENAME=trixie`) |
| Arch       | `armhf` for classic Zero; `arm64` for Zero 2 W 64-bit           |
| SPI        | enabled                                                         |
| Audio      | `dtparam=audio` commented in `/boot/firmware/config.txt`        |
| rtpmidid   | `systemctl is-active rtpmidid` → `active` (if installed)        |
| Visualizer | `systemctl is-active visualizer` → `active` after reboot        |
| Hotspot    | `nmcli -f GENERAL.STATE connection show Hotspot` → activated    |


