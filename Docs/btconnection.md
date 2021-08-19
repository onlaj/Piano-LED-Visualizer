Instruction is under 

> MIDI BLUETOOTH SETUP

on [THIS PAGE](https://neuma.studio/rpi-midi-complete.html)
 
If you have problems with connecting your PC to RPI try to add 

    DisablePlugins = pnat
to */etc/bluetooth/main.conf* file. You will have to restart RPI after making this change.

If you still have problems with connecting your Windows tablet/pc try to install Blueman, graphical bluetooth manager. 

    sudo apt-get install blueman
Of course for Raspberry Pi OS Lite you will need to install GUI first.

- Enabling BT support in Synthesia:

> First, make sure the "Midi.UseWinRtMidi" option is enabled:  
> 1.  Hold your Shift key while launching Synthesia (to open the configuration window).
> 2.  Find the "Midi.UseWinRTMidi" entry in the Setting drop-down box.
> 3.  Add a check mark to the "Value" box.

BT support on different devices:

> -   BLE MIDI on macOS: completely automatic and supported
> -   BLE MIDI on iOS: completely automatic and supported
> -   BLE MIDI on Win10: enable the "Midi.UseWinRTMidi" advanced option to try and use Microsoft's  [complete mess](https://www.synthesiagame.com/forum/viewtopic.php?p=47530#p47530) of a UWP driver.
> -   BLE MIDI on Android: if your device supports the "Android M MIDI" feature, just connect to the MIDI device using  [these instructions](https://synthesiagame.com/forum/viewtopic.php?p=47541#p47541)  and it should "work" fine, with all of Android's awful latency and dropped events
