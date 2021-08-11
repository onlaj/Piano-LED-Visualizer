import argparse
from lib.functions import *


class LedStrip:
    def __init__(self, usersettings, ledsettings):
        self.usersettings = usersettings
        self.ledsettings = ledsettings

        self.brightness_percent = int(self.usersettings.get_setting_value("brightness_percent"))
        self.led_number = int(self.usersettings.get_setting_value("led_count"))
        self.shift = int(self.usersettings.get_setting_value("shift"))
        self.reverse = int(self.usersettings.get_setting_value("reverse"))

        self.brightness = 255 * self.brightness_percent / 100

        self.keylist = [0] * self.led_number
        self.keylist_status = [0] * self.led_number
        self.keylist_color = [0] * self.led_number

        # LED strip configuration:
        self.LED_COUNT = int(self.led_number)  # Number of LED pixels.
        self.LED_PIN = 18  # GPIO pin connected to the pixels (18 uses PWM!).
        # LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
        self.LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
        self.LED_DMA = 10  # DMA channel to use for generating signal (try 10)
        self.LED_BRIGHTNESS = int(self.brightness)  # Set to 0 for darkest and 255 for brightest
        self.LED_INVERT = False  # True to invert the signal (when using NPN transistor level shift)
        self.LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53

        # Create NeoPixel object with appropriate configuration.
        self.strip = Adafruit_NeoPixel(self.LED_COUNT, self.LED_PIN, self.LED_FREQ_HZ, self.LED_DMA, self.LED_INVERT,
                                       self.LED_BRIGHTNESS, self.LED_CHANNEL)
        # Intialize the library (must be called once before other functions).
        self.strip.begin()

    def change_brightness(self, value, ispercent=False):
        if ispercent:
            self.brightness_percent = value
        else:
            self.brightness_percent += value
        self.brightness_percent = clamp(self.brightness_percent, 1, 100)
        self.brightness = 255 * self.brightness_percent / 100

        self.usersettings.change_setting_value("brightness_percent", self.brightness_percent)

        self.strip.setBrightness(int(self.brightness))

    def change_led_count(self, value, fixed_number=False):
        if fixed_number:
            self.led_number = value
        else:
            self.led_number += value
        self.led_number = max(1, self.led_number)

        self.usersettings.change_setting_value("led_count", self.led_number)

        self.keylist = [0] * self.led_number
        self.keylist_status = [0] * self.led_number
        self.keylist_color = [0] * self.led_number

        self.strip = Adafruit_NeoPixel(int(self.led_number), self.LED_PIN, self.LED_FREQ_HZ, self.LED_DMA,
                                       self.LED_INVERT, int(self.brightness), self.LED_CHANNEL)
        # Intialize the library (must be called once before other functions).
        self.strip.begin()

    def change_shift(self, value, fixed_number=False):
        if fixed_number:
            self.shift = value
        else:
            self.shift += value
        self.usersettings.change_setting_value("shift", self.shift)

    def change_reverse(self, value, fixed_number=False):
        if fixed_number:
            self.reverse = value
        else:
            self.reverse += value
        self.reverse = clamp(self.reverse, 0, 1)
        self.usersettings.change_setting_value("reverse", self.reverse)

    def set_adjacent_colors(self, note, color, led_turn_off):
        if self.ledsettings.adjacent_mode == "RGB" and color != 0 and led_turn_off != True:
            color = Color(int(self.ledsettings.adjacent_green), int(self.ledsettings.adjacent_red),
                          int(self.ledsettings.adjacent_blue))
        if self.ledsettings.adjacent_mode != "Off":
            self.strip.setPixelColor(int(note) + 1, color)
            self.strip.setPixelColor(int(note) - 1, color)
