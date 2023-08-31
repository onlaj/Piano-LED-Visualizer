# /draft/

https://github.com/schollz/raspberry-pi-turnkey

default wpa.conf for hotspot:

```
country=GB
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
```

for normal connection:

```
country=GB
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
network={
    ssid="wifi name"
    psk="password"
}
```


After switching to wi-fi:

```
#!/bin/bash

sleep 3

# disable the AP
sudo cp config/hostapd.disabled /etc/default/hostapd
sudo cp config/dhcpcd.conf.disabled /etc/dhcpcd.conf
sudo cp config/dnsmasq.conf.disabled /etc/dnsmasq.conf

# load wlan configuration
sudo cp disable_wpa.conf /etc/wpa_supplicant/wpa_supplicant.conf

sleep 5
sudo wpa_cli -i wlan0 reconfigure
sudo wpa_cli -i p2p-dev-wlan0
sleep 5
sudo ifconfig wlan0 down
sleep 10
sudo ifconfig wlan0 up
```

After switching to hotspot:

```
#!/bin/bash

sleep 3

# enable the AP
sudo cp config/hostapd /etc/default/hostapd
sudo cp config/dhcpcd.conf /etc/dhcpcd.conf
sudo cp config/dnsmasq.conf /etc/dnsmasq.conf

# load wan configuration
sudo cp wpa.conf /etc/wpa_supplicant/wpa_supplicant.conf

sleep 5
sudo wpa_cli -i wlan0 reconfigure
sudo wpa_cli -i p2p-dev-wlan0 reconfigure
sleep 5
sudo ifconfig wlan0 down
sleep 10
sudo ifconfig wlan0 up
sleep 20
sudo systemctl restart hostapd
```
