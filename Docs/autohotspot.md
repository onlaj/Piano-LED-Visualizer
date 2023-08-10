# /draft/

https://github.com/schollz/raspberry-pi-turnkey

default wpa.conf for hotspot:

`country=GB
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1`

for normal connection:

`country=GB
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
network={
    ssid="wifi name"
    psk="password"
}`


After switching to wi-fi:

sleep 5
sudo wpa_cli -i wlan0 reconfigure
sudo wpa_cli -i p2p-dev-wlan0
sleep 5
sudo ifconfig wlan0 down
sleep 10
sudo ifconfig wlan0 up


After switching to hotspot:

`sleep 5
sudo wpa_cli -i wlan0 reconfigure
sudo wpa_cli -i p2p-dev-wlan0
sleep 5
sudo ifconfig wlan0 down
sleep 10
sudo ifconfig wlan0 up
sleep 5
sudo systemctl restart hostapd`
