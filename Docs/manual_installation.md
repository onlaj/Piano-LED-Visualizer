
Install [Raspberry Pi OS Lite](https://www.raspberrypi.org/software/) on your SD card.

If you are not able to connect your monitor, mouse and keyboard to RPi you can connect to it using SSH. Here you can find full tutorial: [Raspberry Pi Setup Without a Monitor, Keyboard or a Mouse](https://www.terminalbytes.com/raspberry-pi-without-monitor-keyboard/ "Raspberry Pi Setup Without a Monitor, Keyboard or a Mouse")

*Note: replace `“` with `"` when editing `wpa_supplicant.conf` file.*

 
### 1. **Updating OS** 
After succesfully booting RPi (and connecting to it by SSH if necessary) we need to make sure that everything is up to date.
- `sudo apt-get update`
- `sudo apt-get upgrade` //*it will take a while, go grab a coffee*


### 2. **Creating autoconnect script** ### 
*You can skip this part if you don't plan to connect any MIDI device other than a piano.*
- Create `connectall.rb` file

 `sudo nano /usr/local/bin/connectall.rb`
- paste the script:
```ruby
#!/usr/bin/ruby

t = `aconnect -i -l`
$devices = {}
$device = 0
t.lines.each do |l|
  match = /client (\d*)\:((?:(?!client).)*)?/.match(l)
  # we skip empty lines and the "Through" port
  unless match.nil? || match[1] == '0' || /Through/=~l
    $device = match[1]
    $devices[$device] = []
  end
  match = /^\s+(\d+)\s/.match(l)
  if !match.nil? && !$devices[$device].nil?
    $devices[$device] << match[1]
  end
end

$devices.each do |device1, ports1|
  ports1.each do |port1|
    $devices.each do |device2, ports2|
      ports2.each do |port2|
        # probably not a good idea to connect a port to itself
        unless device1 == device2 && port1 == port2 
          system "aconnect #{device1}:#{port1} #{device2}:#{port2}"
        end
      end
    end
  end
end
```
Press CTRL + O to save file, confirm with enter and CTRL + X to exit editor.
- Change permissions:

    `sudo chmod +x /usr/local/bin/connectall.rb`

- Make the script launch on USB connect:

   ` sudo nano /etc/udev/rules.d/33-midiusb.rules`

- Paste and save:

    `ACTION=="add|remove", SUBSYSTEM=="usb", DRIVER=="usb", RUN+="/usr/local/bin/connectall.rb"  `

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
ExecStart=/usr/local/bin/connectall.rb

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
sudo apt-get install -y ruby git python3-pip autotools-dev libtool autoconf libasound2-dev libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev python-dev libatlas-base-dev libopenjp2-7 libtiff5 libjack0 libjack-dev libasound2-dev fonts-freefont-ttf gcc make build-essential python-dev git scons swig libavahi-client3
```


### 5. **Disabling audio output** ### 

    `sudo nano /etc/modprobe.d/snd-blacklist.conf`
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

`sudo wget https://github.com/davidmoreno/rtpmidid/releases/download/v20.07/rtpmidid_20.07_armhf.deb`
- Install package

`sudo dpkg -i rtpmidid_20.07_armhf.deb`


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

`sudo crontab -e`
- At the bottom of file paste:

`@reboot sudo python3 /home/Piano-LED-Visualizer/visualizer.py &`

*If you are using WaveShare 1.3inch 240x240 LED Hat instead of 1.44inch 128x128, add this instead:*
`@reboot sudo python3 /home/Piano-LED-Visualizer/visualizer.py --display 1in3 &`

Now you can type `sudo reboot` to test if everything works. After 1-3 minutes you should see Visualizer menu on RPi screen.
