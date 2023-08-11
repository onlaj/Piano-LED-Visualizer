#!/bin/bash

sleep 3

# disable the AP
sudo cp config/hostapd.disabled /etc/default/hostapd
sudo cp config/dhcpcd.conf.disabled /etc/dhcpcd.conf
sudo cp config/dnsmasq.conf.disabled /etc/dnsmasq.conf

# load wlan configuration
sudo cp config/wpa_disable_ap.conf /etc/wpa_supplicant/wpa_supplicant.conf

sleep 5
sudo wpa_cli -i wlan0 reconfigure
sudo wpa_cli -i p2p-dev-wlan0
sleep 5
sudo ifconfig wlan0 down
sleep 10
sudo ifconfig wlan0 up