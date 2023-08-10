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
}```



