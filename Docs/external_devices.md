## Configuration 1
### version A
![configuration 1A](https://i.imgur.com/1vFlqLs.png)

In this configuration, the piano is connected to a Raspberry Pi (with a USB OTG hub in between). 
Our PC/MAC/tablet (from now on, let's just call it the "PC") is also connected to the USB OTG hub, 
but with the Sevilla's USB-USB device in between. This setup allows us to use lights even if the PC is not connected.


### version B
![configuration 1B](https://i.imgur.com/f5xmQGt.png)

In the second configuration, the piano is connected to the PC. 
The connection between the PC and Raspberry Pi is made using the Sevilla's USB-USB. 
This connection is useful if we want minimal delays between the piano and PC, for tasks like recording or learning. 
Since it's a wired connection, differences in latency are negligible, so this configuration is not recommended. 
It also requires the PC to be turned on.

### Why do we need Sevilla's USB-USB at all? 
To transmit MIDI signals over USB, 
at least one side of the transmission must present itself as a MIDI device. 
There is an option for the Raspberry Pi to act as such a device, but then we could only connect one device. 
Instead, we can use a device that simulates MIDI, creating a bridge between two non-MIDI devices.

## Configuration 2
### version A
![configuration 2A](https://i.imgur.com/d61eT1Y.png)

If we don't have Sevilla USB-USB, we can use a wireless connection instead. 
For this, we use the RTP MIDI protocol. We connect our piano with a cable to the Raspberry Pi. 
On our PC, we configure RTP MIDI software and establish a connection between the PC and RPi.


### version B
![configuration 2B](https://i.imgur.com/DI3Cd7h.png)

Another configuration involves connecting the piano to the PC. 
The connection between the RPi and PC is through the RTP MIDI protocol. 
Similar to configuration 2B, this connection aims to minimize delays between Piano and PC. 
In the case of a wireless connection, these differences may become noticeable. 
This connection requires the PC to be turned on and the appropriate configuration of Synthesia or a 
similar program but is useful if we want no delays during learning.


## Configuration 3
![configuration 3](https://i.imgur.com/OxzG7cv.png)

The next configuration is specific to tablets or phones with the Android system. 
After selecting the 'MIDI' option, Android will act as a MIDI device, 
enabling the transmission of MIDI messages without the need for Sevilla's USB-USB.
