import webcolors as wc
import colorsys
import sys
import os
import fcntl

from lib.learnmidi import LearnMIDI
from lib.ledsettings import LedSettings
from lib.ledstrip import LedStrip
from lib.menulcd import MenuLCD
from lib.midiports import MidiPorts
from lib.savemidi import SaveMIDI
from lib.usersettings import UserSettings
from lib.functions import *
from lib.neopixel import *
from lib.color_mode import *
import argparse
import threading
from webinterface import webinterface
import filecmp
from shutil import copyfile
from waitress import serve

os.chdir(sys.path[0])

# Ensure there is only one instance of the script running.
fh = 0


def singleton():
    global fh
    fh = open(os.path.realpath(__file__), 'r')
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception as error:
        print(f"Unexpected exception occurred: {error}")
        restart_script()


def restart_script():
    python = sys.executable
    os.execl(python, python, *sys.argv)


singleton()

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
parser.add_argument('-d', '--display', type=str, help="choose type of display: '1in44' (default) | '1in3'")
parser.add_argument('-f', '--fontdir', type=str, help="Use an alternate directory for fonts")
parser.add_argument('-p', '--port', type=int, help="set port for webinterface (80 is default)")
parser.add_argument('-s', '--skipupdate', action='store_true', help="Do not try to update /usr/local/bin/connectall.py")
parser.add_argument('-w', '--webinterface', help="disable webinterface: 'true' (default) | 'false'")
parser.add_argument('-r', '--rotatescreen', default="false", help="rotate screen: 'false' (default) | 'true'")
args = parser.parse_args()

print(args)

if not args.skipupdate:
    # make sure connectall.py file exists and is updated
    if not os.path.exists('/usr/local/bin/connectall.py') or \
            filecmp.cmp('/usr/local/bin/connectall.py', 'lib/connectall.py') is not True:
        print("connectall.py script is outdated, updating...")
        copyfile('lib/connectall.py', '/usr/local/bin/connectall.py')
        os.chmod('/usr/local/bin/connectall.py', 493)

if args.rotatescreen != "true":
    KEYRIGHT = 26
    KEYLEFT = 5
    KEYUP = 6
    KEYDOWN = 19
    KEY1 = 21
    KEY3 = 16
else:
    KEYRIGHT = 5
    KEYLEFT = 26
    KEYUP = 19
    KEYDOWN = 6
    KEY1 = 16
    KEY3 = 21

KEY2 = 20
JPRESS = 13
BACKLIGHT = 24
# pins are interpreted as BCM pins.
GPIO.setmode(GPIO.BCM)
# Sets the pin as input and sets Pull-up mode for the pin.
GPIO.setup(KEYRIGHT, GPIO.IN, GPIO.PUD_UP)
GPIO.setup(KEYLEFT, GPIO.IN, GPIO.PUD_UP)
GPIO.setup(KEYUP, GPIO.IN, GPIO.PUD_UP)
GPIO.setup(KEYDOWN, GPIO.IN, GPIO.PUD_UP)
GPIO.setup(KEY1, GPIO.IN, GPIO.PUD_UP)
GPIO.setup(KEY2, GPIO.IN, GPIO.PUD_UP)
GPIO.setup(KEY3, GPIO.IN, GPIO.PUD_UP)
GPIO.setup(JPRESS, GPIO.IN, GPIO.PUD_UP)

usersettings = UserSettings()
midiports = MidiPorts(usersettings)
ledsettings = LedSettings(usersettings)
ledstrip = LedStrip(usersettings, ledsettings)
learning = LearnMIDI(usersettings, ledsettings, midiports, ledstrip)
saving = SaveMIDI()
menu = MenuLCD("config/menu.xml", args, usersettings, ledsettings, ledstrip, learning, saving, midiports)

midiports.add_instance(menu)
ledsettings.add_instance(menu, ledstrip)
saving.add_instance(menu)
learning.add_instance(menu)

menu.show()
z = 0
display_cycle = 0
screen_hold_time = 16

midiports.last_activity = time.time()

last_control_change = 0
pedal_deadzone = 10
timeshift_start = time.time()
timeshift = 0
ledshow_timestamp = time.time()
color_mode_name = ""

fastColorWipe(ledstrip.strip, True, ledsettings)


def start_webserver():
    if not args.port:
        args.port = 80

    webinterface.usersettings = usersettings
    webinterface.ledsettings = ledsettings
    webinterface.ledstrip = ledstrip
    webinterface.learning = learning
    webinterface.saving = saving
    webinterface.midiports = midiports
    webinterface.menu = menu
    webinterface.jinja_env.auto_reload = True
    webinterface.config['TEMPLATES_AUTO_RELOAD'] = True
    # webinterface.run(use_reloader=False, debug=False, port=80, host='0.0.0.0')
    serve(webinterface, host='0.0.0.0', port=args.port, threads=20)


if args.webinterface != "false":
    print("Starting webinterface")
    processThread = threading.Thread(target=start_webserver, daemon=True)
    processThread.start()


# Main event loop
while True:
    # screensaver
    if int(menu.screensaver_delay) > 0:
        if (time.time() - midiports.last_activity) > (int(menu.screensaver_delay) * 60):
            screensaver(menu, midiports, saving, ledstrip, ledsettings)
    try:
        elapsed_time = time.time() - saving.start_time
    except Exception as e:
        # Handle any other unexpected exceptions here
        print(f"Unexpected exception occurred: {e}")
        elapsed_time = 0


    # Show menulcd
    if display_cycle >= 3:
        display_cycle = 0

        if elapsed_time > screen_hold_time:
            menu.show()
            timeshift_start = time.time()
    display_cycle += 1


    # Create ColorMode if first-run or changed
    if ledsettings.color_mode != color_mode_name:
        color_mode = ColorMode(ledsettings.color_mode, ledsettings)
        color_mode_name = ledsettings.color_mode

    # Save settings if changed
    if (time.time() - usersettings.last_save) > 1:
        if usersettings.pending_changes:
            color_mode.LoadSettings(ledsettings)
            usersettings.save_changes()
        if usersettings.pending_reset:
            usersettings.pending_reset = False
            ledstrip = LedStrip(usersettings, ledsettings)
            menu = MenuLCD("config/menu.xml", args, usersettings, ledsettings, ledstrip, learning, saving, midiports)
            menu.show()
            ledsettings = LedSettings(usersettings)



    # Process GPIO keys
    if GPIO.input(KEYUP) == 0:
        midiports.last_activity = time.time()
        menu.change_pointer(0)
        while GPIO.input(KEYUP) == 0:
            time.sleep(0.001)
    if GPIO.input(KEYDOWN) == 0:
        midiports.last_activity = time.time()
        menu.change_pointer(1)
        while GPIO.input(KEYDOWN) == 0:
            time.sleep(0.001)
    if GPIO.input(KEY1) == 0:
        midiports.last_activity = time.time()
        menu.enter_menu()
        while GPIO.input(KEY1) == 0:
            time.sleep(0.001)
    if GPIO.input(KEY2) == 0:
        midiports.last_activity = time.time()
        menu.go_back()
        if not menu.screensaver_is_running:
            fastColorWipe(ledstrip.strip, True, ledsettings)
        while GPIO.input(KEY2) == 0:
            time.sleep(0.01)
    if GPIO.input(KEY3) == 0:
        midiports.last_activity = time.time()
        if ledsettings.sequence_active:
            ledsettings.set_sequence(0, 1)
        else:
            active_input = usersettings.get_setting_value("input_port")
            secondary_input = usersettings.get_setting_value("secondary_input_port")
            midiports.change_port("inport", secondary_input)
            usersettings.change_setting_value("secondary_input_port", active_input)
            usersettings.change_setting_value("input_port", secondary_input)
            fastColorWipe(ledstrip.strip, True, ledsettings)

        while GPIO.input(KEY3) == 0:
            time.sleep(0.01)
    if GPIO.input(KEYLEFT) == 0:
        midiports.last_activity = time.time()
        menu.change_value("LEFT")
        time.sleep(0.1)
    if GPIO.input(KEYRIGHT) == 0:
        midiports.last_activity = time.time()
        menu.change_value("RIGHT")
        time.sleep(0.1)
    if GPIO.input(JPRESS) == 0:
        midiports.last_activity = time.time()
        menu.speed_change()
        while GPIO.input(JPRESS) == 0:
            time.sleep(0.01)



    # Rainbow timeshift calculation
    timeshift = (time.time() - timeshift_start) * ledsettings.rainbow_timeshift


    # Fade processing
    for n, strength in enumerate(ledstrip.keylist):
        # Restore led colors
        try:
            if type(ledstrip.keylist_color[n]) is list:
                red = ledstrip.keylist_color[n][0]
                green = ledstrip.keylist_color[n][1]
                blue = ledstrip.keylist_color[n][2]
            else:
                red, green, blue = (0, 0, 0)
        except Exception as e:
            print(f"Unexpected exception occurred: {e}")

        new_color = color_mode.ColorUpdate(time.time() - ledshow_timestamp, n, Color(red,green,blue))
        if new_color is not None:
            red, green, blue = ColorInt2RGB(new_color)

        if ledsettings.mode == "Normal":
            # color_mode Rainbow needs update because of timeshift
            if ledstrip.keylist_status[n] == 1:
                if ledsettings.color_mode == "Rainbow":
                    red, green, blue = calculate_rainbow_colors(ledsettings, n, timeshift)
                    ledstrip.strip.setPixelColor(n, Color(int(green), int(red), int(blue)))
                    ledstrip.set_adjacent_colors(n, Color(int(green), int(red), int(blue)), False)

        elif ledsettings.mode == "Fading" or ledsettings.mode == "Velocity":
            if int(strength) > 0:
                if ledsettings.color_mode == "Rainbow":
                    red, green, blue = calculate_rainbow_colors(ledsettings, n, timeshift)

                    if int(strength) == 1001:
                        ledstrip.strip.setPixelColor(n, Color(int(green), int(red), int(blue)))
                        ledstrip.set_adjacent_colors(n, Color(int(green), int(red), int(blue)), False)

                if ledsettings.color_mode == "Speed":
                    red, green, blue = calculate_speed_colors(ledsettings)

                if ledsettings.color_mode == "Gradient":
                    red, green, blue = calculate_gradient_colors(ledsettings, n)


            if ledsettings.mode == "Velocity":
                # If sustain pedal is off and note is off, turn of fade processing
                if int(last_control_change) < pedal_deadzone and ledstrip.keylist_status[n] == 0:
                    ledstrip.keylist[n] = 0

            if ledstrip.keylist_status[n] == 0 or ledsettings.mode == "Velocity":
                if int(strength) > 0:
                    fading = (strength / float(100)) / 10
                    ledstrip.strip.setPixelColor(n, Color(int(int(green) * fading), int(int(red) * fading),
                                                          int(int(blue) * fading)))
                    ledstrip.set_adjacent_colors(n, Color(int(int(green) * fading), int(int(red) * fading),
                                                          int(int(blue) * fading)), False, fading)
                    ledstrip.keylist[n] = ledstrip.keylist[n] - ledsettings.fadingspeed
                    if ledstrip.keylist[n] <= 0 and menu.screensaver_is_running is not True:
                        red_fading = int(ledsettings.get_backlight_color("Red")) * float(
                            ledsettings.backlight_brightness_percent) / 100
                        green_fading = int(ledsettings.get_backlight_color("Green")) * float(
                            ledsettings.backlight_brightness_percent) / 100
                        blue_fading = int(ledsettings.get_backlight_color("Blue")) * float(
                            ledsettings.backlight_brightness_percent) / 100
                        color = Color(int(green_fading), int(red_fading), int(blue_fading))
                        ledstrip.strip.setPixelColor(n, color)
                        ledstrip.set_adjacent_colors(n, color, False, fading)
                else:
                    ledstrip.keylist[n] = 0




    # Prep midi event queue
    try:
        if len(saving.is_playing_midi) == 0 and learning.is_started_midi is False:
            midiports.midipending = midiports.inport.iter_pending()
        else:
            midiports.midipending = midiports.pending_queue
    except Exception as e:
        print(f"Unexpected exception occurred: {e}")

    # loop through incoming midi messages
    for msg in midiports.midipending:
        if int(usersettings.get_setting_value("midi_logging")) == 1:
            if not msg.is_meta:
                try:
                    learning.socket_send.append("midi_event" + str(msg))
                except Exception as e:
                    print(e)

        midiports.last_activity = time.time()
        note = find_between(str(msg), "note=", " ")
        original_note = note
        note = int(note)
        if "note_off" in str(msg):
            velocity = 0
        else:
            velocity = find_between(str(msg), "velocity=", " ")

        control_change = find_between(str(msg), "value=", " ")
        if control_change:
            last_control_change = control_change

            if ledsettings.sequence_active:

                control = find_between(str(msg), "control=", " ")
                value = find_between(str(msg), "value=", " ")
                try:
                    if "+" in ledsettings.next_step:
                        if int(value) > int(ledsettings.next_step) and control == ledsettings.control_number:
                            ledsettings.set_sequence(0, 1)
                    else:
                        if int(value) < int(ledsettings.next_step) and control == ledsettings.control_number:
                            ledsettings.set_sequence(0, 1)
                except Exception as e:
                    print(f"Unexpected exception occurred: {e}")

        # changing offset to adjust the distance between the LEDs to the key spacing
        note_position = get_note_position(note, ledstrip, ledsettings)

        if (note_position >= ledstrip.led_number or note_position < 0) and control_change is False:
            continue

        elapsed_time = time.time() - saving.start_time



        if int(velocity) == 0 and int(note) > 0 and ledsettings.mode != "Disabled":  # when a note is lifted (off)
            ledstrip.keylist_status[note_position] = 0
            if ledsettings.mode == "Fading":
                ledstrip.keylist[note_position] = 1000
            else:
                if ledsettings.backlight_brightness > 0 and menu.screensaver_is_running is not True:
                    red_backlight = int(
                        ledsettings.get_backlight_color("Red")) * ledsettings.backlight_brightness_percent / 100
                    green_backlight = int(
                        ledsettings.get_backlight_color("Green")) * ledsettings.backlight_brightness_percent / 100
                    blue_backlight = int(
                        ledsettings.get_backlight_color("Blue")) * ledsettings.backlight_brightness_percent / 100
                    color_backlight = Color(int(green_backlight), int(red_backlight), int(blue_backlight))
                    ledstrip.strip.setPixelColor(note_position, color_backlight)
                    ledstrip.set_adjacent_colors(note_position, color_backlight, True)
                elif ledsettings.mode == "Normal":
                    ledstrip.strip.setPixelColor(note_position, Color(0, 0, 0))
                    ledstrip.set_adjacent_colors(note_position, Color(0, 0, 0), False)
            if saving.is_recording:
                saving.add_track("note_off", original_note, velocity, midiports.last_activity)
        elif int(velocity) > 0 and int(note) > 0 and ledsettings.mode != "Disabled":  # when a note is pressed
            red, green, blue = ColorInt2RGB(color_mode.NoteOn(msg, None, note_position))

            ledsettings.speed_add_note()

            if ledsettings.color_mode == "Single":
                red = ledsettings.get_color("Red")
                green = ledsettings.get_color("Green")
                blue = ledsettings.get_color("Blue")

            if ledsettings.color_mode == "Rainbow":
                red, green, blue = calculate_rainbow_colors(ledsettings, note_position, timeshift)

            if ledsettings.color_mode == "Speed":
                red, green, blue = calculate_speed_colors(ledsettings)

            if ledsettings.color_mode == "Gradient":
                red, green, blue = calculate_gradient_colors(ledsettings, note_position)

            if ledsettings.color_mode == "Scale":
                scale_colors = get_scale_color(ledsettings.scale_key, note, ledsettings)
                red = scale_colors[0]
                green = scale_colors[1]
                blue = scale_colors[2]

            if ledsettings.color_mode == "Multicolor":
                chosen_color = ledsettings.get_random_multicolor_in_range(note)
                red = chosen_color[0]
                green = chosen_color[1]
                blue = chosen_color[2]


            # Save ledstrip led colors
            ledstrip.keylist_color[note_position] = [red, green, blue]


            # Set initial fade processing state
            ledstrip.keylist_status[note_position] = 1
            if ledsettings.mode == "Velocity":
                brightness = (100 / (float(velocity) / 127)) / 100
            else:
                brightness = 1
            if ledsettings.mode == "Fading":
                ledstrip.keylist[note_position] = 1001
            if ledsettings.mode == "Velocity":
                ledstrip.keylist[note_position] = 999 / float(brightness)


            # Apply learning colors
            channel = find_between(str(msg), "channel=", " ")
            if channel == "12" or channel == "11":
                if ledsettings.skipped_notes != "Finger-based":
                    if channel == "12":
                        hand_color = learning.hand_colorR
                    else:
                        hand_color = learning.hand_colorL

                    red, green, blue = map(int, learning.hand_colorList[hand_color])
                    s_color = Color(green, red, blue)
                    ledstrip.strip.setPixelColor(note_position, s_color)
                    ledstrip.set_adjacent_colors(note_position, s_color, False)
            else:
                if ledsettings.skipped_notes != "Normal":
                    s_color = Color(int(int(green) / float(brightness)), int(int(red) / float(brightness)),
                                    int(int(blue) / float(brightness)))
                    ledstrip.strip.setPixelColor(note_position, s_color)
                    ledstrip.set_adjacent_colors(note_position, s_color, False)


            # Saving
            if saving.is_recording:
                if ledsettings.color_mode == "Multicolor":
                    saving.add_track("note_on", original_note, velocity, midiports.last_activity,
                                     wc.rgb_to_hex((red, green, blue)))
                else:
                    saving.add_track("note_on", original_note, velocity, midiports.last_activity)


        # Midi control change event
        else:
            control = find_between(str(msg), "control=", " ")
            value = find_between(str(msg), "value=", " ")
            if saving.is_recording:
                saving.add_control_change("control_change", 0, control, value, midiports.last_activity)

        color_mode.MidiEvent(msg, None, ledstrip)

        # Save event-loop update
        saving.restart_time()
        if len(saving.is_playing_midi) > 0:
            midiports.pending_queue.remove(msg)



    # Update ledstrip
    ledstrip.strip.show()
