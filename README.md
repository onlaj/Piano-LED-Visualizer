

# Piano LED Visualizer

## [![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/onlaj)

[![Everything Is AWESOME](https://i.imgur.com/xpfZ0Z6.png)](https://www.youtube.com/watch?v=IZgYViHcXdM "Piano LED Visualizer")

# What you need:

  - Piano with MIDI or USB output
  - MIDI to USB interface (if your piano doesn't have USB output) ~~[Amazon US](https://amzn.to/2xZUipg) | [Aliexpress](http://s.click.aliexpress.com/e/b9mjFaIy)~~ (cheap midi interfaces might not work as intended, I recommend hardware from more known brands. I personally use iConnectivity mio [Amazon US](https://amzn.to/2nhsYBl) )
  - Raspberry Pi Zero WH [Amazon US](https://amzn.to/2TPz3CQ) | [Aliexpress](https://s.click.aliexpress.com/e/_dXc8jGl) | [Aliexpress #2](http://s.click.aliexpress.com/e/3r32Dass)
  - MicroSD card (16GB is more than enough) [Amazon US](https://amzn.to/2oR93cC) | [Aliexpress](http://s.click.aliexpress.com/e/mGNi7sl2)
  - USB OTG [Amazon US](https://amzn.to/3aYWVJj) | [Aliexpress](https://s.click.aliexpress.com/e/_d7FjmJD)
  - WS2812B LED Strip (*at least 1.5m with 144 diodes/meter*)  [Amazon US](https://amzn.to/2JTFpuh) | [Aliexpress](http://s.click.aliexpress.com/e/dFyC7NO)
  - Power Supply (*5V 6A is enough to light 172 LEDs @50% power*)  [Amazon US](https://amzn.to/2JViZJ3) | [Aliexpress](http://s.click.aliexpress.com/e/hUgrv6s)
  - DC 5.5x2.5mm socket with quick connection [Amazon US](https://amzn.to/2YizYOC) | [Aliexpress](http://s.click.aliexpress.com/e/T8YSkbq)
  - Waveshare LCD TFT 1,44'' 128x128px [Amazon US](https://amzn.to/2YkW5nC) | [Aliexpress](http://s.click.aliexpress.com/e/cpk00blQ)
  - Some wires

**Not required but worth having, to make everything look neat:**

  - Custom 3d printed case (*I attached STL file with modified 3d model, there is additional space and holes for power socket and wires, [here](https://www.thingiverse.com/thing:3393553) is original model*) 
  - Braid for cables [Amazon US](https://amzn.to/2yd2Fhz) | [Aliexpress](http://s.click.aliexpress.com/e/cG7ur6Di)
  - Heat shrink bands [Amazon US](https://amzn.to/2SsSYok) | [Aliexpress](http://s.click.aliexpress.com/e/UwKVLo8)
  - Aluminium LED Profile with diffuser (*highly recommend to search for the right one in local shops*) [pic#1](https://i.imgur.com/MF7dd1R.png) [pic#2](https://i.imgur.com/fFWOs3v.png) 
  [Aliexpress](https://s.click.aliexpress.com/e/_A0HNfF)  *(choose T0515 for 12mm 2 meters, credits to [vzoltan](https://github.com/vzoltan) for finding this)*
  - Double side tape to stick everything on the piano
  - Windows 10 laptop/tablet with bluetooth to run Synthesia

**Total cost (excluding piano and tablet) should be 75-100 USD**
*Disclosure: All of the links above are affiliate links, which means that without additional costs for you, I will earn a commission if you make a purchase by clicking through it.*

## Software preparations
There are two ways, you can use preconfigured system image or install everything manually.

### 1. **System image**
- Download latest zip file from releases.
- Unzip the file.
- Use program like [Win32 Disk Imager](https://sourceforge.net/projects/win32diskimager/) or [Etcher](https://www.balena.io/etcher/) to save system image to your SD card (4GB is a minimum).

If you don't need to connect your RPi to Wi-Fi you can eject SD card from your PC and put it in Raspberry Pi. After 3-8 minutes *(depending on how fast your SD card is)* you should see Visualizer menu on RPi screen.

If you want to make your RPi autoconnect to Wi-Fi you need to follow [this guide](https://www.terminalbytes.com/raspberry-pi-without-monitor-keyboard/) *(starting from step 3)*

*Note: replace `“` with `"` when editing `wpa_supplicant.conf` file.*

### 2. **Manual installation**
[Instruction](https://github.com/onlaj/Piano-LED-Visualizer/blob/master/manual_installation.md)

## Learning to play with Synthesia

### We need to make a connection between your PC/MAC/Android. There are at least 3 ways of doing that: ###

**1. Sevilla's Soft MIDI USB-USB device**
This is, in my opinion, the best way to make connection between RPi and PC. It works with any device that support MIDI over USB, offers the lowest latency and no lost packets. The only downside is that it cost €39.00 (~48 USD) + shipping. You connect your Piano and PC to USB HUB connected to RPi and that's it, everything just works.
[Link to store](http://compasflamenco.com/midi-c-3/midi-usbusb-p-4.html)

**2. RTP MIDI** (MIDI by ethernet)
For this method you need to use some software on your Synthesia's device and both devices must be connected to the same local network.

- Windows: [rtpMIDI](https://www.tobias-erichsen.de/software/rtpmidi.html) by [Tobias Erichsen](https://www.tobias-erichsen.de/ "Tobias Erichsen") | [tutorial](http://www.tobias-erichsen.de/software/rtpmidi/rtpmidi-tutorial.html)

- MAC: [Tutorial](https://www.wiksnet.com/Home/Help)
- Android [touchdaw](https://xmmc.de/touchdaw/)

Default port is 5004.

- Connect RTP MIDI server with your piano, type:
`aconnect -i -l`
You should see something like:

```bash

pi@raspberrypi:~ $ aconnect -i -l
client 0: 'System' [type=kernel]
    0 'Timer           '
    1 'Announce        '
client 14: 'Midi Through' [type=kernel]
    0 'Midi Through Port-0'
client 20: 'mio' [type=kernel,card=1]
    0 'mio MIDI 1      '
client 128: 'rtpmidi raspberrypi' [type=user,pid=475]
    0 'Network         '
    1 'DESKTOP-VMRSF66 '
client 133: 'RtMidiOut Client' [type=user,pid=583]
    0 'RtMidi output   '
client 134: 'RtMidiOut Client' [type=user,pid=583]
    0 'RtMidi output   '
        Connecting To: 128:0[real:0]
```
Look for your piano name and RTP midi ports, in my case it's `mio MIDI 1` and `rtpmidi raspberrypi`.
- Connect them accordingly with:

`aconnect 20:0 128:1`

`aconnect 128:1 20:0`

In case of any problems those commands might be helpful:

`sudo systemctl restart rtpmidid` *restarting RTP midi service*

`aconnect --removeall` *removing all connections between ports*

**3. Bluetooth**
This method is not recommended due to problems with establishing the first connection, especially on devices other than those with Windows 10.
If you still want to try, follow [this link](https://github.com/onlaj/Piano-LED-Visualizer/blob/master/btconnection.md) for instructions.


### Configuring Synthesia

You have to enable light support in Synthesia by setting "Key Light" option to "Finger-based channel".
In Visualizer settings you have to change "input" to either *RPI Bluetooth* (for bluetooth connection), *rtpmidi raspberrypi* (for RTP connections) or *MIDI USB-USB* (for cable connection).
After that when learning new song next-to-play keys will be illuminated in corresponding colors, blue for left hand and green for right hand.

If you are getting mixed colors, meaning that leds are lighting up with your predefined and next-to-play colors at the same time, you can use "Skipped notes" option in Visualizer to disable one of them.


## Learning to play MIDI files

The Visualizer supports learning to play MIDI files without the need of Synthesia or additional external devices.

![learnmidi_pic](/Docs/pics/learnmidi_pic.png)

For practicing, the following 3 modes can be used:
- **Melody**: The song will wait for you to hit the correct notes. Take your time and try to avoid mistakes. Holding notes to their full duration is also important, otherwise you might develop muscle memory with the mistakes included.
- **Rhythm**: Adjust the speed using `Set tempo` option until you can play without mistakes. Play as fast as you can comfortably. Work your way up to `100%` speed. Practice the `Melody` first to make this step easier.
- **Listen**: In this mode the song will play in listen only mode at the `Set tempo` speed.

Different combinations of practicing modes be realized using the `Hands` and `Mute Hand` options. To practice only a section of the song, adjust the `Start point` and the `End point` values.

Recommended way of practicing is by following the song music sheet (see below how to print the music sheet from a midi file), while the Visualizer indicates the notes to press on the piano.

### Handling MIDI files

- **Generating music sheet**: To generate a printable music sheet from a MIDI file use the [Midi Sheet Music](http://midisheetmusic.com/) app. The app already contains a library of MIDI files that can be played.
- **Editing MIDI files**: To visualize and edit MIDI files use the [MidiEditor](https://www.midieditor.org/). Only type 1 of midi files have been tested. Other types of midi files might need to be adjusted in order to work with the Visualizer.
- **Uploading MIDI files**: Two ways are proposed here to upload MIDI files to Raspberry Pi Zero 
  - From PC: [WinSCP](https://winscp.net/eng/index.php)
  - From Smartphone: [RaspController](https://play.google.com/store/apps/details?id=it.Ettore.raspcontroller&hl=en&gl=US)

In case of upload errors, use [Putty](https://www.putty.org/) to change the access permissions for the `Songs` folder:
```
cd /home/Piano-LED-Visualizer/
sudo chmod a+rwxX -R Songs/
```


## Connecting LED Strip to Raspberry Pi and enabling SPI
There is no point to reinvent the wheel again, here is a nice [tutorial](https://tutorials-raspberrypi.com/connect-control-raspberry-pi-ws2812-rgb-led-strips/) *(do only the hardware part)*

If you are wondering how to connect wires to RPI if screen hat is taking all pins here is a [picture](https://i.imgur.com/7KhwM7r.jpg) of how I did it. There should be a gap between RPI and screen so you can solder your wires or just wrap cables around the pins and separate them with heat shrink bands.

After connecting all cables as described above everything should fit nicely to case. Scroll down to see some photos of the setup I made
If you don't have a 3d printer (like me) try to find some company or private person who will print it for you. I paid 12USD for my print. [RPICaseModel.stl](https://github.com/onlaj/Piano-LED-Visualizer/blob/master/RPICaseModel.stl "RPICaseModel.stl")

## FAQ ##
**Q - Can I use Raspberry Pi 1/2/3/4 instead of Zero?**

- In theory, yes. In practice many users reported problems with huge delay between key presses and lights reacting to it on Raspberrys other than Zero.

**Q - What about Raspberry Pi Zero without Wi-Fi and bluetooth?**

- If you are going only for the visuals and do not plan to use it with Synthesia you can save some bucks and buy cheaper, non-WH version of Zero.

**Q - Can I use other screens or no screen at all?**

- Currently the only other supported screen is Waveshare LCD TFT 1,3". As for no screen, you need it for changing LED settings. If you don't mind changing it manually by editing settings file you can go without screen.

**Q - Does the color of LED strip PCB matter?**

- No, it's only visuals.

**Q - Can I use other led strip?**

- Only WS281X led strips are supported

**Q - Do I need power supply for LED strip?**

- RPi alone should be fine powering up to 10 LEDs at the same time, although I do not recommend it.

**Q - Do I need soldering skills to make it?**

- Users reported that LED strips bought on Amazon are shipped in one meter strips, in that case you would need to solder them. I bought mine on Aliexpress and it was 2 meters long strip in one piece. As for connecting wires to RPi, I just wrapped them around pins and tightened it with heat shrink bands.

**Q - How do I access recorded files?**

- If you connected your RPi to Wi-Fi you can use SFTP to transfer files. In any FTP program like Filezilla connect to your RPi local address (for example: sftp://192.168.1.10 ) and navigate to /home/Piano-LED-Visualizer/Songs.

**Q - How do I update visualizer?**

- **A** - Connect to your console using SSH and type:

`cd /home/Piano-LED-Visualizer`
and then 

`git pull origin master`

If for some reasons it does not work try to remove whole project and clone it again.

`cd /home`

`sudo rm -rf Piano-LED-Visualizer`

`sudo git clone https://github.com/onlaj/Piano-LED-Visualizer`

## Using the sequences
In the visualizer menu you can find setting called "Sequences". It allows you to change led properties while playing using third key on Waveshare hat or your piano pedals.
You can edit or create new sequences by editing "sequences.xml" file.
The "control_number" defines which pedal is used to go to the next step.

|Control number| Pedal name |
|--|--|
| 64 | Damper Pedal (Sustain/Hold) On/Off  |
| 65 | Portamento On/Off |
| 66 | Sostenuto On/Off |
| 67 | Soft Pedal On/Off |

The "next_step" value decides if next step is activated when you press or release the pedal. For example if you want to change settings after fully pressing Sostenuto pedal you should write it like:

    <control_number>66</control_number> 
    <next_step>126</next_step>
   127 is the maximum value when pedal is fully pressed, so you are saying to script to change settings when value is bigger than 126.
This is how it should look when you want to change settings when fully releasing pedal.

      <control_number>66</control_number> 
	  <next_step>-1</next_step>

 (-) before the number means that next step will be activated when pedal value is below 1.

You can also use sequences as a way to save your presets under custom names.





![Image](https://i.imgur.com/9MgNUl5.jpg?1)
![Image](https://i.imgur.com/WGxGdNM.jpg?2)
![Image](https://i.imgur.com/J1wA1rU.jpg)
![Image](https://i.imgur.com/5riJs9k.jpg?1)
![Image](https://i.imgur.com/LLzeff2.jpg?1)
![Image](https://i.imgur.com/ZnYBxTp.jpg)
![Image](https://i.imgur.com/FVWnBv1.jpg?2)
![Image](https://i.imgur.com/e97ilNU.jpg?1)
