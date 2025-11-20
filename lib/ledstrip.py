from lib.functions import *
import lib.colormaps as cmap
from lib.rpi_drivers import PixelStrip, ws
from lib.LED_drivers import PixelStrip_Emu
from lib.log_setup import logger

class LedStrip:
    def __init__(self, usersettings, ledsettings, driver="rpi_ws281x"):
        self.usersettings = usersettings
        self.ledsettings = ledsettings
        self.driver = driver

        self.brightness_percent = int(self.usersettings.get_setting_value("brightness_percent"))
        self.led_number = int(self.usersettings.get_setting_value("led_count"))
        self.leds_per_meter = int(self.usersettings.get_setting_value("leds_per_meter"))
        self.shift = int(self.usersettings.get_setting_value("shift"))
        self.reverse = int(self.usersettings.get_setting_value("reverse"))

        self.brightness = 255 * self.brightness_percent / 100
        self.led_gamma = float(usersettings.get_setting_value("led_gamma"))

        # Hold individual led state information, initialized in init_strip()
        self.keylist = None
        self.keylist_status = None
        self.keylist_color = None

        self.current_fps = 0

        # LED strip configuration:
        #self.LED_COUNT = int(self.led_number)  # Number of LED pixels.
        # Read LED pin and channel from settings, with fallback to defaults
        try:
            self.LED_PIN = int(self.usersettings.get_setting_value("led_pin"))
        except (ValueError, TypeError):
            self.LED_PIN = 18  # Default GPIO pin (18 uses PWM!)
        # LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
        self.LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
        self.LED_DMA = 10  # DMA channel to use for generating signal (try 10)
        #self.LED_BRIGHTNESS = int(self.brightness)  # Set to 0 for darkest and 255 for brightest
        self.LED_INVERT = False  # True to invert the signal (when using NPN transistor level shift)
        try:
            self.LED_CHANNEL = int(self.usersettings.get_setting_value("led_channel"))
        except (ValueError, TypeError):
            self.LED_CHANNEL = 0  # Default channel (set to '1' for GPIOs 13, 19, 41, 45 or 53)

        self.WEBEMU_FPS = 10

        self.init_strip()

    def init_strip(self):
        self.keylist = [0] * self.led_number
        self.keylist_status = [0] * self.led_number
        self.keylist_color = [0] * self.led_number
        self.keylist_sustained = [0] * self.led_number  # Track notes sustained by pedal
        self.active_pulses = [] # For Pulse mode


        if self.driver == "rpi_ws281x":
            try:
                # Create NeoPixel object with appropriate configuration.
                self.strip = PixelStrip(int(self.led_number), self.LED_PIN, self.LED_FREQ_HZ, self.LED_DMA, self.LED_INVERT,
                                            int(self.brightness), self.LED_CHANNEL, ws.WS2811_STRIP_GRB)
                # Intialize the library (must be called once before other functions).
                self.strip.begin()
                if "releaseGIL" in dir(self.strip):
                    self.strip.releaseGIL()
                self.change_gamma(self.led_gamma)
            except Exception as e:
                logger.warning(e)

                if isinstance(e, RuntimeError):
                    # rpi_ws281x registers _cleanup() atexit, but if it's not initialized ws2811_fini will segfault.
                    # Manually clean up memory, then bypass _cleanup() using knowledge that _cleanup() checks _leds first
                    logger.info("Cleaning up ws281x instance.")
                    ws.delete_ws2811_t(self.strip._leds)
                    self.strip._leds = None

                logger.info("Failed to load LED strip.  Using emu driver.")
                self.strip = PixelStrip_Emu(int(self.led_number))
                self.driver = "emu"
        elif self.driver == "emu":
            self.strip = PixelStrip_Emu(int(self.led_number))


    def change_gamma(self, value):
        self.led_gamma = float(value)
        if 0.01 <= self.led_gamma <= 10.0:
            if self.driver == "rpi_ws281x":
                # rpi_ws281x.py interface has no ported method to set gamma by factor, using direct ws
                ws.ws2811_set_custom_gamma_factor(self.strip._leds, self.led_gamma)

            # Rebuild colormaps
            cmap.generate_colormaps(cmap.gradients, self.led_gamma)

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

        self.init_strip()

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

    def set_adjacent_colors(self, note, color, led_turn_off, fading=1):
        if self.ledsettings.adjacent_mode == "RGB" and color != 0 and led_turn_off is not True:
            color = Color(int(self.ledsettings.adjacent_red * fading), int(self.ledsettings.adjacent_green * fading),
                          int(self.ledsettings.adjacent_blue * fading))
        if self.ledsettings.adjacent_mode != "Off":

            if 1 < note < (self.led_number - 2):
                if self.keylist_status[int(note) + 2] == 0:
                    self.strip.setPixelColor(int(note) + 1, color)

                if self.keylist_status[int(note) - 2] == 0:
                    self.strip.setPixelColor(int(note) - 1, color)
