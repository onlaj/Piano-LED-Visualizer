from subprocess import call
from xml.dom import minidom
import xml.etree.ElementTree as ET
import ast
import LCD_1in44
import LCD_1in3
import LCD_Config
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageColor
import RPi.GPIO as GPIO
import time
import random
import webcolors as wc
import sys
import os
import datetime
import psutil
import fcntl
os.chdir(sys.path[0])
import mido
from mido import MidiFile, Message, tempo2bpm, MidiTrack,MetaMessage
from neopixel import *
import argparse
import threading

# Ensure there is only one instance of the script running.
fh=0
def singleton():
    global fh
    fh=open(os.path.realpath(__file__),'r')
    try:
        fcntl.flock(fh,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except:
        restart_script()

def restart_script():
    python = sys.executable
    os.execl(python, python, *sys.argv)

singleton()

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
parser.add_argument('-d', '--display', type=str, help="choose type of display: '1in44' (default) | '1in3'")
args = parser.parse_args()

class UserSettings:
    def __init__(self):
        self.pending_changes = False
        try:
            self.tree = ET.parse("settings.xml") 
            self.root = self.tree.getroot()
        except:
            print("Can't load settings file, restoring defaults")
            self.reset_to_default()

        self.pending_reset = False

    def get_setting_value(self, name):
        value = self.root.find(name).text
        return value

    def change_setting_value(self, name, value):
        self.root.find(str(name)).text = str(value)
        self.pending_changes = True

    def save_changes(self):
        if(self.pending_changes == True):
            self.pending_changes = False

            self.tree.write("settings.xml")
            self.tree = ET.parse("settings.xml")
            self.root = self.tree.getroot()

    def reset_to_default(self):
        self.tree = ET.parse("default_settings.xml")
        self.tree.write("settings.xml")
        self.root = self.tree.getroot()
        self.pending_reset = True

class LedStrip:
    def __init__(self):

        self.brightness_percent = int(usersettings.get_setting_value("brightness_percent"))
        self.led_number         = int(usersettings.get_setting_value("led_count"))
        self.shift              = int(usersettings.get_setting_value("shift"))
        self.reverse            = int(usersettings.get_setting_value("reverse"))

        self.brightness = 255 * self.brightness_percent / 100

        self.keylist = [0] * self.led_number
        self.keylist_status = [0] * self.led_number
        self.keylist_color = [0] * self.led_number

        # LED strip configuration:
        self.LED_COUNT      = int(self.led_number)     # Number of LED pixels.
        self.LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
        #LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
        self.LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
        self.LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
        self.LED_BRIGHTNESS = int(self.brightness)    # Set to 0 for darkest and 255 for brightest
        self.LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
        self.LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
        parser.add_argument('-d', '--display', type=str, help="choose type of display: '1in44' (default) | '1in3'")
        args = parser.parse_args()

        # Create NeoPixel object with appropriate configuration.
        self.strip = Adafruit_NeoPixel(self.LED_COUNT, self.LED_PIN, self.LED_FREQ_HZ, self.LED_DMA, self.LED_INVERT, self.LED_BRIGHTNESS, self.LED_CHANNEL)
        # Intialize the library (must be called once before other functions).
        self.strip.begin()

    def change_brightness(self, value):
        self.brightness_percent += value
        self.brightness_percent = clamp(self.brightness_percent, 1, 100)
        self.brightness = 255 * self.brightness_percent / 100

        usersettings.change_setting_value("brightness_percent", self.brightness_percent)

        if(menu.screensaver_is_running == True):
            menu.screensaver_is_running = False

        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
        parser.add_argument('-d', '--display', type=str, help="choose type of display: '1in44' (default) | '1in3'")
        args = parser.parse_args()

        self.strip = Adafruit_NeoPixel(self.LED_COUNT, self.LED_PIN, self.LED_FREQ_HZ, self.LED_DMA, self.LED_INVERT, int(self.brightness), self.LED_CHANNEL)
        # Intialize the library (must be called once before other functions).
        self.strip.begin()
        fastColorWipe(ledstrip.strip, True)

    def change_led_count(self, value):
        self.led_number += value
        self.led_number = max(1, self.led_number)

        usersettings.change_setting_value("led_count", self.led_number)

        self.keylist = [0] * self.led_number
        self.keylist_status = [0] * self.led_number
        self.keylist_color = [0] * self.led_number

        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
        parser.add_argument('-d', '--display', type=str, help="choose type of display: '1in44' (default) | '1in3'")
        args = parser.parse_args()

        self.strip = Adafruit_NeoPixel(int(self.led_number), self.LED_PIN, self.LED_FREQ_HZ, self.LED_DMA, self.LED_INVERT, int(self.brightness), self.LED_CHANNEL)
        # Intialize the library (must be called once before other functions).
        self.strip.begin()
        fastColorWipe(ledstrip.strip, True)

    def change_shift(self, value):
        self.shift += value
        usersettings.change_setting_value("shift", self.shift)
        fastColorWipe(ledstrip.strip, True)

    def change_reverse(self, value):
        self.reverse += value
        self.reverse = clamp(self.reverse, 0, 1)
        usersettings.change_setting_value("reverse", self.reverse)
        fastColorWipe(ledstrip.strip, True)

    def set_adjacent_colors(self, note, color, led_turn_off):
        if(ledsettings.adjacent_mode == "RGB" and color != 0 and led_turn_off != True):
            color = Color(int(ledsettings.adjacent_green), int(ledsettings.adjacent_red), int(ledsettings.adjacent_blue))
        if(ledsettings.adjacent_mode != "Off"):
            self.strip.setPixelColor(int(note)+1, color)
            self.strip.setPixelColor(int(note)-1, color)

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
GPIO.setup(KEYRIGHT,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEYLEFT,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEYUP,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEYDOWN,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEY1,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEY2,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(KEY3,GPIO.IN,GPIO.PUD_UP)
GPIO.setup(JPRESS,GPIO.IN,GPIO.PUD_UP)

#LED animations
def fastColorWipe(strip, update):
    brightness = ledsettings.backlight_brightness_percent / 100
    red     = int(ledsettings.get_backlight_color("Red") * brightness)
    green   = int(ledsettings.get_backlight_color("Green") * brightness)
    blue    = int(ledsettings.get_backlight_color("Blue") * brightness)
    color   = Color(green, red, blue)
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    if (update == True):
        strip.show()

def theaterChase(strip, color, wait_ms=50):
    """Movie theater light style chaser animation."""
    if (menu.screensaver_is_running == True):
        menu.screensaver_is_running = False
        time.sleep(1)
        fastColorWipe(ledstrip.strip, True)
    menu.t = threading.currentThread()
    j = 0
    menu.screensaver_is_running = True

    while (menu.screensaver_is_running == True):
        red = int(ledsettings.get_color("Red"))
        green = int(ledsettings.get_color("Green"))
        blue = int(ledsettings.get_color("Blue"))

        for q in range(5):
            for i in range(0, strip.numPixels(), 5):
                strip.setPixelColor(i+q, Color(green, red, blue))
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 5):
                strip.setPixelColor(i+q, 0)
        j += 1
        if(j > 256):
            j = 0
    menu.screensaver_is_running = False
    fastColorWipe(ledstrip.strip, True)

def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)

def rainbow(strip, wait_ms=20):
    """Draw rainbow that fades across all pixels at once."""
    if (menu.screensaver_is_running == True):
        menu.screensaver_is_running = False
        time.sleep(1)
        fastColorWipe(ledstrip.strip, True)
    menu.t = threading.currentThread()
    j = 0
    menu.screensaver_is_running = True
    while (menu.screensaver_is_running == True):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((j) & 255))
        j += 1
        if(j >= 256):
            j = 0
        strip.show()
        time.sleep(wait_ms/1000.0)
    menu.screensaver_is_running = False
    fastColorWipe(ledstrip.strip, True)

def rainbowCycle(strip, wait_ms=20):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    if (menu.screensaver_is_running == True):
        menu.screensaver_is_running = False
        time.sleep(1)
        fastColorWipe(ledstrip.strip, True)
    menu.t = threading.currentThread()
    j = 0
    menu.screensaver_is_running = True
    while (menu.screensaver_is_running == True):
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
        j += 1
        if(j >= 256):
            j = 0
        strip.show()
        time.sleep(wait_ms/1000.0)
    menu.screensaver_is_running = False
    fastColorWipe(ledstrip.strip, True)
 
def theaterChaseRainbow(strip, wait_ms=10):
    """Rainbow movie theater light style chaser animation."""
    if (menu.screensaver_is_running == True):
        menu.screensaver_is_running = False
        time.sleep(1)
        fastColorWipe(ledstrip.strip, True)
    menu.t = threading.currentThread()
    j = 0
    menu.screensaver_is_running = True
    while (menu.screensaver_is_running == True):
        for q in range(5):
            for i in range(0, strip.numPixels(), 5):
                strip.setPixelColor(i+q, wheel((i+j) % 255))
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 5):
                strip.setPixelColor(i+q, 0)
        j += 1

        if(j > 256):
            j = 0
    menu.screensaver_is_running = False
    fastColorWipe(ledstrip.strip, True)

def breathing(strip, wait_ms=2):
    if (menu.screensaver_is_running == True):
        menu.screensaver_is_running = False
        time.sleep(1)
        fastColorWipe(ledstrip.strip, True)
    menu.t = threading.currentThread()
    menu.screensaver_is_running = True

    multiplier = 24
    direction = 2
    while (menu.screensaver_is_running == True):
        if(multiplier >= 98 or multiplier < 24):
            direction *= -1
        multiplier += direction
        divide = multiplier / float(100)
        red = int(round(float(ledsettings.get_color("Red")) * float(divide)))
        green = int(round(float(ledsettings.get_color("Green")) * float(divide)))
        blue = int(round(float(ledsettings.get_color("Blue")) * float(divide)))

        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(green, red, blue))
        strip.show()
        if(wait_ms > 0):
            time.sleep(wait_ms/1000.0)
    menu.screensaver_is_running = False
    fastColorWipe(ledstrip.strip, True)

def sound_of_da_police(strip, wait_ms=5):
    if (menu.screensaver_is_running == True):
        menu.screensaver_is_running = False
        time.sleep(1)
        fastColorWipe(ledstrip.strip, True)
    menu.t = threading.currentThread()
    menu.screensaver_is_running = True
    middle = strip.numPixels() / 2
    r_start = 0
    l_start = 196
    while (menu.screensaver_is_running == True):
        r_start += 14
        l_start -= 14
        for i in range(strip.numPixels()):
            if((i > middle) and i > (r_start) and i < (r_start + 40)):
                strip.setPixelColor(i, Color(0, 255, 0))
            elif((i < middle) and i < (l_start) and i > (l_start - 40)):
                strip.setPixelColor(i, Color(0, 0, 255))
            else:
                strip.setPixelColor(i, Color(0, 0, 0))
        if(r_start > 150):
            r_start = 0
            l_start = 175
        strip.show()
        time.sleep(wait_ms/1000.0)
    menu.screensaver_is_running = False
    fastColorWipe(ledstrip.strip, True)

def scanner(strip, wait_ms=1):
    if (menu.screensaver_is_running == True):
        menu.screensaver_is_running = False
        time.sleep(1)
        fastColorWipe(ledstrip.strip, True)
    menu.t = threading.currentThread()
    menu.screensaver_is_running = True

    position = 0
    direction = 3
    scanner_length = 20

    red_fixed = ledsettings.get_color("Red")
    green_fixed = ledsettings.get_color("Green")
    blue_fixed = ledsettings.get_color("Blue")
    while (menu.screensaver_is_running == True):
        position += direction
        for i in range(strip.numPixels()):
            if(i > (position - (scanner_length)) and i < (position + (scanner_length))):
                distance_from_position = position - i
                if(distance_from_position < 0):
                    distance_from_position *= -1
                divide = ((scanner_length / 2) - distance_from_position) / float(scanner_length / 2)

                red = int(float(red_fixed) * float(divide))
                green = int(float(green_fixed) * float(divide))
                blue = int(float(blue_fixed) * float(divide))

                if(divide > 0):
                    strip.setPixelColor(i, Color(green, red, blue))
                else:
                    strip.setPixelColor(i, Color(0, 0, 0))

        if(position >= strip.numPixels() or position <= 1):
            direction *= -1
        strip.show()
        time.sleep(wait_ms/1000.0)

    menu.screensaver_is_running = False
    fastColorWipe(ledstrip.strip, True)

def get_rainbow_colors(pos, color):
    pos = int(pos)
    if pos < 85:
        if(color == "green"):
            return pos * 3
        elif(color == "red"):
            return 255 - pos * 3
        elif(color == "blue"):
            return 0
    elif pos < 170:
        pos -= 85
        if(color == "green"):
            return 255 - pos * 3
        elif(color == "red"):
            return 0
        elif(color == "blue"):
            return pos * 3
    else:
        pos -= 170
        if(color == "green"):
            return 0
        elif(color == "red"):
            return pos * 3
        elif(color == "blue"):
            return 255 - pos * 3

# scale: 1 means in C, scale: 2 means in C#, scale: 3 means in D, etc...
def get_scale_color(scale, note_position):
    notes_in_scale = [0,2,4,5,7,9,11]
    scale = int(scale)
    note_position = (note_position - scale)  % 12

    if note_position in notes_in_scale:
        return list(ledsettings.key_in_scale.values())
    else:
        return list(ledsettings.key_not_in_scale.values())

class MenuLCD:
    def __init__(self, xml_file_name):
        if args.display == '1in3':
            self.LCD = LCD_1in3.LCD()
            self.font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf', self.scale(10))
        else:
            self.LCD = LCD_1in44.LCD()
            self.font = ImageFont.load_default()
        self.LCD.LCD_Init()
        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), "GREEN")
        self.draw = ImageDraw.Draw(self.image)
        self.LCD.LCD_ShowImage(self.image,0,0)
        self.xml_file_name = xml_file_name
        self.DOMTree = minidom.parse(xml_file_name)
        self.currentlocation = "menu";
        self.scroll_hold = 0
        self.cut_count = 0
        self.pointer_position = 0
        self.background_color = usersettings.get_setting_value("background_color")
        self.text_color = usersettings.get_setting_value("text_color")
        self.update_songs()
        self.update_ports()
        self.speed_multiplier = 1

        self.screensaver_settings = dict()
        self.screensaver_settings['time'] = usersettings.get_setting_value("time")
        self.screensaver_settings['date'] = usersettings.get_setting_value("date")
        self.screensaver_settings['cpu_chart'] = usersettings.get_setting_value("cpu_chart")
        self.screensaver_settings['cpu'] = usersettings.get_setting_value("cpu")
        self.screensaver_settings['ram'] = usersettings.get_setting_value("ram")
        self.screensaver_settings['temp'] = usersettings.get_setting_value("temp")
        self.screensaver_settings['network_usage'] = usersettings.get_setting_value("network_usage")
        self.screensaver_settings['sd_card_space'] = usersettings.get_setting_value("sd_card_space")

        self.screensaver_delay = usersettings.get_setting_value("screensaver_delay")
        self.screen_off_delay = usersettings.get_setting_value("screen_off_delay")
        self.led_animation_delay = usersettings.get_setting_value("led_animation_delay")

        self.led_animation = usersettings.get_setting_value("led_animation")

        self.screen_status = 1

        self.screensaver_is_running = False

    def toggle_screensaver_settings(self, setting):
        setting = setting.lower()
        setting = setting.replace(" ", "_")
        if(str(self.screensaver_settings[setting]) == "1"):
            usersettings.change_setting_value(setting, "0")
            self.screensaver_settings[setting] = "0"
        else:
            usersettings.change_setting_value(setting, "1")
            self.screensaver_settings[setting] = "1"

    def update_songs(self):
        songs_list = os.listdir("Songs")
        self.DOMTree = minidom.parse(self.xml_file_name)
        for song in songs_list:
            # List of songs for Play_MIDI
            element = self.DOMTree.createElement("Choose_song")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", song)
            mc = self.DOMTree.getElementsByTagName("Play_MIDI")[0]
            mc.appendChild(element)
            # List of songs for Learn_MIDI
            element = self.DOMTree.createElement("Load_song")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", song)
            mc = self.DOMTree.getElementsByTagName("Learn_MIDI")[0]
            mc.appendChild(element)

    def update_sequence_list(self):
        try:
            sequences_tree = minidom.parse("sequences.xml")
            self.update_songs()
            i = 0
            while(True):
                try:
                    i += 1
                    sequence_name = sequences_tree.getElementsByTagName("sequence_"+str(i))[0].getElementsByTagName("sequence_name")[0].firstChild.nodeValue
                    element = self.DOMTree.createElement("Sequences")
                    element.appendChild(self.DOMTree.createTextNode(""))
                    element.setAttribute("text"  , str(sequence_name))
                    mc = self.DOMTree.getElementsByTagName("LED_Strip_Settings")[0]
                    mc.appendChild(element)

                except:
                    break
        except:
            self.render_message("Something went wrong", "Check your sequences file", 1500)

    def update_ports(self):
        ports = mido.get_input_names()
        self.update_sequence_list()
        for port in ports:
            element = self.DOMTree.createElement("Input")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , port)
            mc = self.DOMTree.getElementsByTagName("Ports_Settings")[0]
            mc.appendChild(element)

            element = self.DOMTree.createElement("Playback")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , port)
            mc = self.DOMTree.getElementsByTagName("Ports_Settings")[2]
            mc.appendChild(element)

    def update_multicolor(self, colors_list):
        i = 0
        self.update_ports()
        rgb_names = []
        rgb_names = ["Red", "Green", "Blue"]
        for color in colors_list:
            i = i + 1

            element = self.DOMTree.createElement("Multicolor")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , "Color"+str(i))
            mc = self.DOMTree.getElementsByTagName("LED_Color")[0]
            mc.appendChild(element)

            element = self.DOMTree.createElement("Color"+str(i))
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , "RGB Color"+str(i))
            mc = self.DOMTree.getElementsByTagName("Multicolor")[0]
            mc.appendChild(element)

            #adding key range to menu
            element = self.DOMTree.createElement("Color"+str(i))
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , "Key range"+str(i))
            mc = self.DOMTree.getElementsByTagName("Multicolor")[0]
            mc.appendChild(element)	

            element = self.DOMTree.createElement("Key_range"+str(i))
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , "Start")
            mc = self.DOMTree.getElementsByTagName("Color"+str(i))[0]
            mc.appendChild(element)

            element = self.DOMTree.createElement("Key_range"+str(i))
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , "End")
            mc = self.DOMTree.getElementsByTagName("Color"+str(i))[0]
            mc.appendChild(element)

            #adding delete
            element = self.DOMTree.createElement("Color"+str(i))
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text"  , "Delete")
            mc = self.DOMTree.getElementsByTagName("Multicolor")[0]
            mc.appendChild(element)

            for rgb_name in rgb_names:
                element = self.DOMTree.createElement("RGB_Color"+str(i))
                element.appendChild(self.DOMTree.createTextNode(""))
                element.setAttribute("text"  , rgb_name)
                mc = self.DOMTree.getElementsByTagName("Color"+str(i))[0]
                mc.appendChild(element)

    def scale(self, size):
        return int(round(size * self.LCD.font_scale))

    def show(self, position = "default", back_pointer_location=False):
        if(position == "default" and  self.currentlocation):
            position = self.currentlocation
            refresh = 1
        elif(position == "default" and not self.currentlocation):
            position = "menu"
            refresh = 1
        else:
            position = position.replace(" ", "_")
            self.currentlocation = position 
            refresh = 0

        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((self.scale(2), self.scale(5)), position.replace("_", " "), fill=self.text_color, font=self.font)

        #getting list of items in current menu
        staffs = self.DOMTree.getElementsByTagName(position)
        text_margin_top = self.scale(15)
        i = 0
        list_count = len(staffs)
        list_count -= 1

        if(self.pointer_position > 9):
            self.menu_offset = self.pointer_position - 9
        else:
            self.menu_offset = -1

        #looping through menu list
        for staff in staffs:
            self.pointer_position = clamp(self.pointer_position, 0, list_count)
            #drawing little arrow to show there are more items above
            if(self.pointer_position > 9 and i < self.menu_offset):
                self.draw.line(
                    [
                        (self.scale(119), self.scale(20)),
                        (self.scale(125), self.scale(20))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )
                self.draw.line(
                    [
                        (self.scale(119), self.scale(20)),
                        (self.scale(122), self.scale(17))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )
                self.draw.line(
                    [
                        (self.scale(119), self.scale(20)),
                        (self.scale(122), self.scale(17))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )
                i += 1
                continue

            sid = staff.getAttribute("text")

            if(not back_pointer_location):
                if(i == self.pointer_position):
                    try:
                        self.parent_menu = staff.parentNode.tagName
                    except:
                        self.parent_menu = "end"
                    self.draw.rectangle(
                        [
                            (0, text_margin_top),
                            (self.LCD.width, text_margin_top + self.scale(11))
                        ],
                        fill="Crimson"
                    )
                    self.draw.text((self.scale(3), text_margin_top), ">", fill=self.text_color, font=self.font)
                    self.current_choice = sid
            else:
                if(sid == back_pointer_location):
                    try:
                        self.parent_menu = staff.parentNode.tagName
                    except:
                        self.parent_menu = "data"
                    self.draw.rectangle([(0, text_margin_top), (self.LCD.width, text_margin_top + self.scale(11))], fill="Crimson")
                    self.draw.text((self.scale(3), text_margin_top), ">", fill=self.text_color, font=self.font)
                    self.current_choice = sid
                    self.pointer_position = i
            #drawing little arrow to show there are more items below
            if(i == 10 and self.pointer_position < list_count and list_count > 10):
                self.draw.line(
                    [
                        (self.scale(119), self.scale(120)),
                        (self.scale(125), self.scale(120))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )
                self.draw.line(
                    [
                        (self.scale(119), self.scale(120)),
                        (self.scale(122), self.scale(123))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )
                self.draw.line(
                    [
                        (self.scale(122), self.scale(123)),
                        (self.scale(125), self.scale(120))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )

            #scrolling text if too long
            if(self.pointer_position == i and len(sid) > 18):
                tobecontinued = ".."
                if(refresh == 1):
                    try:
                        self.cut_count += 1
                    except:
                        self.cut_count = -6
                else:
                    cut = 0
                    self.cut_count = -6
                if(self.cut_count > (len(sid) - 16)):
                    #hold scrolling on end
                    if(self.scroll_hold < 8):
                        self.cut_count -= 1
                        self.scroll_hold += 1
                        tobecontinued = ""
                    else:
                        self.cut_count = -6
                        self.scroll_hold = 0
                    cut = self.cut_count
                if(self.cut_count >= 0):
                   cut = self.cut_count
                else:
                    cut = 0
            else:
                cut = 0
                tobecontinued = ""

            i += 1

            #diplaying screensaver status
            if(self.currentlocation == "Content"):
                sid_temp = sid.lower()
                sid_temp = sid_temp.replace(" ", "_")
                if(str(menu.screensaver_settings[sid_temp]) == "1"):
                    sid_temp = " +"
                else:
                    sid_temp = " -"
                sid = sid+sid_temp
            self.draw.text((self.scale(10), text_margin_top), sid[cut:(18 + cut)]+tobecontinued, fill=self.text_color, font=self.font)

            text_margin_top += self.scale(10)

        #displaying color example
        if(self.currentlocation == "RGB"):
            self.draw.text((self.scale(10), self.scale(70)), str(ledsettings.get_colors()), fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width,self.LCD.height)],fill="rgb("+str(ledsettings.get_colors())+")")

        if("RGB_Color" in self.currentlocation):
            self.draw.text((self.scale(10), self.scale(70)), str(ledsettings.get_multicolors(self.currentlocation.replace('RGB_Color',''))), fill = self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width,self.LCD.height)], fill="rgb("+str(ledsettings.get_multicolors(self.currentlocation.replace('RGB_Color','')))+")")

        if("Backlight_Color" in self.currentlocation):
            self.draw.text((self.scale(10), self.scale(70)), str(ledsettings.get_backlight_colors()), fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0),self.scale(80)),(self.LCD.width,self.LCD.height)], fill="rgb("+str(ledsettings.get_backlight_colors())+")")

        if("Custom_RGB" in self.currentlocation):
            self.draw.text((self.scale(10), self.scale(70)), str(ledsettings.get_adjacent_colors()), fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)),(self.LCD.width,self.LCD.height)], fill="rgb("+str(ledsettings.get_adjacent_colors())+")")
        
        if("Multicolor" in self.currentlocation):
            try:
                self.draw.rectangle([(self.scale(115), self.scale(50)), (self.LCD.width, self.scale(80))], fill="rgb("+str(ledsettings.get_multicolors(self.current_choice.replace('Color','')))+")")
            except:
                pass

        if("Color_for_slow_speed" in self.currentlocation):
            red = ledsettings.speed_slowest["red"]
            green = ledsettings.speed_slowest["green"]
            blue = ledsettings.speed_slowest["blue"]
            self.draw.text((self.scale(10), self.scale(70)), str(red)+", "+str(green)+", "+str(blue), fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)),(self.LCD.width,self.LCD.height)], fill="rgb("+str(red)+", "+str(green)+", "+str(blue)+")")

        if("Color_for_fast_speed" in self.currentlocation):
            red = ledsettings.speed_fastest["red"]
            green = ledsettings.speed_fastest["green"]
            blue = ledsettings.speed_fastest["blue"]
            self.draw.text((self.scale(10), self.scale(70)), str(red)+", "+str(green)+", "+str(blue), fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)),(self.LCD.width,self.LCD.height)], fill="rgb("+str(red)+", "+str(green)+", "+str(blue)+")")

        if("Color_in_scale" in self.currentlocation):
            red = ledsettings.key_in_scale["red"]
            green = ledsettings.key_in_scale["green"]
            blue = ledsettings.key_in_scale["blue"]
            self.draw.text((self.scale(10), self.scale(70)), str(red)+", "+str(green)+", "+str(blue), fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)),(self.LCD.width,self.LCD.height)], fill="rgb("+str(red)+", "+str(green)+", "+str(blue)+")")

        if("Color_not_in_scale" in self.currentlocation):
            red = ledsettings.key_not_in_scale["red"]
            green = ledsettings.key_not_in_scale["green"]
            blue = ledsettings.key_not_in_scale["blue"]
            self.draw.text((self.scale(10), self.scale(70)), str(red)+", "+str(green)+", "+str(blue), fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)),(self.LCD.width,self.LCD.height)], fill="rgb("+str(red)+", "+str(green)+", "+str(blue)+")")

        #displaying rainbow offset value
        if(self.current_choice == "Offset"):
            self.draw.text((self.scale(10), self.scale(70)), str(ledsettings.rainbow_offset), fill=self.text_color, font=self.font)

        if(self.current_choice == "Scale"):
            self.draw.text((self.scale(10), self.scale(70)), str(ledsettings.rainbow_scale)+"%", fill=self.text_color, font=self.font)

        if(self.current_choice == "Timeshift"):
            self.draw.text((self.scale(10), self.scale(70)), str(ledsettings.rainbow_timeshift), fill=self.text_color, font=self.font)

        #displaying brightness value
        if(self.currentlocation == "Brightness"):
            self.draw.text((self.scale(10), self.scale(35)), str(ledstrip.brightness_percent)+"%", fill=self.text_color, font=self.font)
            miliamps = int(ledstrip.LED_COUNT) * (60 / (100 / float(ledstrip.brightness_percent)))
            amps = round(float(miliamps) / float(1000),2)
            self.draw.text((self.scale(10), self.scale(50)), "Amps needed to "+"\n"+"power "+str(ledstrip.LED_COUNT)+" LEDS with "+"\n"+"white color: "+str(amps), fill=self.text_color, font=self.font)
                    
        if(self.currentlocation == "Backlight_Brightness"):
            self.draw.text((self.scale(10), self.scale(35)), str(ledsettings.backlight_brightness_percent)+"%", fill=self.text_color, font=self.font)

        #displaying led count
        if(self.currentlocation == "Led_count"):
            self.draw.text((self.scale(10), self.scale(35)), str(ledstrip.led_number), fill=self.text_color, font=self.font)

        #displaying shift
        if(self.currentlocation == "Shift"):
            self.draw.text((self.scale(10), self.scale(35)), str(ledstrip.shift), fill=self.text_color, font=self.font)

        #displaying reverse
        if(self.currentlocation == "Reverse"):
            self.draw.text((self.scale(10), self.scale(35)), str(ledstrip.reverse), fill=self.text_color, font=self.font)

        if("Key_range" in self.currentlocation):
            if(self.current_choice == "Start"):
                try:
                    self.draw.text((self.scale(10), self.scale(50)), str(ledsettings.multicolor_range[int(self.currentlocation.replace('Key_range',''))-1][0]), fill = self.text_color, font=self.font)
                except: 
                    pass
            else:
                self.draw.text((self.scale(10), self.scale(50)), str(ledsettings.multicolor_range[int(self.currentlocation.replace('Key_range',''))-1][1]), fill = self.text_color, font=self.font)

        #displaying screensaver settings
        if(self.currentlocation == "Start_delay"):
             self.draw.text((self.scale(10), self.scale(70)), str(self.screensaver_delay), fill=self.text_color, font=self.font)

        if(self.currentlocation == "Turn_off_screen_delay"):
             self.draw.text((self.scale(10), self.scale(70)), str(self.screen_off_delay), fill = self.text_color, font=self.font)

        if(self.currentlocation == "Led_animation_delay"):
             self.draw.text((self.scale(10), self.scale(70)), str(self.led_animation_delay), fill = self.text_color, font=self.font)

        #displaying speed values
        if(self.currentlocation == "Period"):
            self.draw.text((self.scale(10), self.scale(70)), str(ledsettings.speed_period_in_seconds), fill = self.text_color, font=self.font)

        if(self.currentlocation == "Max_notes_in_period"):
            self.draw.text((self.scale(10), self.scale(70)), str(ledsettings.speed_max_notes), fill = self.text_color, font=self.font)

        #displaying scale key
        if(self.currentlocation == "Scale_Coloring"):
            self.draw.text((self.scale(10), self.scale(70)), "scale: " + str(ledsettings.scales[ledsettings.scale_key]), fill = self.text_color, font=self.font)

        # Learn MIDI
        if(self.currentlocation == "Learn_MIDI"):
            #  Position 1: display Load song
            self.draw.text((self.scale(90), self.scale(5+10)), str(learning.loadingList[learning.loading]), fill = self.text_color, font=self.font)
            #  Position 2: display Learning Start/Stop
            self.draw.text((self.scale(90), self.scale(5+20)), str(learning.learningList[learning.is_started_midi]), fill = self.text_color, font=self.font)
            #  Position 3: display Practice
            self.draw.text((self.scale(90), self.scale(5+30)), str(learning.practiceList[learning.practice]), fill = self.text_color, font=self.font)
            #  Position 4: display Hands
            self.draw.text((self.scale(90), self.scale(5+40)), str(learning.handsList[learning.hands]), fill = self.text_color, font=self.font)
            #  Position 5: display Mute hand
            self.draw.text((self.scale(90), self.scale(5+50)), str(learning.mute_handList[learning.mute_hand]), fill = self.text_color, font=self.font)
            #  Position 6: display Start point
            self.draw.text((self.scale(90), self.scale(5+60)), str(learning.start_point)+"%", fill = self.text_color, font=self.font)
            #  Position 7: display End point
            self.draw.text((self.scale(90), self.scale(5+70)), str(learning.end_point)+"%", fill = self.text_color, font=self.font)
            #  Position 8: display Set tempo
            self.draw.text((self.scale(90), self.scale(5+80)), str(learning.set_tempo)+"%", fill = self.text_color, font=self.font)
            #  Position 9,10: display Hands colors
            coordR = 7 + 90
            coordL = 7 + 100
            self.draw.rectangle([(self.scale(90), self.scale(coordR)), (self.LCD.width, self.scale(coordR+7))], fill="rgb("+str(learning.hand_colorList[learning.hand_colorR])[1:-1]+")")
            self.draw.rectangle([(self.scale(90), self.scale(coordL)), (self.LCD.width, self.scale(coordL+7))], fill="rgb("+str(learning.hand_colorList[learning.hand_colorL])[1:-1]+")")

        self.LCD.LCD_ShowImage(self.image,0,0)

    def change_pointer(self, direction):
        if(direction == 0):
            self.pointer_position -= 1
        elif(direction == 1):
            self.pointer_position += 1
        menu.cut_count = -6
        menu.show()

    def enter_menu(self): 
        position = self.current_choice.replace(" ", "_")

        if(not self.DOMTree.getElementsByTagName(position)):
            menu.change_settings(self.current_choice, self.currentlocation)
        else:
            self.currentlocation = self.current_choice
            self.pointer_position = 0
            menu.cut_count = -6
            menu.show(self.current_choice)

    def go_back(self):
        if(self.parent_menu != "data"):
            location_readable = self.currentlocation.replace("_", " ")
            menu.cut_count = -6
            menu.show(self.parent_menu, location_readable)

    def render_message(self, title, message, delay = 500):
        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((self.scale(3), self.scale(55)), title, fill=self.text_color, font=self.font)
        self.draw.text((self.scale(3), self.scale(65)), message, fill=self.text_color, font=self.font)
        self.LCD.LCD_ShowImage(self.image,0,0)
        LCD_Config.Driver_Delay_ms(delay)  

    def render_screensaver(self, hour, date, cpu, cpu_average, ram, temp, cpu_history = [], upload = 0, download = 0, card_space = 0):
        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)

        total_height = self.scale(1)
        info_count = 0
        for key, value in menu.screensaver_settings.items():
            if(str(key) == "time" and str(value) == "1"):
                total_height += self.scale(31)
            elif(str(key) == "date" and str(value) == "1"):
                total_height += self.scale(13)
            elif(str(key) == "cpu_chart" and str(value) == "1"):
                total_height += self.scale(35)
            else:
                if(str(value) == "1"):
                    info_count += 1

            height_left = self.LCD.height - total_height

        if(info_count > 0):
            info_height_font = height_left / info_count
        else:
            info_height_font = 0

        top_offset = self.scale(2)

        if(menu.screensaver_settings["time"] == "1"):
            fonthour = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSansBold.ttf', self.scale(31))
            self.draw.text((self.scale(4), top_offset), hour, fill=self.text_color, font=fonthour)
            top_offset += self.scale(31)

        if(menu.screensaver_settings["date"] == "1"):
            font_date = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSansBold.ttf', self.scale(13))
            self.draw.text((self.scale(34), top_offset), date, fill=self.text_color, font=font_date)
            top_offset += self.scale(13)

        if(menu.screensaver_settings["cpu_chart"] == "1"):
            previous_height = 0
            c = self.scale(-5)
            for cpu_chart in cpu_history:
                height = self.scale(((100 - cpu_chart) * 35) / float(100))
                self.draw.line([(c, top_offset+previous_height), (c+self.scale(5), top_offset+height)], fill="Red", width=self.scale(1))
                previous_height = height
                c += self.scale(5)
            top_offset += self.scale(35)

        if(info_height_font > self.scale(12)):
            info_height_font = self.scale(12)

        font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSansBold.ttf', int(info_height_font))

        if(menu.screensaver_settings["cpu"] == "1"):
            self.draw.text((self.scale(1), top_offset), "CPU: "+str(cpu)+"% ("+str(cpu_average)+"%)", fill = self.text_color, font=font)
            top_offset += info_height_font

        if(menu.screensaver_settings["ram"] == "1"): 
            self.draw.text((self.scale(1), top_offset), "RAM usage: "+str(ram)+"%", fill = self.text_color, font=font)
            top_offset += info_height_font

        if(menu.screensaver_settings["temp"] == "1"): 
            self.draw.text((self.scale(1), top_offset), "Temp: "+str(temp)+" C", fill = self.text_color, font=font)
            top_offset += info_height_font

        if(menu.screensaver_settings["network_usage"] == "1"):
            if(info_height_font > self.scale(11)):
                info_height_font_network = self.scale(11)
            else:
                info_height_font_network = int(info_height_font)
            font_network = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSansBold.ttf', int(info_height_font_network))
            self.draw.text((self.scale(1), top_offset), "D:"+str("{:.2f}".format(download))+"Mb/s U:"+str("{:.2f}".format(upload))+"Mb/s", fill = self.text_color, font=font_network)
            top_offset += info_height_font_network

        if(menu.screensaver_settings["sd_card_space"] == "1"):
            self.draw.text((self.scale(1), top_offset), "SD: "+str(round(card_space.used/(1024.0 ** 3), 1))+"/"+str(round(card_space.total/(1024.0 ** 3), 1))+"("+str(card_space.percent)+"%)", fill = self.text_color, font=font)
            top_offset += info_height_font

        self.LCD.LCD_ShowImage(self.image,0,0)

    def change_settings(self, choice, location):
        if(location == "Text_Color"):
            self.text_color = choice
            usersettings.change_setting_value("text_color", self.text_color)
        if(location == "Background_Color"):
            self.background_color = choice
            usersettings.change_setting_value("background_color", self.background_color)
        if(self.text_color == self.background_color):
            self.text_color = "Red"
            usersettings.change_setting_value("text_color", self.text_color)

        # Play MIDI
        if(location == "Choose_song"):
            saving.t = threading.Thread(target=play_midi, args=(choice,))
            saving.t.start()
        if(location == "Play_MIDI"):
            if(choice == "Save MIDI"):
                now = datetime.datetime.now()
                current_date = now.strftime("%Y-%m-%d %H:%M")
                menu.render_message("Recording stopped", "Saved as "+current_date, 2000)
                saving.save(current_date)
                menu.update_songs()
            if(choice =="Start recording"):
                menu.render_message("Recording started", "", 2000)
                saving.start_recording()
            if(choice == "Cancel recording"):
                menu.render_message("Recording canceled", "", 2000)
                saving.cancel_recording()
            if(choice == "Stop playing"):
                saving.is_playing_midi.clear()
                menu.render_message("Playing stopped", "", 2000)
                fastColorWipe(ledstrip.strip, True)

        # Learn MIDI
        if (location == "Load_song"):
            learning.t = threading.Thread(target=load_midi, args=(choice,))
            learning.t.start()
            menu.go_back()
        if (location == "Learn_MIDI"):
            if (choice == "Learning"):
                if (not learning.is_started_midi):
                    learning.t = threading.Thread(target=learn_midi)
                    learning.t.start()
                else:
                    learning.is_started_midi = False
                    fastColorWipe(ledstrip.strip, True)
                menu.show(location)

        if(location == "Solid"):
            ledsettings.change_color_name(wc.name_to_rgb(choice))
            ledsettings.color_mode = "Single"
            usersettings.change_setting_value("color_mode", ledsettings.color_mode)

        if(location == "Fading"):
            ledsettings.mode = "Fading"
            usersettings.change_setting_value("mode", ledsettings.mode)
            if (choice == "Very fast"):
                ledsettings.fadingspeed = 50
            elif(choice == "Fast"):
                ledsettings.fadingspeed = 40
            elif(choice == "Medium"):
                ledsettings.fadingspeed = 20
            elif(choice == "Slow"):
                ledsettings.fadingspeed = 10
            elif(choice == "Very slow"):
                ledsettings.fadingspeed = 2
            elif (choice == "Instant"):
                ledsettings.fadingspeed = 1000
            usersettings.change_setting_value("fadingspeed", ledsettings.fadingspeed)

        if(location == "Velocity"):
            ledsettings.mode = "Velocity"
            usersettings.change_setting_value("mode", ledsettings.mode)
            if(choice == "Fast"):
                ledsettings.fadingspeed = 10
            elif(choice == "Medium"):
                ledsettings.fadingspeed = 8
            elif(choice == "Slow"):
                ledsettings.fadingspeed = 6
            elif(choice == "Very slow"):
                ledsettings.fadingspeed = 3
            usersettings.change_setting_value("fadingspeed", ledsettings.fadingspeed)

        if(location == "Light_mode"):
            ledsettings.mode = "Normal"
            usersettings.change_setting_value("mode", ledsettings.mode)
            fastColorWipe(ledstrip.strip, True)

        if(location == "Input"):
            midiports.change_port("inport", choice)
        if(location == "Playback"):
            midiports.change_port("playport", choice)

        if(location == "Ports_Settings"):
            if(choice == "Refresh ports" or choice == "Input" or choice == "Playback"):
                menu.update_ports()

            if(choice == "Reset Bluetooth service"):
                menu.render_message("Reseting BL service", "", 1000)
                os.system("sudo systemctl restart btmidi.service")

        if(location == "LED_animations"):
            if(choice == "Theater Chase"):
                self.t = threading.Thread(target=theaterChase, args=(ledstrip.strip, Color(127, 127, 127)))
                self.t.start()
            if(choice == "Theater Chase Rainbow"):
                self.t = threading.Thread(target=theaterChaseRainbow, args=(ledstrip.strip, 5))
                self.t.start()
            if(choice == "Sound of da police"):
                self.t = threading.Thread(target=sound_of_da_police, args=(ledstrip.strip, 1))
                self.t.start()
            if(choice == "Scanner"):
                self.t = threading.Thread(target=scanner, args=(ledstrip.strip, 1))
                self.t.start()
            if(choice == "Clear"):
                fastColorWipe(ledstrip.strip, True)
        if(location == "Breathing"):
            if(choice == "Fast"):
                self.t = threading.Thread(target=breathing, args=(ledstrip.strip,5))
                self.t.start()
            if(choice == "Medium"):
                self.t = threading.Thread(target=breathing, args=(ledstrip.strip,10))
                self.t.start()
            if(choice == "Slow"):
                self.t = threading.Thread(target=breathing, args=(ledstrip.strip,25))
                self.t.start()
        if(location == "Rainbow"):
            if(choice == "Fast"):
                self.t = threading.Thread(target=rainbow, args=(ledstrip.strip,2))
                self.t.start()
            if(choice == "Medium"):
                self.t = threading.Thread(target=rainbow, args=(ledstrip.strip,20))
                self.t.start()
            if(choice == "Slow"):
                self.t = threading.Thread(target=rainbow, args=(ledstrip.strip,50))
                self.t.start()
        if(location == "Rainbow_Cycle"):
            if(choice == "Fast"):
                self.t = threading.Thread(target=rainbowCycle, args=(ledstrip.strip,1))
                self.t.start()
            if(choice == "Medium"):
                self.t = threading.Thread(target=rainbowCycle, args=(ledstrip.strip,20))
                self.t.start()
            if(choice == "Slow"):
                self.t = threading.Thread(target=rainbowCycle, args=(ledstrip.strip,50))
                self.t.start()

        if(location == "LED_animations"):
            if(choice == "Stop animation"):
                self.screensaver_is_running = False

        if(location == "Other_Settings"):
            if(choice == "System Info"):
                screensaver()

        if(location == "Rainbow_Colors"):
            ledsettings.color_mode = "Rainbow"
            usersettings.change_setting_value("color_mode", ledsettings.color_mode)

        if(choice == "Add Color"):
            ledsettings.addcolor()

        if(choice == "Delete"):
            ledsettings.deletecolor(location.replace('Color',''))

        if(location == "Multicolor" and choice == "Confirm"):
            ledsettings.color_mode = "Multicolor"
            usersettings.change_setting_value("color_mode", ledsettings.color_mode)

        if(location == "Speed" and choice == "Confirm"):
            ledsettings.color_mode = "Speed"
            usersettings.change_setting_value("color_mode", ledsettings.color_mode)

        if(location == "Scale_Coloring" and choice == "Confirm"):
            ledsettings.color_mode = "Scale"
            usersettings.change_setting_value("color_mode", ledsettings.color_mode)
            print("color mode set to Scale")

        if (location == "Scale_key"):
            ledsettings.scale_key = ledsettings.scales.index(choice)
            usersettings.change_setting_value("scale_key", ledsettings.scale_key)

        if(location == "Sequences"):
            if(choice == "Update"):
                refresh_result = menu.update_sequence_list()
                if(refresh_result == False):
                    menu.render_message("Something went wrong", "Make sure your sequence file is correct", 1500)
            else:
                ledsettings.set_sequence(self.pointer_position, 0)

        if(location == "Sides_Color"):
            if(choice == "Custom RGB"):
                ledsettings.adjacent_mode = "RGB"
            if(choice == "Same as main"):
                ledsettings.adjacent_mode = "Main"
            if(choice == "Off"):
                ledsettings.adjacent_mode = "Off"
            usersettings.change_setting_value("adjacent_mode", ledsettings.adjacent_mode)

        if(location == "Reset_to_default_settings"):
            if(choice == "Confirm"):
                usersettings.reset_to_default()
            else:
                self.go_back()

        if (location == "Update_visualizer"):
            if (choice == "Confirm"):
                menu.render_message("Updating...", "reboot is required", 5000)
                call("sudo git reset --hard HEAD", shell=True)
                call("sudo git checkout .", shell=True)
                call("sudo git clean -fdx", shell=True)
                call("sudo git pull origin master", shell=True)
            self.go_back()

        if (location == "Shutdown"):
            if (choice == "Confirm"):
                menu.render_message("", "Shutting down...", 5000)
                call("sudo shutdown -h now", shell=True)
            else: 
                self.go_back()

        if (location == "Reboot"):
            if (choice == "Confirm"):
                menu.render_message("", "Rebooting...", 5000)
                call("sudo reboot now", shell=True)
            else:
                self.go_back()

        if (location == "Skipped_notes"):
            ledsettings.skipped_notes = choice
            usersettings.change_setting_value("skipped_notes", ledsettings.skipped_notes)

        if (location == "Content"):
            menu.toggle_screensaver_settings(choice)

        if (location == "Led_animation"): 
            menu.led_animation = choice
            usersettings.change_setting_value("led_animation", choice)

    def change_value(self, value):
        if(value == "LEFT"):
            value = -1
        elif(value == "RIGHT"):
            value = 1
        if(self.currentlocation == "Brightness"):
            ledstrip.change_brightness(value*self.speed_multiplier)

        if(self.currentlocation == "Led_count"):
            ledstrip.change_led_count(value)

        if(self.currentlocation == "Shift"):
            ledstrip.change_shift(value)

        if(self.currentlocation == "Reverse"):
            ledstrip.change_reverse(value)

        if(self.currentlocation == "Backlight_Brightness"):
            if(self.current_choice == "Power"):
                ledsettings.change_backlight_brightness(value*self.speed_multiplier)
        if(self.currentlocation == "Backlight_Color"):
            ledsettings.change_backlight_color(self.current_choice, value*self.speed_multiplier)

        if(self.currentlocation == "Custom_RGB"):
            ledsettings.change_adjacent_color(self.current_choice, value*self.speed_multiplier)

        if(self.currentlocation == "RGB"):
            ledsettings.change_color(self.current_choice, value*self.speed_multiplier)
            ledsettings.color_mode = "Single"
            usersettings.change_setting_value("color_mode", ledsettings.color_mode)

        if("RGB_Color" in self.currentlocation):
            ledsettings.change_multicolor(self.current_choice, self.currentlocation, value*self.speed_multiplier)

        if("Key_range" in self.currentlocation):
            ledsettings.change_multicolor_range(self.current_choice, self.currentlocation, value*self.speed_multiplier)
            ledsettings.light_keys_in_range(self.currentlocation)            

        if(self.current_choice == "Offset"):
            ledsettings.rainbow_offset = ledsettings.rainbow_offset + value * 5 *self.speed_multiplier
        if(self.current_choice == "Scale"):
            ledsettings.rainbow_scale = ledsettings.rainbow_scale + value * 5 *self.speed_multiplier
        if(self.current_choice == "Timeshift"):
            ledsettings.rainbow_timeshift = ledsettings.rainbow_timeshift + value *self.speed_multiplier

        if(self.currentlocation == "Start_delay"):
            self.screensaver_delay = int(self.screensaver_delay) + (value*self.speed_multiplier)
            if(self.screensaver_delay < 0):
                self.screensaver_delay = 0
            usersettings.change_setting_value("screensaver_delay", self.screensaver_delay)

        if(self.currentlocation == "Turn_off_screen_delay"):
            self.screen_off_delay = int(self.screen_off_delay) + (value*self.speed_multiplier)
            if(self.screen_off_delay < 0):
                self.screen_off_delay = 0
            usersettings.change_setting_value("screen_off_delay", self.screen_off_delay)

        if(self.currentlocation == "Led_animation_delay"):
            self.led_animation_delay = int(self.led_animation_delay) + (value*self.speed_multiplier)
            if(self.led_animation_delay < 0):
                self.led_animation_delay = 0
            usersettings.change_setting_value("led_animation_delay", self.led_animation_delay)

        if(self.currentlocation == "Color_for_slow_speed"):
            ledsettings.speed_slowest[self.current_choice.lower()] +=  value*self.speed_multiplier
            if(ledsettings.speed_slowest[self.current_choice.lower()] > 255):
                ledsettings.speed_slowest[self.current_choice.lower()] = 255
            if(ledsettings.speed_slowest[self.current_choice.lower()] < 0):
                ledsettings.speed_slowest[self.current_choice.lower()] = 0
            usersettings.change_setting_value("speed_slowest_"+self.current_choice.lower(), ledsettings.speed_slowest[self.current_choice.lower()])
        
        if(self.currentlocation == "Color_for_fast_speed"):
            ledsettings.speed_fastest[self.current_choice.lower()] +=  value*self.speed_multiplier
            if(ledsettings.speed_fastest[self.current_choice.lower()] > 255):
                ledsettings.speed_fastest[self.current_choice.lower()] = 255
            if(ledsettings.speed_fastest[self.current_choice.lower()] < 0):
                ledsettings.speed_fastest[self.current_choice.lower()] = 0
            usersettings.change_setting_value("speed_fastest_"+self.current_choice.lower(), ledsettings.speed_fastest[self.current_choice.lower()])

        if(self.currentlocation == "Period"):
            ledsettings.speed_period_in_seconds +=  (value/float(10))*self.speed_multiplier
            if(ledsettings.speed_period_in_seconds < 0.1):
                ledsettings.speed_period_in_seconds = 0.1
            usersettings.change_setting_value("speed_period_in_seconds", ledsettings.speed_period_in_seconds)

        if(self.currentlocation == "Max_notes_in_period"):
            ledsettings.speed_max_notes +=  value*self.speed_multiplier
            if(ledsettings.speed_max_notes < 2):
                ledsettings.speed_max_notes = 2
            usersettings.change_setting_value("speed_max_notes", ledsettings.speed_max_notes)

        if(self.currentlocation == "Color_in_scale"):
            ledsettings.key_in_scale[self.current_choice.lower()] +=  value*self.speed_multiplier
            if(ledsettings.key_in_scale[self.current_choice.lower()] > 255):
                ledsettings.key_in_scale[self.current_choice.lower()] = 255
            if(ledsettings.key_in_scale[self.current_choice.lower()] < 0):
                ledsettings.key_in_scale[self.current_choice.lower()] = 0
            usersettings.change_setting_value("key_in_scale_"+self.current_choice.lower(), ledsettings.key_in_scale[self.current_choice.lower()])

        if(self.currentlocation == "Color_not_in_scale"):
            ledsettings.key_not_in_scale[self.current_choice.lower()] +=  value*self.speed_multiplier
            if(ledsettings.key_not_in_scale[self.current_choice.lower()] > 255):
                ledsettings.key_not_in_scale[self.current_choice.lower()] = 255
            if(ledsettings.key_not_in_scale[self.current_choice.lower()] < 0):
                ledsettings.key_not_in_scale[self.current_choice.lower()] = 0
            usersettings.change_setting_value("key_not_in_scale_"+self.current_choice.lower(), ledsettings.key_not_in_scale[self.current_choice.lower()])

        # Learn MIDI
        if (self.currentlocation == "Learn_MIDI"):
            if (self.current_choice == "Practice"):
                learning.change_practice(value)
            if (self.current_choice == "Hands"):
                learning.change_hands(value)
            if (self.current_choice == "Mute hand"):
                learning.change_mute_hand(value)
            if (self.current_choice == "Start point"):
                learning.change_start_point(value)
            if (self.current_choice == "End point"):
                learning.change_end_point(value)
            if (self.current_choice == "Set tempo"):
                learning.change_set_tempo(value)
            if(self.current_choice == "Hand color R"):
                learning.change_hand_color(value, 'RIGHT')
            if(self.current_choice == "Hand color L"):
                learning.change_hand_color(value, 'LEFT')

        menu.show()

    def speed_change(self):
        if(self.speed_multiplier == 10):
            self.speed_multiplier = 1
        elif(self.speed_multiplier == 1):
            self.speed_multiplier = 10

def play_midi(song_path):
    midiports.pending_queue.append(mido.Message('note_on'))

    if song_path in saving.is_playing_midi.keys():
        menu.render_message(song_path, "Already playing", 2000)
        return

    saving.is_playing_midi.clear()

    saving.is_playing_midi[song_path] = True
    menu.render_message("Playing: ", song_path, 2000)
    saving.t = threading.currentThread()

    output_time_last = 0
    delay_debt = 0
    try:
        mid = mido.MidiFile("Songs/"+song_path)
        fastColorWipe(ledstrip.strip, True)
        #length = mid.length
        t0 = False
        for message in mid:
            if song_path in saving.is_playing_midi.keys():
                if(t0 == False):
                    t0 = time.time()
                    output_time_start = time.time()
                output_time_last = time.time() - output_time_start
                delay_temp = message.time - output_time_last
                delay = message.time - output_time_last - float(0.003) + delay_debt
                if(delay > 0):
                    time.sleep(delay)
                    delay_debt = 0
                else:
                    delay_debt += delay_temp
                output_time_start = time.time()

                if not message.is_meta:
                    midiports.playport.send(message)
                    midiports.pending_queue.append(message.copy(time=0))

            else:
                break
        #print('play time: {:.2f} s (expected {:.2f})'.format(
                #time.time() - t0, length))
        #saving.is_playing_midi = False
    except:
        menu.render_message(song_path, "Can't play this file", 2000)

class LearnMIDI:
    def __init__(self):
        self.loading            = 0
        self.practice           = int(usersettings.get_setting_value("practice"))
        self.hands              = int(usersettings.get_setting_value("hands"))
        self.mute_hand          = int(usersettings.get_setting_value("mute_hand"))
        self.start_point        = int(usersettings.get_setting_value("start_point"))
        self.end_point          = int(usersettings.get_setting_value("end_point"))
        self.set_tempo          = int(usersettings.get_setting_value("set_tempo"))
        self.hand_colorR        = int(usersettings.get_setting_value("hand_colorR"))
        self.hand_colorL        = int(usersettings.get_setting_value("hand_colorL"))

        self.loadingList        = ['', 'Load..', 'Proces', 'Merge', 'Done', 'Error!']
        self.learningList       = ['Start', 'Stop']
        self.practiceList       = ['Melody', 'Rhythm', 'Listen']
        self.handsList          = ['Both', 'Right', 'Left']
        self.mute_handList      = ['Off', 'Right', 'Left']
        self.hand_colorList     = ast.literal_eval(usersettings.get_setting_value("hand_colorList"))

        self.song_tempo         = 500000
        self.song_tracks        = []
        self.ticks_per_beat     = 240
        self.is_loaded_midi     = {}
        self.is_started_midi    = False
        self.t                  = 0

    def change_practice(self, value):
        self.practice += value
        self.practice = clamp(self.practice, 0, len(self.practiceList)-1)
        usersettings.change_setting_value("practice", self.practice)

    def change_hands(self, value):
        self.hands += value
        self.hands = clamp(self.hands, 0, len(self.handsList)-1)
        usersettings.change_setting_value("hands", self.hands)

    def change_mute_hand(self, value):
        self.mute_hand += value
        self.mute_hand = clamp(self.mute_hand, 0, len(self.mute_handList)-1)
        usersettings.change_setting_value("mute_hand", self.mute_hand)

    def restart_learning(self):
        if (self.is_started_midi):
            self.is_started_midi = False
            self.t.join()
            self.t = threading.Thread(target=learn_midi)
            self.t.start()

    def change_start_point(self, value):
        self.start_point += 5*value
        self.start_point = clamp(self.start_point, 0, self.end_point-10)
        usersettings.change_setting_value("start_point", self.start_point)
        self.restart_learning()

    def change_end_point(self, value):
        self.end_point += 5*value
        self.end_point = clamp(self.end_point, self.start_point+10, 100)
        usersettings.change_setting_value("end_point", self.end_point)
        self.restart_learning()

    def change_set_tempo(self, value):
        self.set_tempo += 5*value
        self.set_tempo = clamp(self.set_tempo, 10, 200)
        usersettings.change_setting_value("set_tempo", self.set_tempo)

    def change_hand_color(self, value, hand):
        if (hand == 'RIGHT'):
            self.hand_colorR += value
            self.hand_colorR = clamp(self.hand_colorR, 0, len(self.hand_colorList)-1)
            usersettings.change_setting_value("hand_colorR", self.hand_colorR)
        elif (hand == 'LEFT'):
            self.hand_colorL += value
            self.hand_colorL = clamp(self.hand_colorL, 0, len(self.hand_colorList)-1)
            usersettings.change_setting_value("hand_colorL", self.hand_colorL)

# Get midi song tempo
def get_tempo(mid):
    for msg in mid:     # Search for tempo
        if msg.type == 'set_tempo':
            return msg.tempo
    return 500000       # If not found return default tempo

def load_midi(song_path):
    if song_path in learning.is_loaded_midi.keys():
        return

    learning.is_loaded_midi.clear()
    learning.is_loaded_midi[song_path] = True
    learning.loading = 1                # 1 = Load..
    learning.is_started_midi = False    # Stop current learning song
    learning.t = threading.currentThread()

    try:
        # Load the midi file
        mid = mido.MidiFile('Songs/'+song_path)

        # Get tempo and Ticks per beat
        learning.song_tempo = get_tempo(mid)
        learning.ticks_per_beat = mid.ticks_per_beat

        # Assign Tracks to different channels before merging to know the message origin
        learning.loading = 2            # 2 = Proces
        if len(mid.tracks) == 2:        # check if the midi file has only 2 Tracks
            offset = 1
        else:
            offset = 0
        for k in range(len(mid.tracks)):
            for msg in mid.tracks[k]:
                if not msg.is_meta:
                    msg.channel = k + offset
                    if (msg.type == 'note_off'):
                        msg.velocity = 0

        # Merge tracks
        learning.loading = 3            # 3 = Merge
        learning.song_tracks = mido.merge_tracks(mid.tracks)
        fastColorWipe(ledstrip.strip, True)
        learning.loading = 4            # 4 = Done
    except:
        learning.loading = 5            # 5 = Error!
        learning.is_loaded_midi.clear()

def learn_midi():
    # Preliminary checks
    if learning.is_started_midi:
        return
    if learning.loading == 0:
        menu.render_message("Load song to start", "", 1500)
        return
    elif learning.loading > 0 and learning.loading < 4:
        learning.is_started_midi = True     # Prevent restarting the Thread
        while (learning.loading > 0 and learning.loading < 4):
            time.sleep(0.1)
    if learning.loading == 4:
        learning.is_started_midi = True     # Prevent restarting the Thread
    elif learning.loading == 5:
        learning.is_started_midi = False    # Allow restarting the Thread
        return

    learning.t = threading.currentThread()

    try:
        fastColorWipe(ledstrip.strip, True)
        time_prev = time.time()
        notes_to_press = []

        start_idx   = int(learning.start_point * len(learning.song_tracks) / 100)
        end_idx     = int(learning.end_point   * len(learning.song_tracks) / 100)
        for msg in learning.song_tracks[start_idx:end_idx]:
            # Exit thread if learning is stopped
            if not learning.is_started_midi:
                break

            # Get time delay
            tDelay = mido.tick2second(msg.time, learning.ticks_per_beat, learning.song_tempo * 100 / learning.set_tempo)

            # Check notes to press
            if not msg.is_meta:
                if (tDelay > 0 and (msg.type == 'note_on' or msg.type == 'note_off') and notes_to_press and learning.practice == 0):
                    notes_pressed = []
                    while (not set(notes_to_press).issubset(notes_pressed) and learning.is_started_midi):
                        for msg_in in midiports.inport.iter_pending():
                            note = int(find_between(str(msg_in), "note=", " "))
                            if "note_off" in str(msg_in):
                                velocity = 0
                            else:
                                velocity = int(find_between(str(msg_in), "velocity=", " "))
                            if (velocity > 0):
                                if (note not in notes_pressed):
                                    notes_pressed.append(note)
                            else:
                                try:
                                    notes_pressed.remove(note)
                                except ValueError:
                                    pass    # do nothing

                    # Turn off the pressed LEDs
                    fastColorWipe(ledstrip.strip, True)     # ideally clear only pressed notes!
                    notes_to_press.clear()

            # Realize time delay, consider also the time lost during computation
            delay = max(0, tDelay - (time.time() - time_prev) - 0.003)  # 0.003 sec calibratable to acount for extra time loss
            time.sleep(delay)
            time_prev = time.time()

            # Light-up LEDs with the notes to press
            if not msg.is_meta:
                # Calculate note position on the strip and display
                if (msg.type == 'note_on' or msg.type == 'note_off'):
                    note_position = get_note_position(msg.note)
                    brightness = msg.velocity / 127
                    if (msg.channel == 1):
                        red     = int(learning.hand_colorList[learning.hand_colorR][0] * brightness)
                        green   = int(learning.hand_colorList[learning.hand_colorR][1] * brightness)
                        blue    = int(learning.hand_colorList[learning.hand_colorR][2] * brightness)
                    if (msg.channel == 2):
                        red     = int(learning.hand_colorList[learning.hand_colorL][0] * brightness)
                        green   = int(learning.hand_colorList[learning.hand_colorL][1] * brightness)
                        blue    = int(learning.hand_colorList[learning.hand_colorL][2] * brightness)
                    ledstrip.strip.setPixelColor(note_position, Color(green, red, blue))
                    ledstrip.strip.show()

                # Save notes to press
                if (msg.type == 'note_on' and msg.velocity > 0 and (msg.channel == learning.hands or learning.hands == 0)):
                    notes_to_press.append(msg.note)

                # Play selected Track
                if ((learning.hands == 1 and learning.mute_hand != 2 and msg.channel == 2) or   # send midi sound for Left hand
                    (learning.hands == 2 and learning.mute_hand != 1 and msg.channel == 1) or   # send midi sound for Right hand
                    learning.practice == 2):                                                    # send midi sound for Listen only
                    midiports.playport.send(msg)
    except Exception as e:
        learning.is_started_midi = False

def clamp(val, val_min, val_max):
    return max(val_min, min(val, val_max))

def find_between(s, start, end):
    try:
        return (s.split(start))[1].split(end)[0]
    except:
        return False

def shift(l, n):
    return l[n:] + l[:n]

# Get note position on the strip
def get_note_position(note):
    if (note > 92):
        note_offset = 2
    elif (note > 55):
        note_offset = 1
    else:
        note_offset = 0
    note_offset -= ledstrip.shift
    note_pos_raw = 2*(note - 20) - note_offset
    if (ledstrip.reverse):
        return max(0, ledstrip.led_number - note_pos_raw)
    else:
        return max(0, note_pos_raw)

def screensaver():
    delay = 0.1
    interval  = 3 / float(delay)
    i = 0
    cpu_history = [None] * int(interval)
    cpu_chart = [0] * 28
    cpu_average = 0
    
    upload = 0
    download = 0
    upload_start = 0
    download_start = 0
    
    try:
        midiports.inport.poll()
    except:
        pass
    while True:
        if((time.time() - saving.start_time) > 3600  and delay < 0.5 and menu.screensaver_is_running == False):
            delay = 0.9
            interval  = 5 / float(delay)
            cpu_history = [None] * int(interval)
            cpu_average = 0
            i = 0

        if(int(menu.screen_off_delay) > 0 and ((time.time() - saving.start_time) > (int(menu.screen_off_delay) * 60))):
            menu.screen_status = 0
            GPIO.output(24, 0)

        if(int(menu.led_animation_delay) > 0 and ((time.time() - saving.start_time) > (int(menu.led_animation_delay) * 60)) and menu.screensaver_is_running == False):
            menu.screensaver_is_running == True
            if(menu.led_animation == "Theater Chase"):
                menu.t = threading.Thread(target=theaterChase, args=(ledstrip.strip, 1))
                menu.t.start()
            if(menu.led_animation == "Breathing Slow"):
                menu.t = threading.Thread(target=breathing, args=(ledstrip.strip, 25))
                menu.t.start()
            if(menu.led_animation == "Rainbow Slow"):
                menu.t = threading.Thread(target=rainbow, args=(ledstrip.strip, 10))
                menu.t.start()
            if(menu.led_animation == "Rainbow Cycle Slow"):
                menu.t = threading.Thread(target=rainbowCycle, args=(ledstrip.strip, 10))
                menu.t.start()
            if(menu.led_animation == "Theater Chase Rainbow"):
                menu.t = threading.Thread(target=theaterChaseRainbow, args=(ledstrip.strip, 5))
                menu.t.start()
            if(menu.led_animation == "Sound of da police"):
                menu.t = threading.Thread(target=sound_of_da_police, args=(ledstrip.strip, 1))
                menu.t.start()
            if(menu.led_animation == "Scanner"):
                menu.t = threading.Thread(target=scanner, args=(ledstrip.strip, 1))
                menu.t.start()

        hour = datetime.datetime.now().strftime("%H:%M:%S")
        date = datetime.datetime.now().strftime("%d-%m-%Y")
        cpu_usage = psutil.cpu_percent()
        cpu_history[i] = cpu_usage
        cpu_chart.append(cpu_chart.pop(0))
        cpu_chart[27] = cpu_usage  

        if(i>=(int(interval) - 1)):
            i = 0
            try:
                cpu_average = sum(cpu_history) / (float(len(cpu_history) +1))
                last_cpu_average = cpu_average
            except:
                cpu_average = last_cpu_average

        if(menu.screensaver_settings["ram"] == "1"):
            ram_usage = psutil.virtual_memory()[2]
        else:
            ram_usage = 0

        if(menu.screensaver_settings["temp"] == "1"):
            try:
                temp = find_between(str(psutil.sensors_temperatures()["cpu_thermal"]), "current=", ",")
            except:
                temp = find_between(str(psutil.sensors_temperatures()["cpu-thermal"]), "current=", ",")
            temp = round(float(temp), 1)
        else:
            temp = 0

        if(menu.screensaver_settings["network_usage"] == "1"):
            upload_end = psutil.net_io_counters().bytes_sent
            download_end = psutil.net_io_counters().bytes_recv

            if upload_start:
                upload = upload_end - upload_start
                upload = upload*(1 / delay)
                upload = upload/1000000
                upload = round(upload, 2)

            if download_start:
                download = download_end - download_start
                download = download*(1 / delay)
                download = download/1000000
                download = round(download, 2)

            upload_start = upload_end
            download_start = download_end
        else:
            upload = 0
            download = 0
        if(menu.screensaver_settings["sd_card_space"] == "1"):
            card_space = psutil.disk_usage('/')
        else:
            card_space = 0

        menu.render_screensaver(hour, date, cpu_usage, round(cpu_average,1), ram_usage, temp, cpu_chart, upload, download, card_space)
        time.sleep(delay)
        i += 1
        try:
            if (str(midiports.inport.poll()) != "None"):
                menu.screensaver_is_running = False
                saving.start_time = time.time()
                menu.screen_status = 1
                GPIO.output(24, 1)
                menu.show()
                break
        except:
           pass
        if GPIO.input(KEY2) == 0:
            menu.screensaver_is_running = False
            saving.start_time = time.time()
            menu.screen_status = 1
            GPIO.output(24, 1)
            menu.show()
            break

class SaveMIDI:
    def __init__(self):
        self.isrecording = False
        self.is_playing_midi = {}
        self.start_time = time.time()

    def start_recording(self):
        self.isrecording = True
        menu.render_message("Recording started", "", 500)
        self.messages_to_save = dict()
        self.messages_to_save["main"] = []
        self.restart_time()

    def cancel_recording(self):
        self.isrecording = False
        menu.render_message("Recording canceled", "", 1500)

    def add_track(self, status, note, velocity, time_value, hex_color="main"):
        if(hex_color not in self.messages_to_save):
            self.messages_to_save[str(hex_color)] = []

        if(status == "note_off"):
            for key, note_off_message in self.messages_to_save.items():
                self.messages_to_save[key].append(["note", time_value, status, note, velocity])
        else:
            self.messages_to_save[str(hex_color)].append(["note", time_value, status, note, velocity])
            if(str(hex_color) != "main"):
                self.messages_to_save["main"].append(["note", time_value, status, note, velocity])

    def add_control_change(self, status, channel, control, value, time_value):
        self.messages_to_save["main"].append(["control_change", time_value, status, channel, control, value])

    def save(self, filename):
        for key, multicolor_track in self.messages_to_save.items():
            self.mid = MidiFile(None, None, 0, 20000)  # 20000 is a ticks_per_beat value
            self.track = MidiTrack()
            self.mid.tracks.append(self.track)
            for message in multicolor_track:
                try:
                    time_delay = message[1] - previous_message_time
                except:
                    time_delay = 0
                previous_message_time = message[1]
                if(time_delay < 0 ):
                    time_delay = 0
                if(message[0] == "note"):
                    self.track.append(Message(message[2], note=int(message[3]), velocity=int(message[4]), time=int(time_delay*40000)))
                else:
                    self.track.append(Message(message[2], channel=int(message[3]), control=int(message[4]),  value=int(message[5]), time=int(time_delay*40000)))
                self.last_note_time = message[1]

            self.mid.save('Songs/'+filename+'_'+str(key)+'.mid')

        self.messages_to_save = []
        self.isrecording = False
        menu.render_message("File saved", filename+".mid", 1500)

    def restart_time(self):
        self.start_time = time.time()

class LedSettings:
    def __init__(self):
        self.red = int(usersettings.get_setting_value("red"))
        self.green = int(usersettings.get_setting_value("green"))
        self.blue = int(usersettings.get_setting_value("blue"))
        self.mode = usersettings.get_setting_value("mode")
        self.fadingspeed = int(usersettings.get_setting_value("fadingspeed"))
        self.color_mode = usersettings.get_setting_value("color_mode")
        self.rainbow_offset = int(usersettings.get_setting_value("rainbow_offset"))
        self.rainbow_scale = int(usersettings.get_setting_value("rainbow_scale"))
        self.rainbow_timeshift = int(usersettings.get_setting_value("rainbow_timeshift"))

        self.multicolor = ast.literal_eval(usersettings.get_setting_value("multicolor"))
        self.multicolor_range = ast.literal_eval(usersettings.get_setting_value("multicolor_range"))

        menu.update_multicolor(self.multicolor)

        self.sequence_active = usersettings.get_setting_value("sequence_active")

        self.backlight_brightness = int(usersettings.get_setting_value("backlight_brightness"))
        self.backlight_brightness_percent = int(usersettings.get_setting_value("backlight_brightness_percent"))

        self.backlight_red = int(usersettings.get_setting_value("backlight_red"))
        self.backlight_green = int(usersettings.get_setting_value("backlight_green"))
        self.backlight_blue = int(usersettings.get_setting_value("backlight_blue"))

        self.adjacent_mode = usersettings.get_setting_value("adjacent_mode")
        self.adjacent_red = int(usersettings.get_setting_value("adjacent_red"))
        self.adjacent_green = int(usersettings.get_setting_value("adjacent_green"))
        self.adjacent_blue = int(usersettings.get_setting_value("adjacent_blue"))

        self.skipped_notes = usersettings.get_setting_value("skipped_notes")

        self.notes_in_last_period = []
        self.speed_period_in_seconds = 0.8

        self.speed_slowest = {}
        self.speed_slowest["red"] = int(usersettings.get_setting_value("speed_slowest_red"))
        self.speed_slowest["green"] = int(usersettings.get_setting_value("speed_slowest_green"))
        self.speed_slowest["blue"] = int(usersettings.get_setting_value("speed_slowest_blue"))

        self.speed_fastest = {}
        self.speed_fastest["red"] = int(usersettings.get_setting_value("speed_fastest_red"))
        self.speed_fastest["green"] = int(usersettings.get_setting_value("speed_fastest_green"))
        self.speed_fastest["blue"] = int(usersettings.get_setting_value("speed_fastest_blue"))

        self.speed_period_in_seconds = float(usersettings.get_setting_value("speed_period_in_seconds"))
        self.speed_max_notes = int(usersettings.get_setting_value("speed_max_notes"))

        self.key_in_scale = {}
        self.key_in_scale["red"] = int(usersettings.get_setting_value("key_in_scale_red"))
        self.key_in_scale["green"] = int(usersettings.get_setting_value("key_in_scale_green"))
        self.key_in_scale["blue"] = int(usersettings.get_setting_value("key_in_scale_blue"))

        self.key_not_in_scale = {}
        self.key_not_in_scale["red"] = int(usersettings.get_setting_value("key_not_in_scale_red"))
        self.key_not_in_scale["green"] = int(usersettings.get_setting_value("key_not_in_scale_green"))
        self.key_not_in_scale["blue"] = int(usersettings.get_setting_value("key_not_in_scale_blue"))

        self.scales = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B" ]
        self.scale_key = int(usersettings.get_setting_value("scale_key"))

    def addcolor(self):
        self.multicolor.append([0, 255, 0])
        self.multicolor_range.append([20, 108])

        usersettings.change_setting_value("multicolor", self.multicolor)
        usersettings.change_setting_value("multicolor_range", self.multicolor_range)

        menu.update_multicolor(self.multicolor)

    def deletecolor(self, key):
        del self.multicolor[int(key) - 1]
        del self.multicolor_range[int(key) - 1]

        usersettings.change_setting_value("multicolor", self.multicolor)
        usersettings.change_setting_value("multicolor_range", self.multicolor_range)
        
        menu.update_multicolor(self.multicolor)
        menu.go_back()

    def change_multicolor(self, choice, location, value):
        self.sequence_active = False
        location = location.replace('RGB_Color','')
        location = int(location) - 1
        if(choice == "Red"):
            choice = 0
        elif(choice == "Green"):
            choice = 1
        else:
            choice = 2
        self.multicolor[int(location)][choice] += int(value)
        self.multicolor[int(location)][choice] = clamp(self.multicolor[int(location)][choice], 0, 255)

        usersettings.change_setting_value("multicolor", self.multicolor)

    def change_multicolor_range(self, choice, location, value):
        location = location.replace('Key_range','')
        location = int(location) - 1
        if(choice == "Start"):
            choice = 0
        else:
            choice = 1

        self.multicolor_range[int(location)][choice] += int(value)
        usersettings.change_setting_value("multicolor_range", self.multicolor_range)

    def get_multicolors(self, number):
        number = int(number) - 1
        return str(self.multicolor[int(number)][0])+", "+str(self.multicolor[int(number)][1])+", "+str(self.multicolor[int(number)][2])

    def get_random_multicolor_in_range(self, note):
        temporary_multicolor = []
        i = 0
        for range in self.multicolor_range:
            if(note >= range[0] and note <= range[1]):
                temporary_multicolor.append(self.multicolor[i])
            i += 1
        try:
            choosen_color = random.choice(temporary_multicolor)
        except:
            choosen_color = [0, 0, 0]
        return choosen_color

    def light_keys_in_range(self, location):
        fastColorWipe(ledstrip.strip, True)

        color_counter = 0
        for i in self.multicolor:

            start = self.multicolor_range[int(color_counter)][0]
            end = self.multicolor_range[int(color_counter)][1]

            if(start > 92):
                note_offset_start = 2
            elif(start > 55):
                note_offset_start = 1
            else:
                note_offset_start = 0

            if(end > 92):
                note_offset_end = 2
            elif(end > 55):
                note_offset_end = 1
            else:
                note_offset_end = 0

            red = self.multicolor[int(color_counter)][0]
            green = self.multicolor[int(color_counter)][1]
            blue = self.multicolor[int(color_counter)][2]
            
            ledstrip.strip.setPixelColor(int(((start - 20)*2 - note_offset_start)), Color(int(green), int(red), int(blue)))
            ledstrip.strip.setPixelColor(int(((end - 20)*2 - note_offset_end)), Color(int(green), int(red), int(blue)))

            color_counter += 1

    def change_color(self, color, value):
        self.sequence_active = False
        usersettings.change_setting_value("sequence_active", self.sequence_active)
        self.color_mode = "Single"
        usersettings.change_setting_value("color_mode", self.color_mode)
        if(color == "Red"):
            if(self.red <= 255 and self.red >= 0):
                self.red += int(value)
                self.red = clamp(self.red, 0, 255)
                usersettings.change_setting_value("red", self.red)
        elif(color == "Green"):
            if(self.green <= 255 and self.green >= 0):
                self.green += int(value)
                self.green = clamp(self.green, 0, 255)
                usersettings.change_setting_value("green", self.green)
        elif(color == "Blue"):
            if(self.blue <= 255 and self.blue >= 0):
                self.blue += int(value)
                self.blue = clamp(self.blue, 0, 255)
                usersettings.change_setting_value("blue", self.blue)
    def change_color_name(self, color):
        self.sequence_active = False
        usersettings.change_setting_value("sequence_active", self.sequence_active)
        self.color_mode = "Single"
        usersettings.change_setting_value("color_mode", self.color_mode)
        self.red = int(find_between(str(color), "red=", ","))
        self.green = int(find_between(str(color), "green=", ","))
        self.blue = int(find_between(str(color), "blue=", ")"))

        usersettings.change_setting_value("red", self.red)
        usersettings.change_setting_value("green", self.green)
        usersettings.change_setting_value("blue", self.blue)
    def get_color(self, color):
        if(color == "Red"):
            return self.red
        elif(color == "Green"):
            return self.green
        elif(color == "Blue"):
            return self.blue
    def get_colors(self):
        return str(self.red)+", "+str(self.green)+", "+str(self.blue)

    def get_backlight_color(self, color):
        if(color == "Red"):
            return self.backlight_red
        elif(color == "Green"):
            return self.backlight_green
        elif(color == "Blue"):
            return self.backlight_blue
    def get_backlight_colors(self):
        return str(self.backlight_red)+", "+str(self.backlight_green)+", "+str(self.backlight_blue)

    def get_adjacent_color(self, color):
        if(color == "Red"):
            return self.adjacent_red
        elif(color == "Green"):
            return self.adjacent_green
        elif(color == "Blue"):
            return self.adjacent_blue
    def get_adjacent_colors(self):
        return str(self.adjacent_red)+", "+str(self.adjacent_green)+", "+str(self.adjacent_blue)

    def set_sequence(self, sequence, step):
        try:
            if(step != 1):
                self.step_number = 1
                self.sequences_tree = minidom.parse("sequences.xml")

                self.sequence_number = str(sequence + 1)

                self.next_step = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("next_step")[0].firstChild.nodeValue
                self.control_number = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("control_number")[0].firstChild.nodeValue
                self.count_steps = 1
                self.sequence_active = True
                while(True):
                    try:
                        temp_step = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.count_steps))[0].getElementsByTagName("color")[0].firstChild.nodeValue
                        self.count_steps += 1
                    except:
                        self.count_steps -= 1
                        break
            else:
                #print("step_number: "+str(self.step_number)+" count steps: "+str(self.count_steps))
                self.step_number += 1
                if(self.step_number > self.count_steps):
                    self.step_number = 1

            self.color_mode = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("color")[0].firstChild.nodeValue
            self.mode = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("light_mode")[0].firstChild.nodeValue

            if(self.mode == "Velocity" or self.mode == "Fading"):
                self.fadingspeed = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("speed")[0].firstChild.nodeValue
                if(self.mode == "Fading"): 
                    if(self.fadingspeed == "Very fast"):
                        self.fadingspeed = 50
                    elif(self.fadingspeed == "Fast"):
                        self.fadingspeed = 40
                    elif(self.fadingspeed == "Medium"):
                        self.fadingspeed = 20
                    elif(self.fadingspeed == "Slow"):
                        self.fadingspeed = 10
                    elif(self.fadingspeed == "Very slow"):
                        self.fadingspeed = 2
                    elif (self.fadingspeed == "Instant"):
                        self.fadingspeed = 1000

                if(self.mode == "Velocity"):
                    if(self.fadingspeed == "Fast"):
                        self.fadingspeed = 10
                    elif(self.fadingspeed == "Medium"):
                        self.fadingspeed = 8
                    elif(self.fadingspeed == "Slow"):
                        self.fadingspeed = 6
                    elif(self.fadingspeed == "Very slow"):
                        self.fadingspeed = 3
            if(self.color_mode == "RGB"):
                self.color_mode = "Single"
                self.red = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Red")[0].firstChild.nodeValue)
                self.green = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Green")[0].firstChild.nodeValue)
                self.blue = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Blue")[0].firstChild.nodeValue)

            if(self.color_mode == "Rainbow"):
                self.rainbow_offset = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Offset")[0].firstChild.nodeValue)
                self.rainbow_scale = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Scale")[0].firstChild.nodeValue)
                self.rainbow_timeshift = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("Timeshift")[0].firstChild.nodeValue)

            if(self.color_mode == "Speed"):
                self.speed_slowest["red"] = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("speed_slowest_red")[0].firstChild.nodeValue)
                self.speed_slowest["green"] = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("speed_slowest_green")[0].firstChild.nodeValue)
                self.speed_slowest["blue"] = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("speed_slowest_blue")[0].firstChild.nodeValue)

                self.speed_fastest["red"] = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("speed_fastest_red")[0].firstChild.nodeValue)
                self.speed_fastest["green"] = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("speed_fastest_green")[0].firstChild.nodeValue)
                self.speed_fastest["blue"] = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("speed_fastest_blue")[0].firstChild.nodeValue)

                self.speed_period_in_seconds = float(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("speed_period_in_seconds")[0].firstChild.nodeValue)
                self.speed_max_notes = int(self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("speed_max_notes")[0].firstChild.nodeValue)

            if(self.color_mode == "Multicolor"):
                self.multicolor = []
                self.multicolor_range = []
                multicolor_number = 1
                multicolor_range_number = 1
                while(True):
                    try:
                        colors = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("color_"+str(multicolor_number))[0].firstChild.nodeValue
                        colors = colors.split(',')
                        red = colors[0].replace(" ", "")
                        green = colors[1].replace(" ", "")
                        blue = colors[2].replace(" ", "")
                        self.multicolor.append([int(red), int(green), int(blue)])
                        multicolor_number += 1
                    except:
                        break
                while(True):
                    try:
                        colors_range = self.sequences_tree.getElementsByTagName("sequence_"+str(self.sequence_number))[0].getElementsByTagName("step_"+str(self.step_number))[0].getElementsByTagName("color_range_"+str(multicolor_range_number))[0].firstChild.nodeValue
                        colors_range = colors_range.split(',')
                        start = colors_range[0].replace(" ", "")
                        end = colors_range[1].replace(" ", "")
                        self.multicolor_range.append([int(start), int(end)])
                        multicolor_range_number += 1
                    except:
                        break
        except:
            return False

    def change_backlight_brightness(self, value):
        self.backlight_brightness_percent += value
        self.backlight_brightness_percent = clamp(self.backlight_brightness_percent, 0, 100)
        self.backlight_brightness = 255 * self.backlight_brightness_percent / 100 
        usersettings.change_setting_value("backlight_brightness", int(self.backlight_brightness))
        usersettings.change_setting_value("backlight_brightness_percent", self.backlight_brightness_percent)
        fastColorWipe(ledstrip.strip, True)

    def change_backlight_color(self, color, value):
        if(color == "Red"):
            if(self.backlight_red <= 255 and self.backlight_red >= 0):
                self.backlight_red += int(value)
                self.backlight_red = clamp(self.backlight_red, 0, 255)
        elif(color == "Green"):
            if(self.backlight_green <= 255 and self.backlight_green >= 0):
                self.backlight_green += int(value)
                self.backlight_green = clamp(self.backlight_green, 0, 255)
        elif(color == "Blue"):
            if(self.backlight_blue <= 255 and self.backlight_blue >= 0):
                self.backlight_blue += int(value)
                self.backlight_blue = clamp(self.backlight_blue, 0, 255)
        usersettings.change_setting_value("backlight_red", self.backlight_red)
        usersettings.change_setting_value("backlight_green", self.backlight_green)
        usersettings.change_setting_value("backlight_blue", self.backlight_blue)

        fastColorWipe(ledstrip.strip, True)

    def change_adjacent_color(self, color, value):
        self.adjacent_mode = "RGB"
        usersettings.change_setting_value("adjacent_mode", self.adjacent_mode)
        if(color == "Red"):
            if(self.adjacent_red <= 255 and self.adjacent_red >= 0):
                self.adjacent_red += int(value)
                self.adjacent_red = clamp(self.adjacent_red, 0, 255)
        elif(color == "Green"):
            if(self.adjacent_green <= 255 and self.adjacent_green >= 0):
                self.adjacent_green += int(value)
                self.adjacent_green = clamp(self.adjacent_green, 0, 255)
        elif(color == "Blue"):
            if(self.adjacent_blue <= 255 and self.adjacent_blue >= 0):
                self.adjacent_blue += int(value)
                self.adjacent_blue = clamp(self.adjacent_blue, 0, 255)
        usersettings.change_setting_value("adjacent_red", self.adjacent_red)
        usersettings.change_setting_value("adjacent_green", self.adjacent_green)
        usersettings.change_setting_value("adjacent_blue", self.adjacent_blue)
        fastColorWipe(ledstrip.strip, True)

    def speed_add_note(self):
        current_time = time.time()
        self.notes_in_last_period.append(current_time)

    def speed_get_colors(self):
        for note_time in self.notes_in_last_period[:]:
            if ((time.time() - self.speed_period_in_seconds) > note_time):
                self.notes_in_last_period.remove(note_time)

        notes_count = len(self.notes_in_last_period)
        max_notes = self.speed_max_notes
        speed_percent = notes_count / float(max_notes)

        if(notes_count > max_notes):
            red = self.speed_fastest["red"]
            green = self.speed_fastest["green"]
            blue = self.speed_fastest["blue"]
        else:
            red = ((self.speed_fastest["red"]- self.speed_slowest["red"]) * float(speed_percent)) + self.speed_slowest["red"]
            green = ((self.speed_fastest["green"] - self.speed_slowest["green"]) * float(speed_percent)) + self.speed_slowest["green"]
            blue = ((self.speed_fastest["blue"] - self.speed_slowest["blue"]) * float(speed_percent)) + self.speed_slowest["blue"]
        return[round(red), round(green), round(blue)]

class MidiPorts():
    def __init__(self):
        self.pending_queue = []

        # checking if the input port was previously set by the user
        port = usersettings.get_setting_value("input_port")
        if (port != "default"):
            try:
                self.inport = mido.open_input(port)
                print("Inport loaded and set to " + port)
            except:
                print("Can't load input port: " + port)
        else :
            # if not, try to find the new midi port
            try:
                for port in mido.get_input_names():
                    if "Through" not in port and "RPi" not in port and "RtMidOut" not in port and "USB-USB" not in port:
                        self.inport =  mido.open_input(port)
                        usersettings.change_setting_value("input_port", port)
                        print("Inport set to "+port)
                        break
            except:
                print ("no input port")

        try:
            for port in mido.get_output_names():
                if "Through" not in port and "RPi" not in port and "RtMidOut" not in port and "USB-USB" not in port:
                    self.playport =  mido.open_output(port)
                    print("playport set to "+port)
                    break
        except:
            print("no playback port")

        self.portname = "inport"

    def change_port(self, port, portname):
        try:
            if(port == "inport"):
                self.inport =  mido.open_input(portname)
                usersettings.change_setting_value("input_port", portname)
            elif(port == "playport"):
                self.playport =  mido.open_output(portname)
            menu.render_message("Changing "+port+" to:", portname, 1500)
        except:
            menu.render_message("Can't change "+port+" to:", portname, 1500)

usersettings    = UserSettings()
midiports       = MidiPorts()
ledstrip        = LedStrip()
menu            = MenuLCD("menu.xml")
menu.show()
saving          = SaveMIDI()
learning        = LearnMIDI()
ledsettings     = LedSettings()

z = 0
display_cycle = 0
screen_hold_time = 16

last_activity = time.time()

last_control_change = 0
pedal_deadzone = 10
timeshift_start = time.time()

fastColorWipe(ledstrip.strip, True)

while True:
    #screensaver
    if(int(menu.screensaver_delay) > 0):
        if((time.time() - last_activity) > (int(menu.screensaver_delay) * 60)):
            screensaver()
    try:
            elapsed_time = time.time() - saving.start_time
    except:
            elapsed_time = 0
    if(display_cycle >= 3):
        display_cycle = 0

        if(elapsed_time > screen_hold_time):
            menu.show()
            timeshift_start = time.time()
    display_cycle += 1
    
    if((time.time() - last_activity) > 1):
        usersettings.save_changes()
        if(usersettings.pending_reset == True):
            usersettings.pending_reset = False
            ledstrip = LedStrip()
            menu = MenuLCD("menu.xml")
            menu.show()
            ledsettings = LedSettings()

    if GPIO.input(KEYUP) == 0:
        last_activity = time.time()
        menu.change_pointer(0)
        while GPIO.input(KEYUP) == 0:
            time.sleep(0.001)
    if GPIO.input(KEYDOWN) == 0:
        last_activity = time.time()
        menu.change_pointer(1)
        while GPIO.input(KEYDOWN) == 0:
            time.sleep(0.001)
    if GPIO.input(KEY1) == 0:
        last_activity = time.time()
        menu.enter_menu()
        while GPIO.input(KEY1) == 0:
            time.sleep(0.001)
    if GPIO.input(KEY2) == 0:
        last_activity = time.time()
        menu.go_back()
        if(menu.screensaver_is_running == False):
            fastColorWipe(ledstrip.strip, True)
        while GPIO.input(KEY2) == 0:
            time.sleep(0.01)
    if GPIO.input(KEY3) == 0:
        last_activity = time.time()
        if(ledsettings.sequence_active == True):
            ledsettings.set_sequence(0, 1)
        while GPIO.input(KEY3) == 0:
            time.sleep(0.01)
    if GPIO.input(KEYLEFT) == 0:
        last_activity = time.time()
        menu.change_value("LEFT")
        time.sleep(0.1)
    if GPIO.input(KEYRIGHT) == 0:
        last_activity = time.time()
        menu.change_value("RIGHT")
        time.sleep(0.1)
    if GPIO.input(JPRESS) == 0:
        last_activity = time.time()
        menu.speed_change()
        while GPIO.input(JPRESS) == 0:
            time.sleep(0.01)

    red = ledsettings.get_color("Red")
    green = ledsettings.get_color("Green")
    blue = ledsettings.get_color("Blue")

    timeshift = (time.time() - timeshift_start) * ledsettings.rainbow_timeshift

    if(ledsettings.mode == "Fading" or ledsettings.mode == "Velocity"):
        n = 0
        for note in ledstrip.keylist:
            if(ledsettings.color_mode == "Multicolor"):
                try:
                    red = ledstrip.keylist_color[n][0]
                    green = ledstrip.keylist_color[n][1]
                    blue = ledstrip.keylist_color[n][2]
                except:
                    pass

            if(ledsettings.color_mode == "Rainbow"):
                red = get_rainbow_colors(int((int(n) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale)/ 100)) & 255, "red")
                green = get_rainbow_colors(int((int(n) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale) / 100)) & 255, "green")
                blue = get_rainbow_colors(int((int(n) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale)/ 100)) & 255, "blue")

                if (int(note) == 1001):
                    ledstrip.strip.setPixelColor((n), Color(int(green), int(red), int(blue)))
                    ledstrip.set_adjacent_colors(n, Color(int(green), int(red), int(blue)), False)

            if(ledsettings.color_mode == "Speed"):
                speed_colors = ledsettings.speed_get_colors()
                red = speed_colors[0]
                green = speed_colors[1]
                blue = speed_colors[2]

            if(ledsettings.color_mode == "Scale"):
                try:
                    red = ledstrip.keylist_color[n][0]
                    green = ledstrip.keylist_color[n][1]
                    blue = ledstrip.keylist_color[n][2]
                except:
                    pass

            if(int(note) != 1001):
                if(int(note) > 0):
                    fading = (note / float(100)) / 10
                    ledstrip.strip.setPixelColor((n), Color(int(int(green) * fading), int(int(red) * fading), int(int(blue) * fading)))
                    ledstrip.set_adjacent_colors(n, Color(int(int(green) * fading), int(int(red) * fading), int(int(blue) * fading)), False)
                    ledstrip.keylist[n] = ledstrip.keylist[n] - ledsettings.fadingspeed
                    if(ledstrip.keylist[n] <= 0):
                        red_fading = int(ledsettings.get_backlight_color("Red")) * float(ledsettings.backlight_brightness_percent) / 100
                        green_fading = int(ledsettings.get_backlight_color("Green")) * float(ledsettings.backlight_brightness_percent) / 100
                        blue_fading = int(ledsettings.get_backlight_color("Blue")) * float(ledsettings.backlight_brightness_percent) / 100
                        color = Color(int(green_fading),int(red_fading),int(blue_fading))
                        ledstrip.strip.setPixelColor((n), color)
                        ledstrip.set_adjacent_colors(n, color, False)
                else:
                    ledstrip.keylist[n] = 0

            if(ledsettings.mode == "Velocity"):
                if(int(last_control_change) < pedal_deadzone):
                    if(int(ledstrip.keylist_status[n]) == 0):
                        red_fading = int(ledsettings.get_backlight_color("Red"))* float(ledsettings.backlight_brightness_percent) / 100
                        green_fading = int(ledsettings.get_backlight_color("Green")) * float(ledsettings.backlight_brightness_percent) / 100
                        blue_fading = int(ledsettings.get_backlight_color("Blue")) * float(ledsettings.backlight_brightness_percent) / 100
                        color = Color(int(green_fading),int(red_fading),int(blue_fading))
                        ledstrip.strip.setPixelColor((n), color)
                        ledstrip.set_adjacent_colors(n, color, False)
                        ledstrip.keylist[n] = 0
            n += 1
    try:
        if(len(saving.is_playing_midi) == 0 and learning.is_started_midi == False):
            midiports.midipending = midiports.inport.iter_pending()
        else:
            midiports.midipending = midiports.pending_queue
    except:
        continue
    #loop through incoming midi messages
    for msg in midiports.midipending:
        last_activity = time.time()
        note = find_between(str(msg), "note=", " ")
        original_note = note
        note = int(note)
        if "note_off" in str(msg):
            velocity = 0
        else:
            velocity = find_between(str(msg), "velocity=", " ")

        control_change = find_between(str(msg), "value=", " ")
        if(control_change != False):
            last_control_change = control_change

            if(ledsettings.sequence_active == True):

                control = find_between(str(msg), "control=", " ")
                value = find_between(str(msg), "value=", " ")
                try:
                    if("+" in ledsettings.next_step):
                        if(int(value) > int(ledsettings.next_step) and control == ledsettings.control_number):
                            ledsettings.set_sequence(0, 1)
                    else:
                        if(int(value) < int(ledsettings.next_step) and control == ledsettings.control_number):
                            ledsettings.set_sequence(0, 1)
                except:
                    pass

        #changing offset to adjust the distance between the LEDs to the key spacing
        note_position = get_note_position(note)

        if((note_position > ledstrip.led_number or note_position < 0) and control_change == False):
            continue

        elapsed_time = time.time() - saving.start_time

        if(ledsettings.color_mode == "Rainbow"):
            red = get_rainbow_colors(int((int((note_position)) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale)/ 100)) & 255, "red")
            green = get_rainbow_colors(int((int((note_position)) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale) / 100)) & 255, "green")
            blue = get_rainbow_colors(int((int((note_position)) + ledsettings.rainbow_offset + int(timeshift)) * (float(ledsettings.rainbow_scale)/ 100)) & 255, "blue") 

        if(ledsettings.color_mode == "Speed"):
            speed_colors = ledsettings.speed_get_colors()
            red = speed_colors[0]
            green = speed_colors[1]
            blue = speed_colors[2]

        if (ledsettings.color_mode == "Scale"):
            scale_colors = get_scale_color(ledsettings.scale_key, note)
            red = scale_colors[0]
            green = scale_colors[1]
            blue = scale_colors[2]
            ledstrip.keylist_color[note_position] = scale_colors

        if(int(velocity) == 0 and int(note) > 0):                   # when a note is lifted (off)
            ledstrip.keylist_status[note_position] = 0
            if(ledsettings.mode == "Fading"):
                ledstrip.keylist[note_position] = 1000
            elif(ledsettings.mode == "Velocity"):
                if(int(last_control_change) < pedal_deadzone):
                    ledstrip.keylist[note_position] = 0
            else:
                if(ledsettings.backlight_brightness > 0):
                    red_backlight = int(ledsettings.get_backlight_color("Red"))* (ledsettings.backlight_brightness_percent) / 100
                    green_backlight = int(ledsettings.get_backlight_color("Green")) * (ledsettings.backlight_brightness_percent) / 100
                    blue_backlight = int(ledsettings.get_backlight_color("Blue")) * (ledsettings.backlight_brightness_percent) / 100
                    color_backlight = Color(int(green_backlight),int(red_backlight),int(blue_backlight))
                    ledstrip.strip.setPixelColor((note_position), color_backlight)
                    ledstrip.set_adjacent_colors((note_position), color_backlight, True)
                else:
                    ledstrip.strip.setPixelColor((note_position), Color(0, 0, 0))
                    ledstrip.set_adjacent_colors((note_position), Color(0, 0, 0), False)
            if(saving.isrecording == True):
                saving.add_track("note_off", original_note, velocity, last_activity)
        elif(int(velocity) > 0 and int(note) > 0):                  # when a note is pressed
            ledsettings.speed_add_note()
            if(ledsettings.color_mode == "Multicolor"):
                choosen_color = ledsettings.get_random_multicolor_in_range(note)
                red = choosen_color[0]
                green = choosen_color[1]
                blue = choosen_color[2]
                ledstrip.keylist_color[note_position] = [red, green, blue]

            ledstrip.keylist_status[note_position] = 1
            if(ledsettings.mode == "Velocity"):
                brightness = (100 / (float(velocity) / 127 ) )/ 100
            else:
                brightness = 1
            if(ledsettings.mode == "Fading"):
                ledstrip.keylist[note_position] = 1001
            if(ledsettings.mode == "Velocity"):
                ledstrip.keylist[note_position] = 1000/float(brightness)
            if(find_between(str(msg), "channel=", " ") == "12"):
                if(ledsettings.skipped_notes != "Finger-based"):
                    ledstrip.strip.setPixelColor((note_position), Color(255, 0, 0))
            elif(find_between(str(msg), "channel=", " ") == "11"):
                if(ledsettings.skipped_notes != "Finger-based"):
                    ledstrip.strip.setPixelColor((note_position), Color(0, 0, 255))
            else:
                if(ledsettings.skipped_notes != "Normal"):
                    ledstrip.strip.setPixelColor((note_position), Color(int(int(green)/float(brightness)), int(int(red)/float(brightness)), int(int(blue)/float(brightness))))
                    ledstrip.set_adjacent_colors((note_position), Color(int(int(green)/float(brightness)), int(int(red)/float(brightness)), int(int(blue)/float(brightness))), False)
            if(saving.isrecording == True):
                if (ledsettings.color_mode == "Multicolor"):
                    saving.add_track("note_on", original_note, velocity, last_activity, wc.rgb_to_hex((red,green,blue)))
                else:
                    saving.add_track("note_on", original_note, velocity, last_activity)
        else:
            control = find_between(str(msg), "control=", " ")
            value = find_between(str(msg), "value=", " ")
            if(saving.isrecording == True):
                saving.add_control_change("control_change", 0, control, value, last_activity)
        saving.restart_time()
        if(len(saving.is_playing_midi) > 0):
            midiports.pending_queue.remove(msg)
    ledstrip.strip.show()
