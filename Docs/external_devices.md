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

## Visualizer port setup

After the hardware/network connection is in place:

1. Open **Ports Settings** in the Visualizer.
2. Set **Piano Port** to your digital piano.
3. Set **Computer Port** to the RTP / USB-USB / Bluetooth / Android MIDI peer.
4. Choose **MIDI Mode**:
   - **Light show** - piano keys light the LEDs; computer traffic is ignored.
   - **Learning** - piano ↔ computer link in software, with the computer's key lights split off to the LEDs. See below.

You can also toggle MIDI Mode from the web sidebar button or with hardware **KEY3**.

No Connect/Disconnect ports step is required. The Visualizer reconnects the piano/computer ports automatically when a device is plugged back in.

## How Learning mode routes messages

Synthesia (and similar teaching apps) send two independent streams down the same
port, so the Visualizer keeps them apart:

| Stream | Messages | Goes to |
| --- | --- | --- |
| Key lights | `note_on` velocity 1 turns a guide on, `note_off` turns it off | LEDs only |
| Sound | `note_on` velocity > 1 starts a note, `note_on` velocity 0 ends it | Piano only |

On a guide-on note, channel 1-12 selects the hand/finger color (1-5 and 11 are
left hand, 6-10 and 12 are right hand).

Two details follow from this split:

- A `note_off` from the computer for a note whose guide is currently lit belongs
  to the key-light stream and is never forwarded to the piano. The light stream
  lags the sound stream, so forwarding it used to cut repeated notes short in
  Watch and Listen ([issue #618](https://github.com/onlaj/Piano-LED-Visualizer/issues/618)).
  If only some notes of a chord are pressed, Synthesia still sends `note_off`
  for those notes; every guide LED stays on until the whole chord is released
  together. In Watch and Listen there is no player press, so a `note_off` for
  one guide turns that LED off even if other guides stay lit. Software that
  sends no key lights at all is unaffected: with no guide lit, its `note_off`
  is forwarded normally.
- A `note_on` from the computer for a key you are physically holding is your own
  playing coming back, so it is dropped instead of retriggering the note.

Piano notes are always forwarded to the computer. Control changes and program
changes from the computer are blocked by default (see **Block control and
program changes** in Ports Settings); All Notes Off still clears the LEDs and
releases anything the Visualizer started on the piano.
