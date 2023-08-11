#!/bin/bash

sleep 3

# enable the AP
sudo cp config/hostapd /etc/default/hostapd
sudo cp config/dhcpcd.conf /etc/dhcpcd.conf
sudo cp config/dnsmasq.conf /etc/dnsmasq.conf

# load wan configuration
sudo cp wpa_enable_ap.conf /etc/wpa_supplicant/wpa_supplicant.conf

sleep 5
sudo wpa_cli -i wlan0 reconfigure
sudo wpa_cli -i p2p-dev-wlan0 reconfigure
sleep 5
sudo ifconfig wlan0 down
sleep 10
sudo ifconfig wlan0 up
sleep 20
sudo systemctl restart hostapd