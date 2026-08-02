import time
import subprocess
from subprocess import call
import os
import filecmp
from shutil import copyfile
from lib.log_setup import logger
import re
import socket
from collections import defaultdict


class Hotspot:
    def __init__(self, hotspot):
        self.hotspot_script_time = 0
        self.time_without_wifi = 0
        self.last_wifi_check_time = 0

        # Move chmod to background thread to avoid blocking startup
        def chmod_background():
            try:
                subprocess.run("sudo chmod a+rwxX -R /home/Piano-LED-Visualizer/", shell=True, check=True)
            except Exception as e:
                logger.warning(f"Error setting permissions in background: {e}")
        
        import threading
        threading.Thread(target=chmod_background, daemon=True).start()

class PlatformBase:
    def __getattr__(self, name):
        def method(*args, **kwargs):
            return False, f"Method '{name}' is not supported on this platform", ""
        return method


class PlatformNull(PlatformBase):
    def __getattr__(self, name):
        return self.pass_func

    def pass_func(self, *args, **kwargs):
        pass


class PlatformRasp(PlatformBase):
    @staticmethod
    def check_and_enable_spi():
        try:
            # Check if SPI is enabled by looking for spidev in /dev
            if not os.path.exists('/dev/spidev0.0'):
                logger.info("SPI is not enabled. Enabling SPI interface...")
                subprocess.run(['sudo', 'raspi-config', 'nonint', 'do_spi', '0'], check=True)
                logger.info("SPI has been enabled. A reboot may be required for changes to take effect.")
                return False
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to enable SPI: {e}")
            return False
        except Exception as e:
            logger.warning(f"Error checking SPI status: {e}")
            return False

    
    @staticmethod
    def disable_system_midi_scripts():
        """Clean up old connectall.py / udev / midi.service leftovers."""
        try:
            udev_paths = [
                '/etc/udev/rules.d/33-midiusb.rules',
                '/etc/udev/rules.d/33-midiusb.rules.disabled',
            ]
            udev_removed = False
            for udev_path in udev_paths:
                if os.path.exists(udev_path):
                    logger.info(f"Removing legacy udev MIDI rule: {udev_path}")
                    subprocess.call(['sudo', 'rm', '-f', udev_path], check=False)
                    udev_removed = True
            if udev_removed:
                subprocess.call(['sudo', 'udevadm', 'control', '--reload'], check=False)

            service_name = 'midi.service'
            service_unit = '/lib/systemd/system/midi.service'
            try:
                subprocess.call(['sudo', 'systemctl', 'stop', service_name], check=False)
                subprocess.call(['sudo', 'systemctl', 'disable', service_name], check=False)
                if os.path.exists(service_unit):
                    logger.info(f"Removing systemd unit {service_unit}")
                    subprocess.call(['sudo', 'rm', '-f', service_unit], check=False)
                    subprocess.call(['sudo', 'systemctl', 'daemon-reload'], check=False)
                logger.info(f"Legacy systemd service {service_name} cleaned up")
            except Exception:
                logger.info(f"Could not fully clean up systemd service {service_name}")

            connectall_path = '/usr/local/bin/connectall.py'
            if os.path.exists(connectall_path):
                logger.info(f"Removing legacy {connectall_path}")
                subprocess.call(['sudo', 'rm', '-f', connectall_path], check=False)

        except Exception as e:
            logger.warning(f"Error removing legacy system MIDI scripts: {e}")

    def install_midi2abc(self):
        if not self.is_package_installed("abcmidi"):
            logger.info("Installing abcmidi")
            subprocess.call(['sudo', 'apt-get', 'install', 'abcmidi', '-y'])

    @staticmethod
    def _project_root():
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @staticmethod
    def _os_codename():
        """Return VERSION_CODENAME from /etc/os-release, or empty string if unavailable."""
        try:
            with open("/etc/os-release", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VERSION_CODENAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except OSError as e:
            logger.warning(f"Could not read /etc/os-release: {e}")
        return ""

    @staticmethod
    def _uses_venv_install(codename, project_root):
        """
        Prefer venv on Trixie and newer; system pip on Bookworm and older.
        If OS detection fails, use .venv presence as fallback.
        """
        legacy = {"bookworm", "bullseye", "buster", "stretch", "jessie"}
        if codename:
            return codename not in legacy
        venv_python = os.path.join(project_root, ".venv", "bin", "python")
        return os.path.isfile(venv_python)

    @staticmethod
    def _ensure_venv(project_root):
        venv_pip = os.path.join(project_root, ".venv", "bin", "pip")
        if os.path.isfile(venv_pip):
            return True
        logger.info("Creating missing .venv for dependency install")
        result = subprocess.run(
            ["python3", "-m", "venv", os.path.join(project_root, ".venv")],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.error(
                f"Failed to create .venv (exit {result.returncode}): "
                f"{result.stderr or result.stdout}"
            )
            return False
        return os.path.isfile(venv_pip)

    @staticmethod
    def _install_requirements(project_root, use_venv):
        if use_venv:
            if not PlatformRasp._ensure_venv(project_root):
                return False
            pip_cmd = [
                "sudo",
                os.path.join(project_root, ".venv", "bin", "pip"),
                "install",
                "-r",
                "requirements.txt",
            ]
            toolchain = "venv (.venv/bin/pip)"
        else:
            pip_cmd = [
                "sudo",
                "pip3",
                "install",
                "-r",
                "requirements.txt",
                "--break-system-packages",
            ]
            toolchain = "system pip3 --break-system-packages"

        logger.info(f"Installing requirements via {toolchain}")
        result = subprocess.run(
            pip_cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.error(
                f"Dependency install failed (exit {result.returncode}): "
                f"{result.stderr or result.stdout}"
            )
            return False
        logger.info("Dependency install completed successfully")
        return True

    @staticmethod
    def update_visualizer():
        project_root = PlatformRasp._project_root()
        try:
            os.chdir(project_root)
        except OSError as e:
            logger.error(f"Could not chdir to project root {project_root}: {e}")
            return

        codename = PlatformRasp._os_codename()
        use_venv = PlatformRasp._uses_venv_install(codename, project_root)
        logger.info(
            f"Updating visualizer in {project_root} "
            f"(OS codename={codename or 'unknown'}, "
            f"deps={'venv' if use_venv else 'system pip'})"
        )

        call("sudo git reset --hard HEAD", shell=True)
        call("sudo git checkout .", shell=True)
        call(
            "sudo git clean -fdx -e Songs/ -e "
            "config/settings.xml -e config/wpa_disable_ap.conf -e visualizer.log "
            "-e .venv -e .venv/",
            shell=True,
        )
        call("sudo git clean -fdx Songs/cache", shell=True)
        call("sudo git pull origin master", shell=True)
        PlatformRasp._install_requirements(project_root, use_venv)

    @staticmethod
    def shutdown():
        call("sudo /sbin/shutdown -h now", shell=True)

    @staticmethod
    def reboot():
        call("sudo /sbin/reboot now", shell=True)

    @staticmethod
    def restart_visualizer():
        call("sudo systemctl restart visualizer", shell=True)

    @staticmethod
    def restart_rtpmidid():
        call("sudo systemctl restart rtpmidid", shell=True)

    @staticmethod
    def is_package_installed(package_name):
        try:
            # Run the 'dpkg' command to check if the package is installed
            result = subprocess.run(['dpkg', '-s', package_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    check=True, text=True)
            output = result.stdout
            status_line = [line for line in output.split('\n') if line.startswith('Status:')][0]

            if "install ok installed" in status_line:
                logger.info(f"{package_name} package is installed")
                return True
            else:
                logger.info(f"{package_name} package is not installed")
                return False
        except subprocess.CalledProcessError:
            logger.warning(f"Error checking {package_name} package status")
            return False

    @staticmethod
    def create_hotspot_profile():
        # Check if the 'Hotspot' profile already exists
        check_profile = subprocess.run(['sudo', 'nmcli', 'connection', 'show', 'Hotspot'],
                                       capture_output=True, text=True)

        profile_exists = check_profile.returncode == 0 and 'Hotspot' in check_profile.stdout

        # Default password if not provided
        password = "visualizer"

        try:
            if not profile_exists:
                # If we reach here, the profile doesn't exist, so we create it
                logger.info("Creating new Hotspot profile...")
                subprocess.run([
                    'sudo', 'nmcli', 'connection', 'add', 'type', 'wifi', 'ifname', 'wlan0',
                    'con-name', 'Hotspot', 'autoconnect', 'no', 'ssid', 'PianoLEDVisualizer'
                ], check=True)

                subprocess.run([
                    'sudo', 'nmcli', 'connection', 'modify', 'Hotspot',
                    '802-11-wireless.mode', 'ap', '802-11-wireless.band', 'bg',
                    'ipv4.method', 'shared'
                ], check=True)

                subprocess.run([
                    'sudo', 'nmcli', 'connection', 'modify', 'Hotspot',
                    'wifi-sec.key-mgmt', 'wpa-psk'
                ], check=True)

                subprocess.run([
                    'sudo', 'nmcli', 'connection', 'modify', 'Hotspot',
                    'wifi-sec.psk', password
                ], check=True)

                logger.info(f"Hotspot profile created successfully with password: {password}")
            else:
                logger.info("Hotspot profile already exists.")

            # Trixie/newer NM: WPA AP fails with "802.1X supplicant took too long"
            # unless Protected Management Frames (802.11w) are disabled (pmf=1).
            subprocess.run([
                'sudo', 'nmcli', 'connection', 'modify', 'Hotspot',
                '802-11-wireless-security.pmf', '1'
            ], check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"An error occurred while creating the Hotspot profile: {e}")

    @staticmethod
    def change_hotspot_password(new_password):
        logger.info(f"Changing Hotspot password to: {new_password}")
        try:
            # Modify the Hotspot connection with the new password
            subprocess.run([
                'sudo', 'nmcli', 'connection', 'modify', 'Hotspot',
                'wifi-sec.psk', new_password
            ], check=True)

            logger.info("Hotspot password changed successfully.")

            # Restart the hotspot to apply changes
            # First, bring the connection down
            subprocess.run(['sudo', 'nmcli', 'connection', 'down', 'Hotspot'], check=False) # Allow failure if not up
            time.sleep(2) # Give it a moment
            # Then, bring it up again
            subprocess.run(['sudo', 'nmcli', 'connection', 'up', 'Hotspot'], check=True)
            logger.info("Hotspot restarted to apply new password.")
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"An error occurred while changing the Hotspot password: {e}")
            return False
        except Exception as e:
            logger.warning(f"An unexpected error occurred while changing hotspot password: {e}")
            return False

    @staticmethod
    def enable_hotspot():
        """Bring up the Hotspot AP. Ensures PMF is disabled (required on Trixie)."""
        logger.info("Enabling Hotspot")
        # Ensure PMF is off before activation (safe on Bookworm; required on Trixie)
        subprocess.run([
            'sudo', 'nmcli', 'connection', 'modify', 'Hotspot',
            '802-11-wireless-security.pmf', '1'
        ], check=False, capture_output=True, text=True)
        # Free wlan0 from any client Wi-Fi profile so AP mode can start
        active = subprocess.run(
            ['nmcli', '-t', '-f', 'NAME,DEVICE,TYPE', 'connection', 'show', '--active'],
            capture_output=True, text=True, check=False
        )
        if active.returncode == 0:
            for line in active.stdout.splitlines():
                parts = line.split(':')
                if len(parts) >= 2 and parts[1] == 'wlan0' and parts[0] != 'Hotspot':
                    subprocess.run(
                        ['sudo', 'nmcli', 'connection', 'down', parts[0]],
                        check=False, capture_output=True, text=True
                    )
        time.sleep(2)
        result = subprocess.run(
            ['sudo', 'nmcli', 'connection', 'up', 'Hotspot'],
            capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            logger.warning(f"Failed to enable Hotspot: {err}")
        return result.returncode == 0

    @staticmethod
    def disable_hotspot():
        """Take Hotspot down if it is active."""
        logger.info("Disabling Hotspot")
        result = subprocess.run(
            ['sudo', 'nmcli', 'connection', 'down', 'Hotspot'],
            capture_output=True, text=True, check=False
        )
        # Not active is fine when switching to client Wi-Fi
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            if 'not an active connection' not in err.lower() and 'no active connection' not in err.lower():
                logger.warning(f"Hotspot down: {err}")
        time.sleep(3)

    @staticmethod
    def get_current_connections():
        try:
            with open(os.devnull, 'w') as null_file:
                output = subprocess.check_output(['iwconfig'], text=True, stderr=null_file)

            if "Mode:Master" in output:
                return False, "Running as hotspot", ""

            for line in output.split('\n'):
                if "ESSID:" in line:
                    ssid = line.split("ESSID:")[-1].strip().strip('"')
                    if ssid != "off/any":
                        access_point_line = [line for line in output.split('\n') if "Access Point:" in line]
                        if access_point_line:
                            access_point = access_point_line[0].split("Access Point:")[1].strip()
                            return True, ssid, access_point
                        return False, "Not connected to any Wi-Fi network.", ""
                    return False, "Not connected to any Wi-Fi network.", ""

            return False, "No Wi-Fi interface found.", ""
        except subprocess.CalledProcessError:
            return False, "Error occurred while getting Wi-Fi information.", ""

    def is_hotspot_running(self):
        try:
            result = subprocess.run(
                ['nmcli', 'connection', 'show', '--active'],
                capture_output=True,
                text=True
            )
            return 'Hotspot' in result.stdout
        except Exception as e:
            logger.warning(f"Error checking hotspot status: {str(e)}")
            return False

    def manage_hotspot(self, hotspot, usersettings, midiports, first_run=False, current_time=None):
        if first_run:
            self.create_hotspot_profile()
            if int(usersettings.get("is_hotspot_active")):
                if not self.is_hotspot_running():
                    logger.info("Hotspot is enabled in settings but not running. Starting hotspot...")
                    self.enable_hotspot()
                    time.sleep(5)

                    if self.is_hotspot_running():
                        logger.info("Hotspot started successfully")
                    else:
                        logger.warning("Failed to start hotspot")
                else:
                    logger.info("Hotspot is already running")

        if current_time is None:
            current_time = time.time()
        if not hotspot.last_wifi_check_time:
            hotspot.last_wifi_check_time = current_time

        if (current_time - hotspot.hotspot_script_time) > 60 and (current_time - midiports.last_activity) > 60:
            hotspot.hotspot_script_time = current_time
            if int(usersettings.get("is_hotspot_active")):
                return

            wifi_success, wifi_ssid, _ = self.get_current_connections()

            if not wifi_success:
                hotspot.time_without_wifi += (current_time - hotspot.last_wifi_check_time)
                if hotspot.time_without_wifi > 240:
                    logger.info("No wifi connection. Enabling hotspot")
                    usersettings.change_setting_value("is_hotspot_active", 1)
                    self.enable_hotspot()
            else:
                hotspot.time_without_wifi = 0

        hotspot.last_wifi_check_time = current_time

    def connect_to_wifi(self, ssid, password, hotspot, usersettings):
        # Disable the hotspot first (includes settle delay)
        self.disable_hotspot()

        # Sanitize a stable connection profile name (nmcli dislikes some chars in con-name)
        con_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in ssid)[:180] or "wifi"
        password = password or ""

        try:
            # Trixie NetworkManager: `nmcli device wifi connect ... password ...`
            # fails with "802-11-wireless-security.key-mgmt: property is missing".
            # Create/update an explicit connection profile instead (works on Bookworm too).
            existing = subprocess.run(
                ['nmcli', '-t', '-f', 'NAME', 'connection', 'show'],
                capture_output=True, text=True, check=False
            )
            names = set(existing.stdout.splitlines()) if existing.returncode == 0 else set()

            if con_name in names:
                if password:
                    subprocess.run([
                        'sudo', 'nmcli', 'connection', 'modify', con_name,
                        'connection.interface-name', 'wlan0',
                        'connection.autoconnect', 'yes',
                        '802-11-wireless.ssid', ssid,
                        'wifi-sec.key-mgmt', 'wpa-psk',
                        'wifi-sec.psk', password,
                    ], check=True, capture_output=True, text=True)
                else:
                    subprocess.run([
                        'sudo', 'nmcli', 'connection', 'modify', con_name,
                        'connection.interface-name', 'wlan0',
                        'connection.autoconnect', 'yes',
                        '802-11-wireless.ssid', ssid,
                    ], check=True, capture_output=True, text=True)
            else:
                add_cmd = [
                    'sudo', 'nmcli', 'connection', 'add',
                    'type', 'wifi',
                    'ifname', 'wlan0',
                    'con-name', con_name,
                    'ssid', ssid,
                    'connection.autoconnect', 'yes',
                ]
                if password:
                    add_cmd.extend([
                        'wifi-sec.key-mgmt', 'wpa-psk',
                        'wifi-sec.psk', password,
                    ])
                subprocess.run(add_cmd, check=True, capture_output=True, text=True)

            result = subprocess.run(
                ['sudo', 'nmcli', 'connection', 'up', con_name],
                capture_output=True,
                text=True,
                timeout=45
            )
            if result.returncode == 0:
                logger.info(f"Successfully connected to {ssid}")
                usersettings.change_setting_value("is_hotspot_active", 0)
                return True

            err = (result.stderr or result.stdout or "").strip()
            logger.warning(f"Failed to connect to {ssid}. Error: {err}")
            usersettings.change_setting_value("is_hotspot_active", 1)
            self.enable_hotspot()

        except subprocess.TimeoutExpired:
            logger.warning(f"Connection attempt to {ssid} timed out")
            usersettings.change_setting_value("is_hotspot_active", 1)
            self.enable_hotspot()
        except subprocess.CalledProcessError as e:
            err = (getattr(e, 'stderr', None) or getattr(e, 'stdout', None) or str(e))
            if isinstance(err, bytes):
                err = err.decode(errors='replace')
            logger.warning(f"Failed to connect to {ssid}. Error: {str(err).strip()}")
            usersettings.change_setting_value("is_hotspot_active", 1)
            self.enable_hotspot()
        except Exception as e:
            logger.warning(f"An error occurred while connecting to {ssid}: {str(e)}")
            usersettings.change_setting_value("is_hotspot_active", 1)
            self.enable_hotspot()

    def disconnect_from_wifi(self, hotspot, usersettings):
        logger.info("Disconnecting from wifi")
        hotspot.hotspot_script_time = time.time()
        # Bring down active client Wi-Fi on wlan0, then start Hotspot
        active = subprocess.run(
            ['nmcli', '-t', '-f', 'NAME,DEVICE', 'connection', 'show', '--active'],
            capture_output=True, text=True, check=False
        )
        if active.returncode == 0:
            for line in active.stdout.splitlines():
                parts = line.split(':')
                if len(parts) >= 2 and parts[1] == 'wlan0' and parts[0] != 'Hotspot':
                    subprocess.run(
                        ['sudo', 'nmcli', 'connection', 'down', parts[0]],
                        check=False, capture_output=True, text=True
                    )
        self.enable_hotspot()
        usersettings.change_setting_value("is_hotspot_active", 1)

    @staticmethod
    def get_wifi_networks():
        try:
            output = subprocess.check_output(['sudo', 'iwlist', 'wlan0', 'scan'], stderr=subprocess.STDOUT)
            networks = output.decode().split('Cell ')

            def calculate_signal_strength(level):
                # Map the signal level to a percentage (0% to 100%) linearly.
                # -50 dBm or higher -> 100%
                # -90 dBm or lower -> 0%
                if level >= -50:
                    return 100
                elif level <= -90:
                    return 0
                else:
                    return 100 - (100 / 40) * (level + 90)

            wifi_dict = defaultdict(lambda: {'Signal Strength': -float('inf'), 'Signal dBm': -float('inf')})

            for network in networks[1:]:
                wifi_data = {}

                address_line = [line for line in network.split('\n') if 'Address:' in line]
                if address_line:
                    wifi_data['Address'] = address_line[0].split('Address:')[1].strip()

                ssid_line = [line for line in network.split('\n') if 'ESSID:' in line]
                if ssid_line:
                    ssid = ssid_line[0].split('ESSID:')[1].strip('"')
                    wifi_data['ESSID'] = ssid

                freq_line = [line for line in network.split('\n') if 'Frequency:' in line]
                if freq_line:
                    wifi_data['Frequency'] = freq_line[0].split('Frequency:')[1].split(' (')[0]

                signal_line = [line for line in network.split('\n') if 'Signal level=' in line]
                if signal_line:
                    signal_dbm = int(signal_line[0].split('Signal level=')[1].split(' dBm')[0])
                    signal_strength = calculate_signal_strength(signal_dbm)
                    wifi_data['Signal Strength'] = signal_strength
                    wifi_data['Signal dBm'] = signal_dbm

                # Update the network info if this is the strongest signal for this SSID
                if wifi_data['Signal Strength'] > wifi_dict[ssid]['Signal Strength']:
                    wifi_dict[ssid].update(wifi_data)

            # Convert the dictionary to a list
            wifi_list = list(wifi_dict.values())

            # Sort descending by "Signal Strength"
            wifi_list.sort(key=lambda x: x['Signal Strength'], reverse=True)

            return wifi_list
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error while scanning Wi-Fi networks: {e.output}")
            return []

    @staticmethod
    def get_local_address():
        try:
            # Get the hostname
            hostname = socket.gethostname()

            # Get the IP address
            ip_address = socket.gethostbyname(hostname + ".local")

            # Construct the full local address
            local_address = f"{hostname}.local"

            return {
                "success": True,
                "local_address": local_address,
                "ip_address": ip_address
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def change_local_address(new_name):
        new_name = new_name.rstrip('.local')
        logger.info("Changing local address to " + new_name)
        # Validate the new name
        if not re.match(r'^[a-zA-Z0-9-]+$', new_name):
            raise ValueError("Invalid name. Use only letters, numbers, and hyphens.")

        try:
            # Change the hostname
            subprocess.run(['sudo', 'hostnamectl', 'set-hostname', new_name], check=True)

            # Update /etc/hosts file
            with open('/etc/hosts', 'r') as file:
                hosts_content = file.readlines()

            with open('/etc/hosts', 'w') as file:
                for line in hosts_content:
                    if "127.0.1.1" in line:
                        file.write(f"127.0.1.1\t{new_name}\n")
                    else:
                        file.write(line)

            # Restart avahi-daemon to apply changes
            subprocess.run(['sudo', 'systemctl', 'restart', 'avahi-daemon'], check=True)

            # Optionally, restart the networking service
            subprocess.run(['sudo', 'systemctl', 'restart', 'networking'], check=True)

            logger.info(f"Local address successfully changed to {new_name}.local")
            return True

        except subprocess.CalledProcessError as e:
            logger.warning(f"An error occurred while changing the local address: {e}")
            return False
        except IOError as e:
            logger.warning(f"An error occurred while updating the hosts file: {e}")
            return False
        except Exception as e:
            logger.warning(f"An unexpected error occurred: {e}")
            return False

    @staticmethod
    def get_current_timezone():
        """Get the current system timezone."""
        try:
            # Try using timedatectl first (preferred method)
            result = subprocess.run(
                ['timedatectl', 'show', '-p', 'Timezone', '--value'],
                capture_output=True,
                text=True,
                check=True
            )
            timezone = result.stdout.strip()
            if timezone:
                return timezone
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        try:
            # Fallback to reading /etc/timezone
            if os.path.exists('/etc/timezone'):
                with open('/etc/timezone', 'r') as f:
                    timezone = f.read().strip()
                    if timezone:
                        return timezone
        except Exception as e:
            logger.warning(f"Error reading timezone from /etc/timezone: {e}")
        
        # Default fallback
        logger.warning("Could not determine timezone, returning UTC")
        return "UTC"

    @staticmethod
    def get_available_timezones():
        """Get list of available timezones."""
        try:
            result = subprocess.run(
                ['timedatectl', 'list-timezones'],
                capture_output=True,
                text=True,
                check=True
            )
            timezones = [tz.strip() for tz in result.stdout.split('\n') if tz.strip()]
            return timezones
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"Error getting timezone list: {e}")
            # Return common timezones as fallback
            return [
                "UTC",
                "America/New_York",
                "America/Chicago",
                "America/Denver",
                "America/Los_Angeles",
                "Europe/London",
                "Europe/Paris",
                "Europe/Berlin",
                "Asia/Tokyo",
                "Asia/Shanghai",
                "Australia/Sydney"
            ]

    @staticmethod
    def set_timezone(timezone):
        """Set the system timezone."""
        try:
            logger.info(f"Setting timezone to {timezone}")
            subprocess.run(
                ['sudo', 'timedatectl', 'set-timezone', timezone],
                check=True
            )
            logger.info(f"Timezone successfully changed to {timezone}")
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error setting timezone: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error setting timezone: {e}")
            return False
