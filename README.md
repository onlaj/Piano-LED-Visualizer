# Piano LED Visualizer

## [![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/onlaj)

[![Everything Is AWESOME](https://i.imgur.com/xpfZ0Z6.png)](https://www.youtube.com/watch?v=IZgYViHcXdM "Piano LED Visualizer")

# What you need:

  - Piano with MIDI or USB output
  - MIDI to USB interface (if your piano doesn't have USB output) ~~[Amazon US](https://amzn.to/2xZUipg) | [Aliexpress](http://s.click.aliexpress.com/e/b9mjFaIy)~~ (cheap midi interfaces might not work as intended, I recommend hardware from more known brands. I personally use [iConnectivity mio](https://amzn.to/2nhsYBl) )
  - Raspberry Pi Zero [Amazon US](https://amzn.to/2K8N7B1) | [Aliexpress](http://s.click.aliexpress.com/e/cSG376u0)
  - MicroSD card (16GB is more than enough) [Amazon US](https://amzn.to/2oR93cC) | [Aliexpress](http://s.click.aliexpress.com/e/mGNi7sl2)
  - WS2812B LED Strip (*at least 1.5m with 144 diodes/meter*)  [Amazon US](https://amzn.to/2JTFpuh) | [Aliexpress](http://s.click.aliexpress.com/e/dFyC7NO)
  - Power Supply (*5V 6A is enough to light 172 LEDs @50% power*)  [Amazon US](https://amzn.to/2JViZJ3) | [Aliexpress](http://s.click.aliexpress.com/e/hUgrv6s)
  - DC 5.5x2.5mm socket with quick connection [Amazon US](https://amzn.to/2YizYOC) | [Aliexpress](http://s.click.aliexpress.com/e/T8YSkbq)
  - Waveshare LCD TFT 1,44'' 128x128px [Amazon US](https://amzn.to/2YkW5nC) | [Aliexpress](http://s.click.aliexpress.com/e/cpk00blQ)
  - Some wires

**Not required but worth to have to make everything look neat:**

  - Custom 3d printed case (*I attached STL file with modified 3d model, there is additional space and holes for power socket and wires, [here](https://www.thingiverse.com/thing:3393553) is original model*)
 
  - Braid for cables [Amazon US](https://amzn.to/2yd2Fhz) | [Aliexpress](http://s.click.aliexpress.com/e/cG7ur6Di)
  - Heat shrink bands [Amazon US](https://amzn.to/2SsSYok) | [Aliexpress](http://s.click.aliexpress.com/e/UwKVLo8)
  - Aluminium LED Profile with diffuser (*highly recommend to search for right one in local shops*)
  - Double side tape to mount everything on piano
  - Windows 10 laptop/tablet with bluetooth to run Synthesia

**Total cost (excluding piano and tablet) should be 75-100 USD**
***

## Connecting LED Strip to Raspberry Pi and enabling SPI
There is no point to reinvent the wheel again, here is a nice [tutorial](https://tutorials-raspberrypi.com/connect-control-raspberry-pi-ws2812-rgb-led-strips/)

If you are wondering how to connect wires to RPI if screen hat is taking all pins here is a [picture](https://i.imgur.com/7KhwM7r.jpg) of how I did it. There should be a gap between RPI and screen so you can solder your wires or just wrap cables around the pins and separate them with heat shrink bands.

You also need to [enable SPI](https://www.raspberrypi-spy.co.uk/2014/08/enabling-the-spi-interface-on-the-raspberry-pi/)

## Setting Raspberry Pi as Bluetooth MIDI host
Same as above, here is [instruction](https://neuma.studio/rpi-as-midi-host.html)
Just do following parts and skip the others:
- configuring automatic midi connection
- midi bluetooth setup

If you have problems with connecting your PC to RPI try to add 

    DisablePlugins = pnat
To */etc/bluetooth/main.conf* file. You will have to restart RPI after making this change.

If you still have problems with connecting your Windows tablet/pc try to install Blueman, graphical bluetooth manager

    sudo apt-get install blueman

## Running Visualizer
Install [Raspbian](https://www.raspberrypi.org/documentation/installation/installing-images/) on you Raspberry Pi.
Download or clone this repository into your RPI.
Using [PIP](https://pypi.org/project/pip/) install all libraries listed in [requirements.txt](https://github.com/onlaj/Piano-LED-Visualizer/blob/master/requirements.txt "requirements.txt") file
Run visualizer.py with command

> sudo -E python visualizer.py


## Learning to play with Synthesia
As of today Synthesia doesn't support MIDI via Bluetooth, it should be added in next update. There is official workaround, you have to replace dll file.
[Instruction](http://www.synthesiagame.com/forum/viewtopic.php?f=6&t=8798&p=46920&hilit=bluetooth&sid=0ea574c5b0eaa07d4cedaeacc7b6b64b#p46920)
You also have to enable light support in Synthesia.
In Visualizer settings you have to change "input" to RPI Bluetooth. After that when learning new song next-to-play keys will be illuminated in corresponding colors, blue for left hand and green for right hand.
***

## Putting everything together
After connecting all cables as described above everything should fit nicely to case.
If you don't have a 3d printer (like me) try to find some company or private person who will print it for you. I paid 12USD for my print.

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

The "next_step" value decide if next step is activated when you press or release the pedal. For example if you want to change settings after fully pressing Sostenuto pedal you should write it like:

    <control_number>66</control_number> 
    <next_step>126</next_step>
   127 is the maximum value when pedal is fully pressed, so you are saying to script to change settings when value is bigger than 126.
This is how it should look when you want to change settings when fully releasing pedal.

      <control_number>66</control_number> 
	  <next_step>-1</next_step>

 (-) before the number means that next step will be activated when pedal value is below 1

You can also use sequences as a way to save your presets under custom names.





![Image](https://i.imgur.com/9MgNUl5.jpg?1)
![Image](https://i.imgur.com/WGxGdNM.jpg?2)
![enter image description here](https://i.imgur.com/J1wA1rU.jpg)
![Image](https://i.imgur.com/5riJs9k.jpg?1)
![Image](https://i.imgur.com/LLzeff2.jpg?1)
![Image](https://i.imgur.com/ZnYBxTp.jpg)
![Image](https://i.imgur.com/FVWnBv1.jpg?2)
![Image](https://i.imgur.com/e97ilNU.jpg?1)
