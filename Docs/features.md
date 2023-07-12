# Features

1. [Led settings](#ledsettings)
    1. [Color modes](#color_modes)
    2. [Light modes](#light_modes)
    3. [Other settings](#other_settings)
2. [Songs](#songs)
    1. [Recording](#recording)
    1. [Playing](#playing)
    1. [Managing songs](#managing_songs)
3. [Sequences](#sequences)
4. [Led animations](#led_animations)

# Led settings <a name="ledsettings"></a>

Each setting can be changed from the web interface or RPi's screen.

## Color modes <a name="color_modes"></a>

- ### **Single**

  ![learnmidi_pic](https://i.imgur.com/1CmdUSC.png)

- ### **Multicolor**

  You can define color and range. Keys without a defined range will create a gradient from the surrounding colors.

  ![learnmidi_pic](https://i.imgur.com/NOgFYoD.png)

  ![learnmidi_pic](https://i.imgur.com/fd0OVlf.png)

- ### **Rainbow**

  Creates a rainbow effect. You can edit the scale of rainbow and make it change in time (move left or right).

  ![learnmidi_pic](https://i.imgur.com/JBthTuW.png)

- ### **Velocity Rainbow**

  Color is based on the speed at which a key is pressed.- 

  [Credits to](https://github.com/onlaj/Piano-LED-Visualizer/pull/454) [@stephen322](https://github.com/stephen322)

  ![learnmidi_pic](https://imgur.com/b65QO45.jpg)

- ### **Speed**

  The color of the LEDs depends on the speed at which the keys are pressed.

  ![learnmidi_pic](https://i.imgur.com/QRHHuwI.png)

- ### **Gradient**

  ![learnmidi_pic](https://i.imgur.com/hJeAqK6.png)

- ### **Scale**

  Color depends on scale; in the example below, it lights black keys with a red color.

  ![learnmidi_pic](https://i.imgur.com/hQxsUvP.png)

## Light modes <a name="light_modes"></a>

There are 3 modes


- ### Normal    
- ### Fading

    When the key is released, it slowly turns off the LED.
- ### Velocity
    The faster (with more velocity) you press the key, the brighter the led will light up. It will also slowly fade
    when the key is released AND the sustain pedal is pressed. If the sustain pedal is not pressed, the fading effect is not present.

## Other settings <a name="other_settings"></a>

- ### Brightness
- ### Backlight
    It lights up all the keys when they are not pressed.
- ### Sides colors
    Light up 3 LEDs instead of 1. Adjacent LEDs can be set to a separate color.
- ### Skipped notes
    Allows to filter notes with left/right hand information. Useful when Synthesia is doubling the input
- ### Led count
    For keyboards with less than 88 keys
- ### Shift
    Helps align the LED strip
- ### Reverse
    For setups with led strip mounted from right to left (input cables on right)
- ### LED notes offset
    By default, it offsets LEDs by 1 for notes bigger than 55 and by 1 for notes bigger than 92.
    Can be modified if LEDs are not aligned with keys.

# Recording/playing songs <a name="songs"></a>

## Recording <a name="recording"></a>

  Visualizer can record your playing. When Multicolor mode is selected, it will record each color on separate midi file.
  Songs are saved into the "Songs" folder, they can be downloaded using the Web interface.
  
  ![learnmidi_pic](https://i.imgur.com/jAcR3kT.png)
 
## Playing <a name="playing"></a>

  Songs can be played directly in the Web interface or through your piano.
  When playing in the browser, it also displays simple falling note visualisation.

  ![learnmidi_pic](https://i.imgur.com/izbDAYb.png)


## Learning <a name="playing"></a>

  Visualizer comes with a built-in learning tool.
  You can load any midi file, and it will light up the next-to-play key.
  In the Web interface it will also show sheet music. Conversion is automatic and far from perfect,
  so if it doesn't suit your needs you can load your custom sheet.

  ![learnmidi_pic](https://i.imgur.com/zEBs4Gj.png)

## Managing songs <a name="managing_songs"></a>

You can search, sort, edit names, play, start learning, download, and delete songs through Web interface.

![learnmidi_pic](https://i.imgur.com/X3RAPPE.png)

## Uploading 
You can upload songs through the Web interface

![learnmidi_pic](https://i.imgur.com/3QxBxgB.png)


# Sequences <a name="sequences"></a>

## Using the sequences
In the visualizer menu and in the web interface you can find a setting called "Sequences". 
It allows you to change led properties while playing using the third key on Waveshare hat, your piano pedals,
or by clicking "next step"/pressing space in the Web interface.
You can edit or create new sequences by editing the "sequences.xml" file or through Web interface.
The "control_number" defines which pedal is used to go to the next step.

|Control number| Pedal name |
|--|--|
| 64 | Damper Pedal (Sustain/Hold) On/Off  |
| 65 | Portamento On/Off |
| 66 | Sostenuto On/Off |
| 67 | Soft Pedal On/Off |

The "next_step" value decides if next step is activated when you press or release the pedal. For example, if you want to change settings after fully pressing Sostenuto pedal you should write it like:

    <control_number>66</control_number> 
    <next_step>126</next_step>
   127 is the maximum value when pedal is fully pressed, so you are saying to script to change settings when value is bigger than 126.
This is how it should look when you want to change settings when fully releasing pedal.

      <control_number>66</control_number> 
	  <next_step>-1</next_step>

 (-) before the number means that next step will be activated when pedal value is below 1.

You can also use sequences as a way to save your presets under custom names.

![learnmidi_pic](https://i.imgur.com/iDedXym.png)
![learnmidi_pic](https://i.imgur.com/1FT1zXJ.png)


# Led animations <a name="led_animations"></a>

You can start some simple led strip animations. They can also be set to run automatically when the Visualizer is idling.

![learnmidi_pic](https://i.imgur.com/gybF01Y.png)