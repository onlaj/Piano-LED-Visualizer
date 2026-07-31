# Wi-Fi setup

Get the Raspberry Pi onto your LAN (or reach it via the Visualizer hotspot) so you can use the web interface or SSH.

Modern Raspberry Pi OS (Bookworm / Trixie) uses **NetworkManager**. Do **not** use a boot-partition `wpa_supplicant.conf` on current images - that method is obsolete (see [Legacy](#legacy-older-pi-os-only) at the bottom).

Default credentials used throughout this project:

| Setting | Value |
| ------- | ----- |
| Hostname | `pianoledvisualizer` |
| SSH user | `plv` |
| Password | `visualizer` |
| Hotspot SSID | `PianoLEDVisualizer` |
| Hotspot password | `visualizer` |

---

## Method A - Raspberry Pi Imager (recommended for fresh OS installs)

Use this when flashing stock Raspberry Pi OS Lite before autoinstall or manual install.

1. Open [Raspberry Pi Imager](https://www.raspberrypi.com/software/), choose your Pi model and **Raspberry Pi OS Lite**.
2. Open **OS customisation** and set:
   - Hostname: `pianoledvisualizer`
   - Enable SSH (password authentication)
   - Username: `plv`
   - Password: `visualizer`
   - Configure Wi-Fi (SSID, password, and country)
3. Write the image, insert the SD card, and boot the Pi.
4. From another device on the same network:

```bash
ssh plv@pianoledvisualizer.local
```

If mDNS fails, use the Pi’s IP address instead (see [Finding the Pi](#finding-the-pi--ssh)).

---

## Method B - Hotspot + web Network tab (project image / running Visualizer)

Use this when Visualizer is already installed (prebuilt image, or after first boot with hotspot enabled).

1. On your phone or computer, join the Wi-Fi network **PianoLEDVisualizer** (password: `visualizer`).
2. Open a browser to `http://pianoledvisualizer.local`.  
   If that does not resolve, try the hotspot gateway IP (often `http://10.42.0.1` on NetworkManager).
3. Open the **Network** tab and connect to your home Wi-Fi.
4. After a successful connect, the hotspot shuts down and the Pi joins your LAN. Reconnect your phone/computer to the home network, then open `http://pianoledvisualizer.local` again (or the new LAN IP).

---

## Method C - Manual `nmcli` over SSH

Use this when you already have SSH (Imager Wi-Fi, Ethernet, or recovery) and need to join or change a Wi-Fi network from the command line.

On Trixie, prefer an **explicit connection profile**. Do **not** rely on `nmcli device wifi connect … password …` (it can fail with `key-mgmt: property is missing`).

Replace `MyWifi`, `YourSSID`, and `YourPassword` with your values. If a profile with that name already exists, delete it first (`sudo nmcli connection delete MyWifi`) or pick a different `con-name`.

### Switching from the Visualizer hotspot

If you are SSH’d over the **PianoLEDVisualizer** hotspot, bringing the hotspot down drops your session. Create the profile first (still connected), then run the switch in the background so it finishes after SSH disconnects:

```bash
sudo nmcli connection add type wifi ifname wlan0 con-name MyWifi ssid "YourSSID" \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "YourPassword"

nohup bash -c 'sudo nmcli connection down Hotspot; sudo nmcli connection up MyWifi' \
  >/tmp/wifi-switch.log 2>&1 &
```

Your SSH session will drop when the hotspot goes down - that is expected. Rejoin your home Wi-Fi, wait a few seconds, then reconnect with `ssh plv@pianoledvisualizer.local`. Check `/tmp/wifi-switch.log` if it did not come online.

### Already on Ethernet or LAN Wi-Fi

If SSH is not going through the hotspot, a normal sequence is fine:

```bash
sudo nmcli connection add type wifi ifname wlan0 con-name MyWifi ssid "YourSSID" \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "YourPassword"
sudo nmcli connection down Hotspot   # skip if Hotspot is not active
sudo nmcli connection up MyWifi
```

For hotspot PMF / `802.1X` failures and related NetworkManager issues on Trixie, see [Troubleshooting in the Trixie manual](manual_installation.md#troubleshooting).

---

## Finding the Pi / SSH

Ways to find the address:

- **LCD:** enable Local IP under *Other Settings → Screensaver → Content*, then open *Other Settings → System Info*.
- **mDNS:** `ping pianoledvisualizer.local` or open `http://pianoledvisualizer.local` in a browser.
- **Network scan:** e.g. `nmap 192.168.0.1/24 -p 80` (adjust the subnet for your LAN), or an app like [Fing](https://play.google.com/store/apps/details?id=com.overlook.android.fing).

SSH (Imager-customised installs and the project image share these defaults):

```bash
ssh plv@pianoledvisualizer.local
```

Password: `visualizer`. You can also use `ssh plv@<ip-address>`.

---

## Legacy (older Pi OS only)

On very old Raspberry Pi OS images, some guides used a `wpa_supplicant.conf` file plus an empty `ssh` file on the boot partition. That approach is **not supported** on current Bookworm/Trixie NetworkManager images. Use Method A, B, or C above instead.
