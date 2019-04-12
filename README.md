# Piano LED Visualizer

## [![contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat)](https://github.com/onlaj)

[![Everything Is AWESOME](https://i.imgur.com/xpfZ0Z6.png)](https://www.youtube.com/watch?v=IZgYViHcXdM "Piano LED Visualizer")

# What you need:

  - Piano with MIDI or USB output
  - MIDI to USB interface (if your piano doesn't have USB output) (*[example](https://www.iconnectivity.com/products/midi/mio)*)
  - Raspberry Pi Zero
  - WS2812B LED Strip (*at least 1.5m with 144 diodes/meter*) ([example](https://www.aliexpress.com/item/DC5V-WS2812B-1m-4m-5m-30-60-74-96-144-pixels-leds-m-Smart-led-pixel/32832420003.html?spm=a2g0s.9042311.0.0.25234c4dKeOOfi))
  - Power Supply (*5V 6A is enough to light 172 LEDs @50% power*) ([example](https://www.aliexpress.com/item/LED-Power-Supply-Adapter-DC5V-DC12V-DC24V-1A-2A-3A-5A-7A-8A-10A-For-led/32846184926.html?spm=a2g0s.9042311.0.0.25234c4dKeOOfi))
  - Waveshare LCD TFT 1,44'' 128x128px ([example](https://www.aliexpress.com/item/Waveshare-1-44-inch-LCD-Display-HAT-for-Raspberry-Pi-2B-3B-3B-Zero-Zero-W/32844614289.html?spm=a2g17.10010108.1000001.12.5f23ca02bab3rn))
  - Some wires

**Not required but worth to have to make everything look neat:**

  - Custom 3d printed case (*I attached STL file with modified 3d model, there is additional space and holes for power socket and wires, [here](https://www.thingiverse.com/thing:3393553) is original model*)
  - DC 5.5x2.5mm socket with quick connection ([example](https://www.aliexpress.com/item/10PCS-dc-5-5-2-5MM-power-jack-socket-connector-5-5X2-5MM-FEMALE-PLUG-solderless/32900110313.html?spm=2114.search0104.3.1.30c64a6718uG3M&ws_ab_test=searchweb0_0,searchweb201602_9_10065_10068_10843_319_10059_10884_317_10887_10696_321_322_453_10084_454_10083_10103_10618_10304_10307_10820_10301_10821_537_536,searchweb201603_51,ppcSwitch_0&algo_expid=583fe5eb-d9b9-4772-8074-779dcf3f74c9-0&algo_pvid=583fe5eb-d9b9-4772-8074-779dcf3f74c9&transAbTest=ae803_5))
  - Braid for cables
  - Heat shrink bands
  - Aluminium LED Profile with diffuser (*highly recommend to search for right one in local shops*)
  - Double side tape to mount everything on piano
  - Windows 10 laptop/tablet with bluetooth to run Synthesia

**Total cost (excluding piano and tablet) should be 75-100 USD**
***

## Connecting LED Strip to Raspberry Pi
There is no point to reinvent the wheel again, here is a nice [tutorial](https://tutorials-raspberrypi.com/connect-control-raspberry-pi-ws2812-rgb-led-strips/)

## Setting Raspberry Pi as Bluetooth MIDI host
Same as above, here is [instruction](https://neuma.studio/rpi-as-midi-host.html)

## Learning to play with Synthesia
As of today Synthesia doesn't support MIDI via Bluetooth, it should be added in next update. There is official workaround, you have to replace dll file.
[Instruction](http://www.synthesiagame.com/forum/viewtopic.php?f=6&t=8798&p=46920&hilit=bluetooth&sid=0ea574c5b0eaa07d4cedaeacc7b6b64b#p46920)
You also have to enable light support in Synthesia.
In Visualizer settings you have to change "input" to RPI Bluetooth. After that when learning new song next-to-play keys will be illuminated in corresponding colors, blue for left hand and green for right hand.
***

## Putting everything together
After connecting all cables as described above everything should fit nicely to case.
If you don't have a 3d printer (like me) try to find some company or private person who will print it for you. I payed 12USD for my print.


![Image](https://i.imgur.com/9MgNUl5.jpg?1)
![Image](https://i.imgur.com/WGxGdNM.jpg?2)
![Image](https://i.imgur.com/5riJs9k.jpg?1)
![Image](https://i.imgur.com/LLzeff2.jpg?1)
![Image](https://i.imgur.com/ZnYBxTp.jpg)
![Image](https://i.imgur.com/FVWnBv1.jpg?2)
![Image](https://i.imgur.com/e97ilNU.jpg?1)
