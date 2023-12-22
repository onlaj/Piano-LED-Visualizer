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
        call("sudo git clean -fdx -e Songs/ -e config/settings.xml", shell=True)
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

    def manage_hotspot(self, hotspot, usersettings, midiports, first_run=False):
        if not hotspot.is_hostapd_installed:
            return

        # Visualizer is starting, check if hotspot is active and run enable_ap.sh
        if first_run:
            self.create_hotspot_config()
            if int(usersettings.get("is_hotspot_active")):
                self.disconnect_from_wifi(hotspot, usersettings)
                return
            elif int(usersettings.get_setting_value("reinitialize_network_on_boot")) == 1:
                try:
                    logger.info("Running disable_ap.sh")
                    subprocess.Popen(['sudo', './disable_ap.sh'], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
                except Exception as error:
                    # handle the exception
                    logger.info("An exception occurred while shutting down a hotspot:", error)

        # Calculate time passed without Wi-fi
        current_time = time.time()
        if not hotspot.last_wifi_check_time:
            hotspot.last_wifi_check_time = current_time

        time_without_wifi = current_time - hotspot.last_wifi_check_time

        # run script every 60 seconds
        if (time.time() - hotspot.hotspot_script_time) > 60 and time.time() - midiports.last_activity > 60:
            hotspot.hotspot_script_time = current_time
            if int(usersettings.get("is_hotspot_active")):
                return

            # check if wi-fi is connected
            wifi_success, wifi_ssid, address = self.get_current_connections()

            if not wifi_success:
                # Update the time without Wi-Fi
                hotspot.time_without_wifi += time_without_wifi
                logger.info("Time without Wi-Fi: ", hotspot.time_without_wifi)

                # If hotspot.time_without_wifi is greater than 240 seconds, start hotspot
                if hotspot.time_without_wifi > 240:
                    usersettings.change_setting_value("is_hotspot_active", 1)
                    time.sleep(2)
                    self.disconnect_from_wifi(hotspot, usersettings)
            else:
                # Reset the time without Wi-Fi since there is a connection now
                hotspot.time_without_wifi = 0

    def create_hotspot_config(self):
        hotspot_config_content = """
interface=wlan0
driver=nl80211
ssid=PianoLEDVisualizer
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=visualizer
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""

        filepath = '/etc/hostapd/hostapd.conf'

        try:
            # Check if the file doesn't exist or is empty
            if not (os.path.exists(filepath) and os.path.getsize(filepath) > 0):
                with open(filepath, 'w') as file:
                    file.write(hotspot_config_content)
                logger.info("Hotspot configuration added successfully.")
        except Exception as e:
            logger.warning(f"Error: {e}")

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

    def connect_to_wifi(self, ssid, password, hotspot, usersettings):
        hotspot.hotspot_script_time = time.time()
        logger.info("Method:connecting to wifi")
        success, wifi_ssid, address = self.get_current_connections()

        if success:
            if wifi_ssid == ssid:
                logger.info("Already connected to Wi-Fi:", ssid)
                return True

        wpa_conf = """country=GB
        ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
        update_config=1
        network={
            scan_ssid=1
            ssid="%s"
            %s
        }"""

        pwd = 'psk="' + password + '"'
        if password == "":
            pwd = "key_mgmt=NONE"  # If open AP

        with open('config/wpa_disable_ap.conf', 'w') as f:
            f.write(wpa_conf % (ssid, pwd))
        logger.info("Running shell script disable_ap")
        try:
            subprocess.Popen(['sudo', './disable_ap.sh'], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        except Exception as error:
            # handle the exception
            logger.warning("An exception occurred while shutting down a hotspot:", error)
        usersettings.change_setting_value("is_hotspot_active", 0)

    def disconnect_from_wifi(self, hotspot, usersettings):
        hotspot.hotspot_script_time = time.time()
        logger.info("Running script enable_ap")
        try:
            subprocess.Popen(['sudo', './enable_ap.sh'], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        except Exception as error:
            # handle the exception
            logger.warning("An exception occurred while creating a hotspot:", error)
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
