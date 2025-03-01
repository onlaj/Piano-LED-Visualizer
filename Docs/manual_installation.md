## Pre-installation setup

Before installing Raspberry Pi OS Lite, it's recommended to configure your system with the following settings:
- Username: plv
- Password: visualizer
- Local hostname: pianoledvisualizer.local

These settings can be easily configured using the **Raspberry Pi Imager** tool:
1. Open Raspberry Pi Imager
2. Select Raspberry Pi OS Lite (for RPi Zero) as your operating system
3. Click the gear/cog icon to access advanced options
4. Set the hostname to "pianoledvisualizer.local"
5. Enable SSH
6. Set username to "plv" and password to "visualizer"
7. Configure your WiFi settings if needed
8. Save settings and write the image to your SD card

This configuration will make it easier to connect to your Raspberry Pi using SSH via `ssh plv@pianoledvisualizer.local`

---

Install [Raspberry Pi OS Lite](https://www.raspberrypi.org/software/) on your SD card.

If you are not able to connect your monitor, mouse and keyboard to RPi you can connect to it using SSH over [Wi-Fi](https://github.com/onlaj/Piano-LED-Visualizer/blob/master/Docs/wifi_setup.md)

Run installation script:

`sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/onlaj/Piano-LED-Visualizer/master/autoinstall.sh)"`

**or follow those steps:**
 
### 1. **Updating OS** 
After succesfully booting RPi (and connecting to it by SSH if necessary) we need to make sure that everything is up to date.
- `sudo apt-get update`
- `sudo apt-get upgrade` //*it will take a while, go grab a coffee*


### 2. **Creating autoconnect script** ### 
*You can skip this part if you don't plan to connect any MIDI device other than a piano.*
- Create `connectall.py` file

 `sudo nano /usr/local/bin/connectall.py`
- paste the script:
```python
#!/usr/bin/python3
import subprocess

ports = subprocess.check_output(["aconnect", "-i", "-l"], text=True)
port_list = []
client = "0"
for line in str(ports).splitlines():
    if line.startswith("client "):
        client = line[7:].split(":",2)[0]
        if client == "0" or "Through" in line:
            client = "0"
    else:
        if client == "0" or line.startswith('\t'):
            continue
        port = line.split()[0]
        port_list.append(client+":"+port)
for source in port_list:
    for target in port_list:
        if source != target:
            #print("aconnect %s %s" % (source, target))
            subprocess.call("aconnect %s %s" % (source, target), shell=True)
```
Press CTRL + O to save file, confirm with enter and CTRL + X to exit editor.
- Change permissions:

    `sudo chmod +x /usr/local/bin/connectall.py`

- Make the script launch on USB connect:

   ` sudo nano /etc/udev/rules.d/33-midiusb.rules`

- Paste and save:

    `ACTION=="add|remove", SUBSYSTEM=="usb", DRIVER=="usb", RUN+="/usr/local/bin/connectall.py"  `

- Reload services:

   ` sudo udevadm control --reload`

    `sudo service udev restart`
- Open file

    `sudo nano /lib/systemd/system/midi.service`
- Paste and save:
```bash
[Unit]
Description=Initial USB MIDI connect

[Service]
ExecStart=/usr/local/bin/connectall.py

[Install]
WantedBy=multi-user.target
```

- Reload daemon and enable service:

   ` sudo systemctl daemon-reload`
   
   ` sudo systemctl enable midi.service`
    
   `sudo systemctl start midi.service`
    

###  3. **Enabling SPI interface** ### 
 - Here you can find instruction: [Enable SPI Interface on the Raspberry Pi](https://www.raspberrypi-spy.co.uk/2014/08/enabling-the-spi-interface-on-the-raspberry-pi/)


### 4. **Installing packages** //*ready for another cup?* ### 

```bash
sudo apt-get install -y ruby git python3-pip autotools-dev libtool autoconf libasound2 libavahi-client3 libavahi-common3 libc6 libfmt9 libgcc-s1 libstdc++6 python3 libopenblas-dev libavahi-client-dev libasound2-dev libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev libatlas-base-dev libopenjp2-7 libtiff6 libjack0 libjack-dev fonts-freefont-ttf gcc make build-essential scons swig abcmidi
```


### 5. **Disabling audio output** ### 

    sudo nano /etc/modprobe.d/snd-blacklist.conf
- paste and save:

    `blacklist snd_bcm2835`
- And one more file:

    `sudo nano /boot/config.txt`
- Change `dtparam=audio=on` to `#dtparam=audio=on`

- Reboot RPi

`sudo reboot`


### 6. **Installing RTP-midi server** (optional) ### 
*This part is not needed if you're not going to connect your RPi to PC.*

We are going to use  [RTP MIDI User Space Driver Daemon for Linux](https://github.com/davidmoreno/rtpmidid/releases)
- Navigate to /home folder:

` cd /home/`   

- Download deb package:


`sudo wget https://github.com/davidmoreno/rtpmidid/releases/download/v24.12/rtpmidid_24.12.2_armhf.deb`
- Install package

`sudo dpkg -i rtpmidid_24.12.2_armhf.deb`

`sudo apt -f install`

### 7. **Installing Piano-LED-Visualizer** ###
- Navigate to /home folder:

` cd /home/`

- GIT clone repository

`sudo git clone https://github.com/onlaj/Piano-LED-Visualizer`

`cd Piano-LED-Visualizer`
- Install required libraries

`sudo pip3 install -r requirements.txt`
- Enable autologin on boot

`sudo raspi-config`

`Select "System options" then “Boot / Auto Login” then “Console Autologin” `
- Enable autostart script on boot:

`sudo nano /lib/systemd/system/visualizer.service`

Paste and save:

```bash
[Unit]
Description=Piano LED Visualizer
After=network-online.target
Wants=network-online.target

[Install]
WantedBy=multi-user.target

[Service]
ExecStart=sudo python3 /home/Piano-LED-Visualizer/visualizer.py
Restart=always
Type=simple
User=pi
Group=pi
```

*If you are using WaveShare 1.3inch 240x240 LED Hat instead of 1.44inch 128x128, edit accordingly:*
`ExecStart=sudo python3 /home/Piano-LED-Visualizer/visualizer.py --display 1in3`

*If you want to use your RPi upside down add `--rotatescreen true` :*

`ExecStart=sudo python3 /home/Piano-LED-Visualizer/visualizer.py --rotatescreen true`

- Reload daemon and enable service:

   ` sudo systemctl daemon-reload`
   
   ` sudo systemctl enable visualizer.service`
    
   `sudo systemctl start visualizer.service`


- Change permissions:

  `sudo chmod a+rwxX -R /home/Piano-LED-Visualizer/`

Now you can type `sudo reboot` to test if everything works. After 1-3 minutes you should see Visualizer menu on RPi screen.
