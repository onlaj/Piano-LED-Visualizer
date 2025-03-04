# <a href="url"><img src="https://raw.githubusercontent.com/onlaj/Piano-LED-Visualizer/master/Docs/logo.svg" align="left" height="40" width="40" ></a> Piano LED Visualizer
### <a style="color:inherit;margin-left:10px;" href="https://discord.gg/kQyABw8GCD"><img src="https://raw.githubusercontent.com/onlaj/Piano-LED-Visualizer/master/Docs/discord-logo.svg" align="left" height="25" width="25">Join Discord</a>

## [![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/onlaj)

[![Everything Is AWESOME](https://i.imgur.com/AEGVXs2.png)](https://www.youtube.com/watch?v=t6PyMeW4dmw "Piano LED Visualizer")

The Piano LED Visualizer is a project that enables you to connect an LED strip to your Raspberry Pi and enhance your piano playing with captivating visual effects. This repository provides detailed instructions on how to set up the LED strip, connect it to a digital piano, and synchronize the lighting with your playing. Additionally, it offers integration with external software such as Synthesia for an enhanced learning experience.
# Features

- Visual Effects: Acts as a sound visualizer, making your piano playing look cool with lights that react to your music.

- Learning: Lights above the keys show you which ones to play, helping you learn piano.

- MIDI Integration: Supports external software like Synthesia for lighting next-to-play keys.

- Customizable Lights: You can change the colors and brightness of the lights to fit your style.

- Record and Play: Record your piano songs, download them or play directly from Visualizer.

- MIDI Files: Load MIDI files to see which keys to play, making it easy to learn new songs.

- Light Sequences: Create sequences to switch between different light settings during your performance.

- Web Control: Use a simple web interface to set up and control the lights.

- Optional Hat Extension: There's an extra hat with buttons and a screen for easier control, making it a standalone device.

- Cool Animations: Enjoy light animations to add atmosphere to your music.

## [Detailed feature showcase with images](https://github.com/onlaj/Piano-LED-Visualizer/blob/master/Docs/features.md)

# What you need:

  - Piano with MIDI or USB output
  - MIDI to USB interface (if your piano doesn't have USB output) [Amazon US](https://amzn.to/2nhsYBl) | [Amazon FR](https://amzn.to/3Ul5wAi) | [Aliexpress](https://s.click.aliexpress.com/e/_DBobxwH) (cheap midi interfaces might not work as intended, I recommend hardware from more known brands. I personally use iConnectivity mio 
  - Raspberry Pi Zero WH [Amazon US](https://amzn.to/3D9hMdc) | [Amazon FR](https://amzn.to/3SDyxWA) | [Aliexpress](https://s.click.aliexpress.com/e/_dXc8jGl) | [Aliexpress #2](https://s.click.aliexpress.com/e/_DmR3jvb)
  - MicroSD card (16 GB is more than enough, Class 10 recommended for faster loading) [Amazon US](https://amzn.to/2oR93cC) | [Amazon FR](https://amzn.to/480tZxM)) | [Aliexpress](https://s.click.aliexpress.com/e/_DdNW6lB)
  - USB OTG hub (At least two ports, for piano and computer/tablet connection) [Amazon US](https://amzn.to/3yVpdmV) | [Amazon FR](https://amzn.to/3HBY6kv) | [Aliexpress](https://s.click.aliexpress.com/e/_DBrYA2p)
  - WS2812B LED Strip (*at least 1.5m with 144 diodes/meter*)  [Amazon US](https://amzn.to/2JTFpuh) | [Amazon FR](https://amzn.to/3SBT0eh) | [Aliexpress](https://s.click.aliexpress.com/e/_DEEkJyR)
  - Power Supply (*5V 6A is enough to light 172 LEDs @50% power*)  [Amazon US](https://amzn.to/3O5zAJc) | [Amazon FR](https://amzn.to/42loc4x) | [Aliexpress](https://s.click.aliexpress.com/e/_Dn5Mt0n)

 **Make sure the power supply is 5V (5 Volt). using power supply with more Volt WILL damage both LED strip and Raspberry Pi.**

  - female DC 5.5x2.5mm socket with quick connection [Amazon US](https://amzn.to/3NJcTfP) | [Aliexpress](http://s.click.aliexpress.com/e/T8YSkbq)
   *(if you bought power supply on amazon it might be already included)*
  - Some wires *(22–18 AWG, at least 1 meter; more if placing Raspberry Pi further away from piano)* [Amazon US](https://amzn.to/3ky6k2G) | [Aliexpress](https://s.click.aliexpress.com/e/_AKKvPu)

**Not required but worth having, to make everything look neat:**

  - Custom 3d printed case (*I attached [STL file](https://github.com/onlaj/Piano-LED-Visualizer/blob/master/Docs/RPICaseModel.stl) with modified 3d model, there is additional space and holes for power socket and wires, [here](https://www.thingiverse.com/thing:3393553) is original model*). Optionally you can use models without a holes for screen, hdmi and sd port, provided by [fermaton](https://github.com/fermaton)
  - Nylon standoffs M2.5 10mm [Amazon US](https://amzn.to/3Ku1Lma) | [Aliexpress](https://s.click.aliexpress.com/e/_DkrBqaX)
  - Screws M2.5 10mm [Amazon US](https://amzn.to/47iQv5P) | [Aliexpress](https://s.click.aliexpress.com/e/_DmAzsqB)
  - Waveshare LCD TFT 1,44'' 128x128px [Amazon US](https://amzn.to/2YkW5nC) | [Aliexpress](http://s.click.aliexpress.com/e/cpk00blQ)
  - Braid for cables [Amazon US](https://amzn.to/3rmCrYF) | [Aliexpress](http://s.click.aliexpress.com/e/cG7ur6Di)
  - Heat shrink bands *(diameter slightly larger than chosen wires; used for insulation and securing connections)* [Amazon US](https://amzn.to/3NPO3uy) | [Aliexpress](http://s.click.aliexpress.com/e/UwKVLo8)
  - Aluminium LED Profile with diffuser (*highly recommend to search for the right one in local shops*) [pic#1](https://i.imgur.com/MF7dd1R.png) [pic#2](https://i.imgur.com/fFWOs3v.png) 
  Alternative made of silica gel: [Aliexpress](https://s.click.aliexpress.com/e/_A0HNfF)  *(choose T0515 for 12mm 2 meters, credits to [vzoltan](https://github.com/vzoltan) for finding this)*
  - Double side tape to stick everything on the piano
  - Windows 10 laptop/tablet with bluetooth to run Synthesia
  - magnetic or mechanical switch to detect if the keyboard cover is opened or closed, if your piano has one (see [Instructions](https://github.com/onlaj/Piano-LED-Visualizer/blob/master/Docs/cover_detection.md))

  *For items like screws, standoffs, and wires, look at local hardware stores to avoid buying in bulk.*

**Total cost (excluding piano and tablet) should be 75-100 USD**
*Disclosure: All of the links above are affiliate links, which means that without additional costs for you, I will earn a commission if you make a purchase by clicking through it.*

## Software preparations
There are two ways, you can use preconfigured system image or install everything manually.

### 1. **System image**
- Download the latest zip file from releases.
- Unzip the file.
- Use program like [Win32 Disk Imager](https://sourceforge.net/projects/win32diskimager/) or [Etcher](https://www.balena.io/etcher/) to save system image to your SD card (4GB is a minimum).

If you don't need to connect your RPi to Wi-Fi you can eject SD card from your PC and put it in Raspberry Pi. After 3-8 minutes *(depending on how fast your SD card is)* you should see Visualizer menu on RPi screen.  

For version 1.5 and above:

The Raspberry Pi sets up a Wi-Fi hotspot named 'PianoLEDVisualizer' with the password 'visualizer'. 
Once connected, open your browser and go to "pianoledvisualizer.local" to access the web interface. 
Use the "Network" tab there to link the Raspberry Pi to your regular network.

You can also connect Raspberry Pi to your network [manually](https://github.com/onlaj/Piano-LED-Visualizer/blob/master/Docs/wifi_setup.md)

### 2. **Manual installation**
[Instructions](https://github.com/onlaj/Piano-LED-Visualizer/blob/master/Docs/manual_installation.md)

## Connecting LED Strip to Raspberry Pi
There is no point to reinvent the wheel again, here is a nice [tutorial](https://tutorials-raspberrypi.com/connect-control-raspberry-pi-ws2812-rgb-led-strips/) *(do only the hardware part)*.
Double check how your LED strip is wired. Most strips use G-D-V (ground, data, voltage), however in the wiring diagram shown in the tutorial the voltage and data lines are swapped.
Connecting voltage directly to your data pin might seriously damage or kill your Raspberry!

Optionally, you can connect a switch to BCM pin 12 and GND. Attach the switch to the key cover, if available. When it is closed, the animations are automatically switched off.

If you are wondering how to connect wires to RPI if screen hat is taking all pins here is a [picture](https://i.imgur.com/7KhwM7r.jpg) of how I did it. There should be a gap between RPI and screen so you can solder your wires or just wrap cables around the pins and separate them with heat shrink bands.

After connecting all cables as described above everything should fit nicely to case. Scroll down to see some photos of the setup I made
If you don't have a 3d printer, try to find some company or private person who will print it for you. I paid 12USD for my print. [RPICaseModel.stl](https://github.com/onlaj/Piano-LED-Visualizer/blob/master/Docs/RPICaseModel.stl "RPICaseModel.stl")

## Web interface
The visualizer comes with a web interface with which you can control the colors of the LED strip, change port settings, run animations of the strip, control sequences and manage midi files, including downloading, uploading, renaming, deleting, and playing.
To connect to the web interface, type the local address of your raspberry pi in the browser, for example [http:/192.168.1.10](http:/192.168.1.10)
Both devices must be connected to the same network. By default, web interface works on port 80, but if needed it can be changed with the script's argument `--port`

    sudo python3 /home/Piano-LED-Visualizer/visualizer.py --port 5000

Although in my tests I did not notice any deterioration in performance, if necessary, you can disable the web interface with the `--webinterface` parameter

    sudo python3 /home/Piano-LED-Visualizer/visualizer.py --webinterface false


## FAQ ##
**Q - Can I use Raspberry Pi 1/2/3/4 instead of Zero?**

- In theory, yes. In practice many users reported problems with huge delay between key presses and lights reacting to it on Raspberrys other than Zero.

**Q - What about Raspberry Pi Zero without Wi-Fi and bluetooth?**

- If you are going only for the visuals and do not plan to use it with Synthesia you can save some bucks and buy cheaper, non-WH version of Zero. 
Notice, that you won't be able to use web interface

**Q - Can I use other screens or no screen at all?**

- Currently, the only other supported screen is Waveshare LCD TFT 1,3". As for no screen, you can instead use web interface.

**Q - Does the color of LED strip PCB matter?**

- No, it's only visuals.

**Q - Can I use other led strip?**

- Only WS281X led strips are supported

**Q - Do I need power supply for LED strip?**

- RPi alone should be fine powering up to 10 LEDs at the same time, although I do not recommend it.

**Q - Do I need soldering skills to make it?**

- Users reported that LED strips bought on Amazon are shipped in one meter strips, in that case you would need to solder them. I bought mine on Aliexpress and it was 2 meters long strip in one piece. As for connecting wires to RPi, I just wrapped them around pins and tightened it with heat shrink bands.

**Q - How do I access recorded files?**

- If you connected your RPi to Wi-Fi you can use SFTP or web interface to transfer files. 

For web interface: Open internet browser on device connected to the same network and type RPi's local address `pianoledvisualizer.local` Then from the menu on the left choose "songs management" tab.

For SFTP: in any FTP program (like Filezilla) connect to your RPi local address (for example: sftp://192.168.1.10) and navigate to /home/Piano-LED-Visualizer/Songs.

**Q - How do I update visualizer?**

- **A** - From the Visualiser menu `Other Settings > Update visualizer > Confirm`. 
 
After the update, a reboot is required.

- **B** - Connect to your console using SSH and type:

`cd /home/Piano-LED-Visualizer`
and then 

`git pull origin master`

If for some reasons it does not work try to remove whole project and clone it again.

`cd /home`

`sudo rm -rf Piano-LED-Visualizer`

`sudo git clone https://github.com/onlaj/Piano-LED-Visualizer`


![Image](https://i.imgur.com/9MgNUl5.jpg?1)
![Image](https://i.imgur.com/WGxGdNM.jpg?2)
![Image](https://i.imgur.com/J1wA1rU.jpg)



![sidebar](https://i.imgur.com/ZVLsu0K.png)
![homepage](https://i.imgur.com/LiSszwF.png)
![changing led colors](https://i.imgur.com/iBEIM3x.png)
![ports settings](https://i.imgur.com/k6stIXg.png)
![songs_management](https://i.imgur.com/uoD2Gxz.png)

![Image](https://i.imgur.com/5riJs9k.jpg?1)
![Image](https://i.imgur.com/LLzeff2.jpg?1)
![Image](https://i.imgur.com/ZnYBxTp.jpg)
![Image](https://i.imgur.com/FVWnBv1.jpg?2)
![Image](https://i.imgur.com/e97ilNU.jpg?1)
