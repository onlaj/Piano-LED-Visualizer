#!/bin/bash

REPO_URL="https://github.com/GoulagmanYt/Piano-LED-Visualizer.git"
REPO_BRANCH="master"
APP_DIR="/home/Piano-LED-Visualizer"
PLV_USER="plv"
PLV_PASSWORD="visualizer"
PLV_HOSTNAME="pianoledvisualizer"

# Function to display error message and exit
display_error() {
  echo "Error: $1" >&2
  exit 1
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
      exit $exit_code
    fi
  fi
}



# Function to update the OS
update_os() {
  execute_command "sudo apt-get update" "check_internet"
  execute_command "sudo apt-get upgrade -y"
}

configure_pi_identity() {
  local user_groups="sudo"
  for group in audio video input render plugdev dialout netdev spi i2c gpio; do
    if getent group "$group" >/dev/null 2>&1; then
      user_groups="${user_groups},${group}"
    fi
  done

  execute_command "sudo hostnamectl set-hostname ${PLV_HOSTNAME}"
  execute_command "sudo sed -i -E 's/^(127\\.0\\.1\\.1\\s+).*/\\1${PLV_HOSTNAME}/' /etc/hosts"
  if ! getent hosts "${PLV_HOSTNAME}" >/dev/null 2>&1; then
    echo "127.0.1.1 ${PLV_HOSTNAME}" | sudo tee -a /etc/hosts >/dev/null
  fi

  if ! id -u "${PLV_USER}" >/dev/null 2>&1; then
    execute_command "sudo useradd -m -s /bin/bash -G ${user_groups} ${PLV_USER}"
  fi

  echo "${PLV_USER}:${PLV_PASSWORD}" | sudo chpasswd
  execute_command "sudo usermod -aG ${user_groups} ${PLV_USER}"
  echo "${PLV_USER} ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/010_pi-nopasswd >/dev/null
  execute_command "sudo chmod 0440 /etc/sudoers.d/010_pi-nopasswd"

  if systemctl list-unit-files ssh.service --no-legend 2>/dev/null | grep -q '^ssh\.service'; then
    execute_command "sudo systemctl enable ssh.service"
    execute_command "sudo systemctl start ssh.service"
  fi
}

# Function to create and configure the autoconnect script
configure_autoconnect_script() {
  # Create connectall.py file
  cat <<EOF | sudo tee /usr/local/bin/connectall.py > /dev/null
#!/usr/bin/python3
import subprocess

ports = subprocess.check_output(["aconnect", "-i", "-l"], text=True)
port_list = []
client = "0"
for line in str(ports).splitlines():
    if line.startswith("client "):
        client = line[7:].split(":",2)[0]
        if client == "0" or "Through" in line:
            client = "0"
    else:
        if client == "0" or line.startswith('\t'):
            continue
        port = line.split()[0]
        port_list.append(client+":"+port)
for source in port_list:
    for target in port_list:
        if source != target:
            subprocess.call("aconnect %s %s" % (source, target), shell=True)
EOF
  execute_command "sudo chmod +x /usr/local/bin/connectall.py"

  # Create udev rules file
  echo 'ACTION=="add|remove", SUBSYSTEM=="usb", DRIVER=="usb", RUN+="/usr/local/bin/connectall.py"' | sudo tee -a /etc/udev/rules.d/33-midiusb.rules > /dev/null

  # Reload services
  execute_command "sudo udevadm control --reload"
  execute_command "sudo service udev restart"

  # Create midi.service file
  cat <<EOF | sudo tee /lib/systemd/system/midi.service > /dev/null
[Unit]
Description=Initial USB MIDI connect

[Service]
ExecStart=/usr/local/bin/connectall.py

[Install]
WantedBy=multi-user.target
EOF

  # Reload daemon and enable service
  execute_command "sudo systemctl daemon-reload"
  execute_command "sudo systemctl enable midi.service"
  execute_command "sudo systemctl start midi.service"
}

# Function to enable SPI interface
enable_spi_interface() {
  # Edit config.txt file to enable SPI interface
  execute_command "sudo raspi-config nonint do_spi 0"
}

# Function to install required packages
install_packages() {
  execute_command "sudo apt-get install -y ruby git wget iw python3-pip autotools-dev libtool autoconf libasound2 libavahi-client3 libavahi-common3 libc6 libfmt9 libgcc-s1 libstdc++6 python3 libopenblas-dev libavahi-client-dev libasound2-dev libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev libatlas-base-dev libopenjp2-7 libtiff6 libjack0 libjack-dev fonts-freefont-ttf gcc make build-essential scons swig abcmidi" "check_internet"
}

# Function to disable audio output
disable_audio_output() {
  echo 'blacklist snd_bcm2835' | sudo tee -a /etc/modprobe.d/snd-blacklist.conf > /dev/null
  local boot_config="/boot/firmware/config.txt"
  if [ ! -f "$boot_config" ]; then
    boot_config="/boot/config.txt"
  fi
  sudo sed -i 's/^dtparam=audio=on/#dtparam=audio=on/' "$boot_config"
}

# Function to install RTP-midi server
install_rtpmidi_server() {
  execute_command "cd /home/"
  execute_command "sudo wget https://github.com/davidmoreno/rtpmidid/releases/download/v24.12/rtpmidid_24.12.2_armhf.deb" "check_internet"
  execute_command "sudo dpkg -i rtpmidid_24.12.2_armhf.deb"
  execute_command "sudo apt -f install -y"
  execute_command "rm rtpmidid_24.12.2_armhf.deb"
}


# Function to install Piano-LED-Visualizer
install_piano_led_visualizer() {
  if [ -d "${APP_DIR}/.git" ]; then
    execute_command "sudo git -C ${APP_DIR} remote set-url origin ${REPO_URL}"
    execute_command "sudo git -C ${APP_DIR} fetch origin ${REPO_BRANCH}" "check_internet"
    execute_command "sudo git -C ${APP_DIR} checkout ${REPO_BRANCH}"
    execute_command "sudo git -C ${APP_DIR} pull --ff-only origin ${REPO_BRANCH}" "check_internet"
  else
    if [ -e "${APP_DIR}" ]; then
      execute_command "sudo mv ${APP_DIR} ${APP_DIR}.pre-autoinstall-$(date +%Y%m%d-%H%M%S)"
    fi
    execute_command "cd /home/ && sudo git clone --branch ${REPO_BRANCH} ${REPO_URL} ${APP_DIR}" "check_internet"
  fi

  execute_command "sudo git -C ${APP_DIR} config --local pull.ff only"
  execute_command "sudo git -C ${APP_DIR} config --local core.filemode false"
  execute_command "sudo chown -R ${PLV_USER}:${PLV_USER} ${APP_DIR}"
  execute_command "sudo pip3 install -r ${APP_DIR}/requirements.txt --break-system-packages" "check_internet"
  execute_command "sudo raspi-config nonint do_boot_behaviour B2"
  cat <<EOF | sudo tee /lib/systemd/system/visualizer.service > /dev/null
[Unit]
Description=Piano LED Visualizer
After=network-online.target
Wants=network-online.target

[Install]
WantedBy=multi-user.target

[Service]
WorkingDirectory=${APP_DIR}/
ExecStart=/usr/bin/python3 ${APP_DIR}/visualizer.py
Restart=always
Type=simple
User=root
Group=root
EOF
  execute_command "sudo systemctl daemon-reload"
  execute_command "sudo systemctl enable visualizer.service"
  execute_command "sudo bash ${APP_DIR}/scripts/configure_rtpmidi_stability.sh rtpmidid"
  execute_command "sudo env PLV_DIR=${APP_DIR} bash ${APP_DIR}/scripts/configure_pi_low_latency.sh"
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
# Autoinstall script
# - maintained by GoulagmanYt, based on the original Onlaj installer
"

# Main script execution
configure_pi_identity
update_os
configure_autoconnect_script
enable_spi_interface
install_packages
disable_audio_output
install_rtpmidi_server
install_piano_led_visualizer
finish_installation
