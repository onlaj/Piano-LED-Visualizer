#!/bin/bash
#
# Autoinstall for Piano LED Visualizer on Raspberry Pi OS Trixie (Debian 13).
# For Bookworm, use autoinstall_bookworm.sh instead.
#

# Function to display error message and exit
display_error() {
  echo "Error: $1" >&2
  exit 1
}

require_trixie() {
  if [ ! -f /etc/os-release ]; then
    display_error "Cannot detect OS (/etc/os-release missing). This script requires Raspberry Pi OS Trixie."
  fi
  # shellcheck source=/dev/null
  . /etc/os-release
  if [ "${VERSION_CODENAME:-}" != "trixie" ]; then
    echo "Error: This script requires Raspberry Pi OS Trixie (got: ${VERSION_CODENAME:-unknown})." >&2
    echo "For Bookworm, use autoinstall_bookworm.sh instead:" >&2
    echo "  sudo bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/onlaj/Piano-LED-Visualizer/master/autoinstall_bookworm.sh)\"" >&2
    exit 1
  fi
}

# Function to execute a command and handle errors, with optional internet connectivity check
execute_command() {
  local check_internet="$2"  # Check for internet if this argument is provided

  echo "Executing: $1"

  if [ "$check_internet" = "check_internet" ]; then
    local max_retries=18  # Total number of retries (18 retries * 10 seconds = 3 minutes)
    local retry_interval=10  # Retry interval in seconds

    for ((attempt = 1; attempt <= max_retries; attempt++)); do
      # Check for internet connectivity
      if ping -q -c 1 -W 1 google.com &>/dev/null; then
        # Internet is available, execute the command
        eval "$1"
        local exit_code=$?

        if [ $exit_code -eq 0 ]; then
          return 0  # Command executed successfully
        else
          echo "Command failed with exit code $exit_code."
          sleep $retry_interval  # Wait before retrying
        fi
      else
        echo "Internet not available, retrying in $retry_interval seconds (Attempt $attempt/$max_retries)..."
        sleep $retry_interval  # Wait before retrying
      fi
    done

    echo "Command failed after $((max_retries * retry_interval)) seconds of retries."
    exit 1  # Exit the script after multiple unsuccessful retries
  else
    eval "$1"  # Execute the command without internet connectivity check
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
      echo "Command failed with exit code $exit_code."
      return "$exit_code"
    fi
  fi
}

# Function to update the OS
update_os() {
  execute_command "sudo apt-get update" "check_internet"
  execute_command "sudo apt-get upgrade -y"
}

# Function to enable SPI interface
enable_spi_interface() {
  execute_command "sudo raspi-config nonint do_spi 0"
}

# Function to install required packages (Trixie)
install_packages() {
  execute_command "sudo apt-get install -y \
    ruby git python3-pip python3-venv \
    autotools-dev libtool autoconf \
    libasound2t64 libavahi-client3 libavahi-common3 \
    libc6 libgcc-s1 libstdc++6 python3 \
    libopenblas-dev libavahi-client-dev libasound2-dev \
    libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev \
    libical-dev libreadline-dev \
    libopenjp2-7 libtiff6 libjack0 libjack-dev \
    fonts-freefont-ttf libfreetype6 gcc make build-essential scons swig abcmidi \
    cmake pkg-config ninja-build libfmt-dev" "check_internet"
}

# Function to disable audio output (takes effect after final reboot)
disable_audio_output() {
  echo 'blacklist snd_bcm2835' | sudo tee /etc/modprobe.d/snd-blacklist.conf > /dev/null
  sudo sed -i 's/dtparam=audio=on/#dtparam=audio=on/' /boot/firmware/config.txt
}

# Function to create and configure the autoconnect script
configure_autoconnect_script() {
  cat <<'EOF' | sudo tee /usr/local/bin/connectall.py > /dev/null
#!/usr/bin/python3
import subprocess

ports = subprocess.check_output(["aconnect", "-i", "-l"], text=True)
port_list = []
client = "0"
for line in str(ports).splitlines():
    if line.startswith("client "):
        client = line[7:].split(":", 2)[0]
        if client == "0" or "Through" in line:
            client = "0"
    else:
        if client == "0" or line.startswith("\t"):
            continue
        port = line.split()[0]
        port_list.append(client + ":" + port)
for source in port_list:
    for target in port_list:
        if source != target:
            subprocess.call("aconnect %s %s" % (source, target), shell=True)
EOF
  execute_command "sudo chmod +x /usr/local/bin/connectall.py"

  echo 'ACTION=="add|remove", SUBSYSTEM=="usb", DRIVER=="usb", RUN+="/usr/local/bin/connectall.py"' \
    | sudo tee /etc/udev/rules.d/33-midiusb.rules > /dev/null

  cat <<EOF | sudo tee /lib/systemd/system/midi.service > /dev/null
[Unit]
Description=Initial USB MIDI connect

[Service]
ExecStart=/usr/local/bin/connectall.py

[Install]
WantedBy=multi-user.target
EOF

  execute_command "sudo udevadm control --reload"
  execute_command "sudo systemctl daemon-reload"
  execute_command "sudo systemctl enable --now midi.service"
}

install_rtpmidi_arm64() {
  execute_command "cd /home"
  execute_command "sudo wget https://github.com/davidmoreno/rtpmidid/releases/download/v26.01/rtpmidid-debian-trixie-arm64-26.01.deb" "check_internet"
  execute_command "sudo apt-get install -y libasound2t64 libavahi-client3 libavahi-common3" "check_internet"
  execute_command "sudo dpkg -i rtpmidid-debian-trixie-arm64-26.01.deb"
  execute_command "sudo apt -f install -y"
  execute_command "sudo systemctl enable --now rtpmidid"
  execute_command "rm -f rtpmidid-debian-trixie-arm64-26.01.deb"
}

install_rtpmidi_armhf_from_source() {
  echo "Building rtpmidid from source for armhf. On a Pi Zero this can take a long time — do not interrupt."
  execute_command "cd /home"
  execute_command "sudo rm -rf rtpmidid-src"
  execute_command "sudo git clone --depth 1 --branch v26.01 https://github.com/davidmoreno/rtpmidid.git rtpmidid-src" "check_internet"
  execute_command "cd /home/rtpmidid-src && sudo cmake -S . -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DENABLE_TESTS=OFF \
    -DENABLE_PCH=OFF \
    -DUSE_FMT=ON \
    -DCPP_VERSION=17 \
    -GNinja"
  execute_command "cd /home/rtpmidid-src && sudo cmake --build build"
  execute_command "sudo install -m 755 /home/rtpmidid-src/build/src/rtpmidid /usr/bin/rtpmidid"
  execute_command "sudo mkdir -p /etc/rtpmidid"
  execute_command "sudo cp /home/rtpmidid-src/default.ini /etc/rtpmidid/default.ini"
  execute_command "sudo cp /home/rtpmidid-src/debian/rtpmidid.service /lib/systemd/system/rtpmidid.service"
  execute_command "sudo useradd -r -s /usr/sbin/nologin -G audio rtpmidid 2>/dev/null || true"
  execute_command "sudo systemctl daemon-reload"
  execute_command "sudo systemctl enable --now rtpmidid"
}

# Function to install RTP-midi server (arch-specific)
install_rtpmidi_server() {
  local arch
  arch="$(dpkg --print-architecture)"
  case "$arch" in
    arm64)
      install_rtpmidi_arm64
      ;;
    armhf)
      install_rtpmidi_armhf_from_source
      ;;
    *)
      display_error "Unsupported architecture for rtpmidid install: $arch (expected arm64 or armhf)"
      ;;
  esac
}

# Function to install Piano-LED-Visualizer
install_piano_led_visualizer() {
  execute_command "cd /home"
  execute_command "sudo git clone https://github.com/onlaj/Piano-LED-Visualizer" "check_internet"
  execute_command "sudo chown -R $USER:$USER /home/Piano-LED-Visualizer"
  execute_command "cd /home/Piano-LED-Visualizer && python3 -m venv .venv"
  execute_command "cd /home/Piano-LED-Visualizer && .venv/bin/pip install --upgrade pip" "check_internet"
  execute_command "cd /home/Piano-LED-Visualizer && .venv/bin/pip install -r requirements.txt" "check_internet"
  execute_command "sudo raspi-config nonint do_boot_behaviour B2"
  execute_command "sudo cp /home/Piano-LED-Visualizer/systemd/visualizer.service /lib/systemd/system/visualizer.service"
  execute_command "sudo systemctl daemon-reload"
  execute_command "sudo systemctl enable visualizer.service"
  execute_command "sudo chmod a+rwxX -R /home/Piano-LED-Visualizer/"
}

finish_installation() {
  echo "------------------"
  echo "------------------"
  echo "Installation complete. Raspberry Pi will automatically restart in 60 seconds."
  echo "If the Raspberry Pi does not restart on its own, please wait for 2 minutes and then manually reboot."
  echo "After the reboot, please wait for up to 10 minutes. The Visualizer should start, and the Hotspot 'PianoLEDVisualizer' will become available."

  execute_command "sudo shutdown -r +1"
  sleep 60
  # Reboot Raspberry Pi
  execute_command "sudo reboot"
}

echo "
#    _____  _                        _       ______  _____
#   |  __ \\(_)                      | |     |  ____||  __ \\
#   | |__) |_   __ _  _ __    ___   | |     | |__   | |  | |
#   |  ___/| | / _\` || '_ \\  / _ \\  | |     |  __|  | |  | |
#   | |    | || (_| || | | || (_) | | |____ | |____ | |__| |
#   |_|    |_| \\__,_||_| |_| \\___/  |______||______||_____/
#   __      __ _                     _  _
#   \\ \\    / /(_)                   | |(_)
#    \\ \\  / /  _  ___  _   _   __ _ | | _  ____ ___  _ __
#     \\ \\/ /  | |/ __|| | | | / _\` || || ||_  // _ \\| '__|
#      \\  /   | |\\__ \\| |_| || (_| || || | / /|  __/| |
#       \\/    |_||___/ \\__,_| \\__,_||_||_|/___|\\___||_|
#
# Autoinstall script (Trixie)
# - by Onlaj
"

# Main script execution
require_trixie
update_os
enable_spi_interface
install_packages
disable_audio_output
configure_autoconnect_script
install_rtpmidi_server
install_piano_led_visualizer
finish_installation
