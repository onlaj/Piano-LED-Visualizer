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

        subprocess.run("sudo chmod a+rwxX -R /home/Piano-LED-Visualizer/", shell=True, check=True)

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
    def copy_connectall_script():
        # make sure connectall.py file exists and is updated
        if not os.path.exists('/usr/local/bin/connectall.py') or \
                filecmp.cmp('/usr/local/bin/connectall.py', 'lib/connectall.py') is not True:
            logger.info("connectall.py script is outdated, updating...")
            copyfile('lib/connectall.py', '/usr/local/bin/connectall.py')
            os.chmod('/usr/local/bin/connectall.py', 493)

    def install_midi2abc(self):
        if not self.is_package_installed("abcmidi"):
            logger.info("Installing abcmidi")
            subprocess.call(['sudo', 'apt-get', 'install', 'abcmidi', '-y'])

    @staticmethod
    def update_visualizer():
        call("sudo git reset --hard HEAD", shell=True)
        call("sudo git checkout .", shell=True)
        call("sudo git clean -fdx -e Songs/ -e "
             "config/settings.xml -e config/wpa_disable_ap.conf -e visualizer.log", shell=True)
        call("sudo git clean -fdx Songs/cache", shell=True)
        call("sudo git pull origin master", shell=True)
        call("sudo pip install -r requirements.txt", shell=True)

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

        if 'Hotspot' in check_profile.stdout:
            logger.info("Hotspot profile already exists. Skipping creation.")
            return

        # If we reach here, the profile doesn't exist, so we create it
        logger.info("Creating new Hotspot profile...")

        try:
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
                'wifi-sec.psk', 'visualizer'
            ], check=True)

            logger.info("Hotspot profile created successfully.")
        except subprocess.CalledProcessError as e:
            logger.warning(f"An error occurred while creating the Hotspot profile: {e}")

    @staticmethod
    def enable_hotspot():
        logger.info("Enabling Hotspot")
        subprocess.run(['sudo', 'nmcli', 'connection', 'up', 'Hotspot'])

    @staticmethod
    def disable_hotspot():
        logger.info("Disabling Hotspot")
        subprocess.run(['sudo', 'nmcli', 'connection', 'down', 'Hotspot'])

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

    def manage_hotspot(self, hotspot, usersettings, midiports, first_run=False):
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
        # Disable the hotspot first
        self.disable_hotspot()

        try:
            result = subprocess.run(
                ['sudo', 'nmcli', 'device', 'wifi', 'connect', ssid, 'password', password],
                capture_output=True,
                text=True,
                timeout=30  # Set a timeout for the connection attempt
            )
            # Check if the connection was successful
            if result.returncode == 0:
                logger.info(f"Successfully connected to {ssid}")
                usersettings.change_setting_value("is_hotspot_active", 0)
                return True
            else:
                logger.warning(f"Failed to connect to {ssid}. Error: {result.stderr}")
                usersettings.change_setting_value("is_hotspot_active", 1)
                self.enable_hotspot()

        except subprocess.TimeoutExpired:
            logger.warning(f"Connection attempt to {ssid} timed out")
            usersettings.change_setting_value("is_hotspot_active", 1)
            self.enable_hotspot()
        except Exception as e:
            logger.warning(f"An error occurred while connecting to {ssid}: {str(e)}")
            usersettings.change_setting_value("is_hotspot_active", 1)
            self.enable_hotspot()

    def disconnect_from_wifi(self, hotspot, usersettings):
        logger.info("Disconnecting from wifi")
        hotspot.hotspot_script_time = time.time()
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
