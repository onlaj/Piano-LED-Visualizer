import webcolors as wc
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
from neopixel import *
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
    except:
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
args = parser.parse_args()

print(args)

if not args.skipupdate:
    # make sure connectall.py file exists and is updated
    if not os.path.exists('/usr/local/bin/connectall.py') or \
        filecmp.cmp('/usr/local/bin/connectall.py', 'connectall.py') is not True:
        print("connectall.py script is outdated, updating...")
        copyfile('connectall.py', '/usr/local/bin/connectall.py')
        os.chmod('/usr/local/bin/connectall.py', 493)

KEYRIGHT = 26
KEYLEFT = 5
KEYUP = 6
KEYDOWN = 19
KEY1 = 21
KEY2 = 20
KEY3 = 16
JPRESS = 13
BACKLIGHT = 24
# pin numbers are interpreted as BCM pin numbers.
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
menu = MenuLCD("menu.xml", args, usersettings, ledsettings, ledstrip, learning, saving, midiports)

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
    #webinterface.run(use_reloader=False, debug=False, port=80, host='0.0.0.0')
    serve(webinterface, host='0.0.0.0', port=args.port)

if args.webinterface != "false":
    print ("Starting webinterface")
    processThread = threading.Thread(target=start_webserver, daemon=True)
    processThread.start()

while True:
    # screensaver
    if int(menu.screensaver_delay) > 0:
        if (time.time() - midiports.last_activity) > (int(menu.screensaver_delay) * 60):
            screensaver(menu, midiports, saving, ledstrip, ledsettings)
    try:
        elapsed_time = time.time() - saving.start_time
    except:
        elapsed_time = 0
    if display_cycle >= 3:
        display_cycle = 0

        if elapsed_time > screen_hold_time:
            menu.show()
            timeshift_start = time.time()
    display_cycle += 1

    if (time.time() - midiports.last_activity) > 1:
        usersettings.save_changes()
        if usersettings.pending_reset:
            usersettings.pending_reset = False
            ledstrip = LedStrip(usersettings, ledsettings)
            menu = MenuLCD("menu.xml", args, usersettings, ledsettings, ledstrip, learning, saving, midiports)
            menu.show()
            ledsettings = LedSettings(usersettings)

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

    red = ledsettings.get_color("Red")
    green = ledsettings.get_color("Green")
    blue = ledsettings.get_color("Blue")

    timeshift = (time.time() - timeshift_start) * ledsettings.rainbow_timeshift

    if ledsettings.mode == "Fading" or ledsettings.mode == "Velocity":
        n = 0
        for note in ledstrip.keylist:
            if ledsettings.color_mode == "Multicolor":
                try:
                    red = ledstrip.keylist_color[n][0]
                    green = ledstrip.keylist_color[n][1]
                    blue = ledstrip.keylist_color[n][2]
                except:
                    pass

            if int(note) > 0:
                if ledsettings.color_mode == "Rainbow":
                    red = get_rainbow_colors(int((int(n) + ledsettings.rainbow_offset + int(timeshift)) * (
                            float(ledsettings.rainbow_scale) / 100)) & 255, "red")
                    green = get_rainbow_colors(int((int(n) + ledsettings.rainbow_offset + int(timeshift)) * (
                            float(ledsettings.rainbow_scale) / 100)) & 255, "green")
                    blue = get_rainbow_colors(int((int(n) + ledsettings.rainbow_offset + int(timeshift)) * (
                            float(ledsettings.rainbow_scale) / 100)) & 255, "blue")

                    if int(note) == 1001:
                        ledstrip.strip.setPixelColor(n, Color(int(green), int(red), int(blue)))
                        ledstrip.set_adjacent_colors(n, Color(int(green), int(red), int(blue)), False)

                if ledsettings.color_mode == "Speed":
                    speed_colors = ledsettings.speed_get_colors()
                    red = speed_colors[0]
                    green = speed_colors[1]
                    blue = speed_colors[2]

                if ledsettings.color_mode == "Gradient":
                    gradient_colors = ledsettings.gradient_get_colors(n)
                    red = gradient_colors[0]
                    green = gradient_colors[1]
                    blue = gradient_colors[2]

                if ledsettings.color_mode == "Scale":
                    try:
                        red = ledstrip.keylist_color[n][0]
                        green = ledstrip.keylist_color[n][1]
                        blue = ledstrip.keylist_color[n][2]
                    except:
                        pass

            if int(note) != 1001:
                if int(note) > 0:
                    fading = (note / float(100)) / 10
                    ledstrip.strip.setPixelColor(n, Color(int(int(green) * fading), int(int(red) * fading),
                                                          int(int(blue) * fading)))
                    ledstrip.set_adjacent_colors(n, Color(int(int(green) * fading), int(int(red) * fading),
                                                          int(int(blue) * fading)), False)
                    ledstrip.keylist[n] = ledstrip.keylist[n] - ledsettings.fadingspeed
                    if ledstrip.keylist[n] <= 0:
                        red_fading = int(ledsettings.get_backlight_color("Red")) * float(
                            ledsettings.backlight_brightness_percent) / 100
                        green_fading = int(ledsettings.get_backlight_color("Green")) * float(
                            ledsettings.backlight_brightness_percent) / 100
                        blue_fading = int(ledsettings.get_backlight_color("Blue")) * float(
                            ledsettings.backlight_brightness_percent) / 100
                        color = Color(int(green_fading), int(red_fading), int(blue_fading))
                        ledstrip.strip.setPixelColor(n, color)
                        ledstrip.set_adjacent_colors(n, color, False)
                else:
                    ledstrip.keylist[n] = 0

            if ledsettings.mode == "Velocity":
                if int(last_control_change) < pedal_deadzone:
                    if int(ledstrip.keylist_status[n]) == 0:
                        red_fading = int(ledsettings.get_backlight_color("Red")) * float(
                            ledsettings.backlight_brightness_percent) / 100
                        green_fading = int(ledsettings.get_backlight_color("Green")) * float(
                            ledsettings.backlight_brightness_percent) / 100
                        blue_fading = int(ledsettings.get_backlight_color("Blue")) * float(
                            ledsettings.backlight_brightness_percent) / 100
                        color = Color(int(green_fading), int(red_fading), int(blue_fading))
                        ledstrip.strip.setPixelColor(n, color)
                        ledstrip.set_adjacent_colors(n, color, False)
                        ledstrip.keylist[n] = 0
            n += 1
    try:
        if len(saving.is_playing_midi) == 0 and learning.is_started_midi is False:
            midiports.midipending = midiports.inport.iter_pending()
        else:
            midiports.midipending = midiports.pending_queue
    except:
        continue
    # loop through incoming midi messages
    for msg in midiports.midipending:
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
                except:
                    pass

        # changing offset to adjust the distance between the LEDs to the key spacing
        note_position = get_note_position(note, ledstrip, ledsettings)

        if (note_position > ledstrip.led_number or note_position < 0) and control_change is False:
            continue

        elapsed_time = time.time() - saving.start_time

        if ledsettings.color_mode == "Rainbow":
            red = get_rainbow_colors(int((int(note_position) + ledsettings.rainbow_offset + int(timeshift)) * (
                    float(ledsettings.rainbow_scale) / 100)) & 255, "red")
            green = get_rainbow_colors(int((int(note_position) + ledsettings.rainbow_offset + int(timeshift)) * (
                    float(ledsettings.rainbow_scale) / 100)) & 255, "green")
            blue = get_rainbow_colors(int((int(note_position) + ledsettings.rainbow_offset + int(timeshift)) * (
                    float(ledsettings.rainbow_scale) / 100)) & 255, "blue")

        if ledsettings.color_mode == "Speed":
            speed_colors = ledsettings.speed_get_colors()
            red = speed_colors[0]
            green = speed_colors[1]
            blue = speed_colors[2]

        if ledsettings.color_mode == "Gradient":
            gradient_colors = ledsettings.gradient_get_colors(note_position)
            red = gradient_colors[0]
            green = gradient_colors[1]
            blue = gradient_colors[2]

        if ledsettings.color_mode == "Scale":
            scale_colors = get_scale_color(ledsettings.scale_key, note, ledsettings)
            red = scale_colors[0]
            green = scale_colors[1]
            blue = scale_colors[2]
            ledstrip.keylist_color[note_position] = scale_colors

        if int(velocity) == 0 and int(note) > 0 and ledsettings.mode != "Disabled":  # when a note is lifted (off)
            ledstrip.keylist_status[note_position] = 0
            if ledsettings.mode == "Fading":
                ledstrip.keylist[note_position] = 1000
            elif ledsettings.mode == "Velocity":
                if int(last_control_change) < pedal_deadzone:
                    ledstrip.keylist[note_position] = 0
            else:
                if ledsettings.backlight_brightness > 0:
                    red_backlight = int(
                        ledsettings.get_backlight_color("Red")) * ledsettings.backlight_brightness_percent / 100
                    green_backlight = int(
                        ledsettings.get_backlight_color("Green")) * ledsettings.backlight_brightness_percent / 100
                    blue_backlight = int(
                        ledsettings.get_backlight_color("Blue")) * ledsettings.backlight_brightness_percent / 100
                    color_backlight = Color(int(green_backlight), int(red_backlight), int(blue_backlight))
                    ledstrip.strip.setPixelColor(note_position, color_backlight)
                    ledstrip.set_adjacent_colors(note_position, color_backlight, True)
                else:
                    ledstrip.strip.setPixelColor(note_position, Color(0, 0, 0))
                    ledstrip.set_adjacent_colors(note_position, Color(0, 0, 0), False)
            if saving.isrecording:
                saving.add_track("note_off", original_note, velocity, midiports.last_activity)
        elif int(velocity) > 0 and int(note) > 0 and ledsettings.mode != "Disabled":  # when a note is pressed
            ledsettings.speed_add_note()
            if ledsettings.color_mode == "Multicolor":
                choosen_color = ledsettings.get_random_multicolor_in_range(note)
                red = choosen_color[0]
                green = choosen_color[1]
                blue = choosen_color[2]
                ledstrip.keylist_color[note_position] = [red, green, blue]

            ledstrip.keylist_status[note_position] = 1
            if ledsettings.mode == "Velocity":
                brightness = (100 / (float(velocity) / 127)) / 100
            else:
                brightness = 1
            if ledsettings.mode == "Fading":
                ledstrip.keylist[note_position] = 1001
            if ledsettings.mode == "Velocity":
                ledstrip.keylist[note_position] = 1000 / float(brightness)
            if find_between(str(msg), "channel=", " ") == "12":
                if ledsettings.skipped_notes != "Finger-based":
                    red = int(learning.hand_colorList[learning.hand_colorR][0])
                    green = int(learning.hand_colorList[learning.hand_colorR][1])
                    blue = int(learning.hand_colorList[learning.hand_colorR][2])
                    s_color = Color(green, red, blue)
                    ledstrip.strip.setPixelColor(note_position, s_color)
                    ledstrip.set_adjacent_colors(note_position, s_color, False)
            elif find_between(str(msg), "channel=", " ") == "11":
                if ledsettings.skipped_notes != "Finger-based":
                    red = int(learning.hand_colorList[learning.hand_colorL][0])
                    green = int(learning.hand_colorList[learning.hand_colorL][1])
                    blue = int(learning.hand_colorList[learning.hand_colorL][2])
                    s_color = Color(green, red, blue)
                    ledstrip.strip.setPixelColor(note_position, s_color)
                    ledstrip.set_adjacent_colors(note_position, s_color, False)
            else:
                if ledsettings.skipped_notes != "Normal":
                    s_color = Color(int(int(green) / float(brightness)), int(int(red) / float(brightness)),
                                   int(int(blue) / float(brightness)))
                    ledstrip.strip.setPixelColor(note_position, s_color)
                    ledstrip.set_adjacent_colors(note_position, s_color, False)
            if saving.isrecording:
                if ledsettings.color_mode == "Multicolor":
                    saving.add_track("note_on", original_note, velocity, midiports.last_activity,
                                     wc.rgb_to_hex((red, green, blue)))
                else:
                    saving.add_track("note_on", original_note, velocity, midiports.last_activity)
        else:
            control = find_between(str(msg), "control=", " ")
            value = find_between(str(msg), "value=", " ")
            if saving.isrecording:
                saving.add_control_change("control_change", 0, control, value, midiports.last_activity)
        saving.restart_time()
        if len(saving.is_playing_midi) > 0:
            midiports.pending_queue.remove(msg)
    ledstrip.strip.show()
