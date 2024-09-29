import time
import subprocess
from subprocess import call
import os
import filecmp
from shutil import copyfile
from lib.log_setup import logger


class Hotspot:
    def __init__(self, platform):
        self.hotspot_script_time = 0
        self.time_without_wifi = 0
        self.last_wifi_check_time = 0
        self.is_hostapd_installed = platform.is_package_installed("hostapd")

        subprocess.run("sudo chmod a+rwxX -R /home/Piano-LED-Visualizer/", shell=True, check=True)

class Platform_null:
    def __getattr__(self, name):
        return self.pass_func

    def pass_func(self, *args, **kwargs):
        pass

    def get_current_connections(self):
        return False, "Platform disabled", ""


class PlatformRasp:
    def copy_connectall_script(self):
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

    def update_visualizer(self):
        call("sudo git reset --hard HEAD", shell=True)
        call("sudo git checkout .", shell=True)
        call("sudo git clean -fdx -e Songs/ -e config/settings.xml -e config/wpa_disable_ap.conf -e visualizer.log", shell=True)
        call("sudo git clean -fdx Songs/cache", shell=True)
        call("sudo git pull origin master", shell=True)
        call("sudo pip install -r requirements.txt", shell=True)

    def shutdown(self):
        call("sudo /sbin/shutdown -h now", shell=True)

    def reboot(self):
        call("sudo /sbin/reboot now", shell=True)

    def restart_visualizer(self):
        call("sudo systemctl restart visualizer", shell=True)

    def restart_rtpmidid(self):
        call("sudo systemctl restart rtpmidid", shell=True)

    def is_package_installed(self, package_name):
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

    def create_hotspot_profile(self):
        # Check if the 'Hotspot' profile already exists
        check_profile = subprocess.run(['sudo', 'nmcli', 'connection', 'show', 'Hotspot'],
                                       capture_output=True, text=True)

        if 'Hotspot' in check_profile.stdout:
            print("Hotspot profile already exists. Skipping creation.")
            return

        # If we reach here, the profile doesn't exist, so we create it
        print("Creating new Hotspot profile...")

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

            print("Hotspot profile created successfully.")
        except subprocess.CalledProcessError as e:
            print(f"An error occurred while creating the Hotspot profile: {e}")

    def enable_hotspot(self):
        print("run nmcli connection up Hotspot")
        subprocess.run(['sudo', 'nmcli', 'connection', 'up', 'Hotspot'])

    def disable_hotspot(self):
        print("run nmcli connection down Hotspot")
        subprocess.run(['sudo', 'nmcli', 'connection', 'down', 'Hotspot'])

    def get_current_connections(self):
        try:
            with open(os.devnull, 'w') as null_file:
                output = subprocess.check_output(['iwconfig'], text=True, stderr=null_file)

            for line in output.split('\n'):
                if "ESSID:" in line:
                    ssid = line.split("ESSID:")[-1].strip().strip('"')
                    if ssid != "off/any":
                        access_point_line = [line for line in output.split('\n') if "Access Point:" in line]
                        if access_point_line:
                            access_point = access_point_line[0].split("Access Point:")[1].strip()
                            return True, ssid, access_point
                        else:
                            return False, "Not connected to any Wi-Fi network.", ""
                    else:
                        return False, "Not connected to any Wi-Fi network.", ""

            return False, "No Wi-Fi interface found.", ""
        except subprocess.CalledProcessError:
            return False, "Error occurred while getting Wi-Fi information.", ""


    def manage_hotspot(self, hotspot, usersettings, midiports, first_run=False):
        if first_run:
            #self.create_hotspot_profile()
            if int(usersettings.get("is_hotspot_active")):
                print("enabling hotspot - test")
                #usersettings.change_setting_value("is_hotspot_active", 1)
                #self.enable_hotspot()
                return
            elif int(usersettings.get_setting_value("reinitialize_network_on_boot")) == 1:
                pass
                #self.disable_hotspot()

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
                    print("enabling hotspot - test 2")
                    usersettings.change_setting_value("is_hotspot_active", 1)
                    self.enable_hotspot()
            else:
                hotspot.time_without_wifi = 0

        hotspot.last_wifi_check_time = current_time

    # def connect_to_wifi(self, ssid, password, hotspot, usersettings):
    #     print("connecting to wifi")
    #     self.disable_hotspot()
    #     hotspot.hotspot_script_time = time.time()
    #     usersettings.change_setting_value("is_hotspot_active", 0)
    #     subprocess.run([
    #         'sudo', 'nmcli', 'device', 'wifi', 'connect', ssid,
    #         'password', password
    #     ])

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
            print("Result: ", result)
            # Check if the connection was successful
            if result.returncode == 0:
                print(f"Successfully connected to {ssid}")
                usersettings.change_setting_value("is_hotspot_active", 0)
                return True
            else:
                print(f"Failed to connect to {ssid}. Error: {result.stderr}")
                usersettings.change_setting_value("is_hotspot_active", 1)
                self.enable_hotspot()

        except subprocess.TimeoutExpired:
            print(f"Connection attempt to {ssid} timed out")
            usersettings.change_setting_value("is_hotspot_active", 1)
            self.enable_hotspot()
        except Exception as e:
            print(f"An error occurred while connecting to {ssid}: {str(e)}")
            usersettings.change_setting_value("is_hotspot_active", 1)
            self.enable_hotspot()

    def disconnect_from_wifi(self, hotspot, usersettings):
        print("disconnecting from wifi")
        hotspot.hotspot_script_time = time.time()
        self.enable_hotspot()
        usersettings.change_setting_value("is_hotspot_active", 1)

    def get_wifi_networks(self):
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

            wifi_list = []
            for network in networks[1:]:
                wifi_data = {}

                address_line = [line for line in network.split('\n') if 'Address:' in line]
                if address_line:
                    wifi_data['Address'] = address_line[0].split('Address:')[1].strip()

                ssid_line = [line for line in network.split('\n') if 'ESSID:' in line]
                if ssid_line:
                    wifi_data['ESSID'] = ssid_line[0].split('ESSID:')[1].strip('"')

                freq_line = [line for line in network.split('\n') if 'Frequency:' in line]
                if freq_line:
                    wifi_data['Frequency'] = freq_line[0].split('Frequency:')[1].split(' (')[0]

                signal_line = [line for line in network.split('\n') if 'Signal level=' in line]
                if signal_line:
                    signal_level = int(signal_line[0].split('Signal level=')[1].split(' dBm')[0])
                    wifi_data['Signal Strength'] = calculate_signal_strength(signal_level)

                signal_dbm = [line for line in network.split('\n') if 'Signal level=' in line]
                if signal_dbm:
                    signal_dbm = signal_dbm[0].split('Signal level=')[1].split(' dBm')[0]
                    wifi_data['Signal dBm'] = int(signal_dbm)

                wifi_list.append(wifi_data)

            # Sort descending by "Signal Strength"
            wifi_list.sort(key=lambda x: x['Signal Strength'], reverse=True)

            return wifi_list
        except subprocess.CalledProcessError as e:
            logger.warning("Error while scanning Wi-Fi networks:", e.output)
            return []
