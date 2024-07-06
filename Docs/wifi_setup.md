### **Wi-Fi setup** (Optional)
  1. In the boot partition of the card you flashed, create a file named `wpa_supplicant.conf` and add the following lines, replacing the ssid and passkey with your own:
```
country=IE 
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev 
update_config=1 
network={ 
scan_ssid=1 
ssid="wifi-network-name"        # Replace with your Wi-Fi name
psk="wifi-network-password"     # Replace with your Wi-Fi password
key_mgmt=WPA-PSK 
}
```
  2. Create another file named `ssh` in the same folder, leave it empty and with no extension. This will allow you to remotely access the RPi's command line. This is not required, but it might make setup easier.
  3. Eject the card and put it in the Raspberry Pi. The pi can take a moment to boot up, so give it a few minutes. There are a few ways you can find the ip of the RPi: 
   
     - If you have an lcd screen, go to *`Other Settings`* > *`Screensaver`* > *`Content`*, and enable `Local IP`. From there, go to *`Other Settings`* and open `System Info`. If the Rpi is connected, it will display the ip
     - Run the command `ping pianoledvisualizer.local`. This might not work, but if it does it should output the ip address.
     - Run the command `nmap 192.168.0.1/24 -p 80`. The RPi should have an open address. Note that `192.168.0.1/24` is the subnet, and might be different depending on the network.
     - Use an app like [Fing](https://play.google.com/store/apps/details?id=com.overlook.android.fing&hl=en_IN) to find the ip.
  4. If you need to ssh into the pi to run commands, run `ssh plv@[the-ip-address]` with the password `visualizer`