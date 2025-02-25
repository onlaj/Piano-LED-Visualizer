#!/usr/bin/env python3

import sys
import os
import fcntl
import argparse
import threading
import asyncio
import atexit
import time

from rpi_ws281x import Color
from waitress import serve

from lib.functions import fastColorWipe, startup_animation, find_between, get_note_position, screensaver, \
    manage_idle_animation
from lib.learnmidi import LearnMIDI
from lib.ledsettings import LedSettings
from lib.ledstrip import LedStrip
from lib.menulcd import MenuLCD
from lib.midiports import MidiPorts
from lib.savemidi import SaveMIDI
from lib.usersettings import UserSettings
from lib.color_mode import ColorMode
import lib.colormaps as cmap
from lib.platform import Hotspot, PlatformRasp, PlatformNull
from lib.rpi_drivers import GPIO, RPiException
from webinterface import webinterface
import webinterface as web_mod

from lib.log_setup import logger


def restart_script():
    """Restart the current script."""
    python = sys.executable
    os.execl(python, python, *sys.argv)


class ArgumentParser:
    def __init__(self):
        self.args = self.parse_arguments()

    def parse_arguments(self):
        appmode_default = 'platform'
        if isinstance(RPiException, RuntimeError):
            appmode_default = 'app'

        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
        parser.add_argument('-d', '--display', type=str, help="choose type of display: '1in44' (default) | '1in3'")
        parser.add_argument('-f', '--fontdir', type=str, help="Use an alternate directory for fonts")
        parser.add_argument('-p', '--port', type=int, help="set port for webinterface (80 is default)")
        parser.add_argument('-s', '--skipupdate', action='store_true',
                            help="Do not try to update /usr/local/bin/connectall.py")
        parser.add_argument('-w', '--webinterface', help="disable webinterface: 'true' (default) | 'false'")
        parser.add_argument('-r', '--rotatescreen', default="false", help="rotate screen: 'false' (default) | 'true'")
        parser.add_argument('-a', '--appmode', default=appmode_default, help="appmode: 'platform' (default) | 'app'")
        parser.add_argument('-l', '--leddriver', default="rpi_ws281x",
                            help="leddriver: 'rpi_ws281x' (default) | 'emu' ")
        return parser.parse_args()


class GPIOHandler:
    def __init__(self, args, midiports, menu, ledstrip, ledsettings, usersettings):
        self.args = args
        self.midiports = midiports
        self.menu = menu
        self.ledstrip = ledstrip
        self.ledsettings = ledsettings
        self.usersettings = usersettings
        self.setup_gpio()

    def setup_gpio(self):
        if self.args.rotatescreen != "true":
            self.KEYRIGHT = 26
            self.KEYLEFT = 5
            self.KEYUP = 6
            self.KEYDOWN = 19
            self.KEY1 = 21
            self.KEY3 = 16
        else:
            self.KEYRIGHT = 5
            self.KEYLEFT = 26
            self.KEYUP = 19
            self.KEYDOWN = 6
            self.KEY1 = 16
            self.KEY3 = 21

        self.KEY2 = 20
        self.JPRESS = 13
        self.BACKLIGHT = 24

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.KEYRIGHT, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEYLEFT, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEYUP, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEYDOWN, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEY1, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEY2, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEY3, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.JPRESS, GPIO.IN, GPIO.PUD_UP)

    def process_gpio_keys(self):
        if GPIO.input(self.KEYUP) == 0:
            self.midiports.last_activity = time.time()
            self.menu.change_pointer(0)
            while GPIO.input(self.KEYUP) == 0:
                time.sleep(0.001)

        if GPIO.input(self.KEYDOWN) == 0:
            self.midiports.last_activity = time.time()
            self.menu.change_pointer(1)
            while GPIO.input(self.KEYDOWN) == 0:
                time.sleep(0.001)

        if GPIO.input(self.KEY1) == 0:
            self.midiports.last_activity = time.time()
            self.menu.enter_menu()
            while GPIO.input(self.KEY1) == 0:
                time.sleep(0.001)

        if GPIO.input(self.KEY2) == 0:
            self.midiports.last_activity = time.time()
            self.menu.go_back()
            if not self.menu.screensaver_is_running:
                fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
            while GPIO.input(self.KEY2) == 0:
                time.sleep(0.01)

        if GPIO.input(self.KEY3) == 0:
            self.midiports.last_activity = time.time()
            if self.ledsettings.sequence_active:
                self.ledsettings.set_sequence(0, 1)
            else:
                active_input = self.usersettings.get_setting_value("input_port")
                secondary_input = self.usersettings.get_setting_value("secondary_input_port")
                self.midiports.change_port("inport", secondary_input)
                self.usersettings.change_setting_value("secondary_input_port", active_input)
                self.usersettings.change_setting_value("input_port", secondary_input)
                fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
            while GPIO.input(self.KEY3) == 0:
                time.sleep(0.01)

        if GPIO.input(self.KEYLEFT) == 0:
            self.midiports.last_activity = time.time()
            self.menu.change_value("LEFT")
            time.sleep(0.1)

        if GPIO.input(self.KEYRIGHT) == 0:
            self.midiports.last_activity = time.time()
            self.menu.change_value("RIGHT")
            time.sleep(0.1)

        if GPIO.input(self.JPRESS) == 0:
            self.midiports.last_activity = time.time()
            self.menu.speed_change()
            while GPIO.input(self.JPRESS) == 0:
                time.sleep(0.01)


class ComponentInitializer:
    def __init__(self, args):
        self.args = args
        self.platform = PlatformRasp() if self.args.appmode == "platform" else PlatformNull()
        self.usersettings = UserSettings()
        self.midiports = MidiPorts(self.usersettings)
        self.ledsettings = LedSettings(self.usersettings)
        self.ledstrip = LedStrip(self.usersettings, self.ledsettings, self.args.leddriver)
        self.learning = LearnMIDI(self.usersettings, self.ledsettings, self.midiports, self.ledstrip)
        self.hotspot = Hotspot(self.platform)
        self.saving = SaveMIDI()
        self.menu = MenuLCD("config/menu.xml", self.args, self.usersettings, self.ledsettings,
                            self.ledstrip, self.learning, self.saving, self.midiports,
                            self.hotspot, self.platform)
        self.setup_components()

    def setup_components(self):
        if not self.args.skipupdate:
            self.platform.copy_connectall_script()

        self.platform.install_midi2abc()
        logger.info(self.args)

        cmap.gradients.update(cmap.load_colormaps())
        cmap.generate_colormaps(cmap.gradients, self.ledstrip.led_gamma)
        cmap.update_multicolor(self.ledsettings.multicolor_range, self.ledsettings.multicolor)

        t = threading.Thread(target=startup_animation, args=(self.ledstrip, self.ledsettings))
        t.start()

        self.midiports.add_instance(self.menu)
        self.ledsettings.add_instance(self.menu, self.ledstrip)
        self.saving.add_instance(self.menu)
        self.learning.add_instance(self.menu)

        self.menu.show()
        self.midiports.last_activity = time.time()
        self.hotspot.hotspot_script_time = time.time()

        fastColorWipe(self.ledstrip.strip, True, self.ledsettings)


class WebInterfaceManager:
    def __init__(self, args, usersettings, ledsettings, ledstrip, learning, saving, midiports, menu, hotspot, platform):
        self.args = args
        self.usersettings = usersettings
        self.ledsettings = ledsettings
        self.ledstrip = ledstrip
        self.learning = learning
        self.saving = saving
        self.midiports = midiports
        self.menu = menu
        self.hotspot = hotspot
        self.platform = platform
        self.websocket_loop = asyncio.new_event_loop()
        self.setup_web_interface()

    def setup_web_interface(self):
        if self.args.webinterface != "false":
            logger.info('Starting webinterface')

            webinterface.usersettings = self.usersettings
            webinterface.ledsettings = self.ledsettings
            webinterface.ledstrip = self.ledstrip
            webinterface.learning = self.learning
            webinterface.saving = self.saving
            webinterface.midiports = self.midiports
            webinterface.menu = self.menu
            webinterface.hotspot = self.hotspot
            webinterface.platform = self.platform
            webinterface.jinja_env.auto_reload = True
            webinterface.config['TEMPLATES_AUTO_RELOAD'] = True

            if not self.args.port:
                self.args.port = 80

            processThread = threading.Thread(
                target=serve,
                args=(webinterface,),
                kwargs={'host': '0.0.0.0', 'port': self.args.port, 'threads': 20},
                daemon=True
            )
            processThread.start()

            processThread = threading.Thread(
                target=web_mod.start_server,
                args=(self.websocket_loop,),
                daemon=True
            )
            processThread.start()

            atexit.register(web_mod.stop_server, self.websocket_loop)


class MIDIEventProcessor:
    def __init__(self, midiports, ledstrip, ledsettings, usersettings, saving, learning, menu, color_mode):
        self.midiports = midiports
        self.ledstrip = ledstrip
        self.ledsettings = ledsettings
        self.usersettings = usersettings
        self.saving = saving
        self.learning = learning
        self.menu = menu
        self.color_mode = color_mode
        self.last_sustain = 0  # Initialize last_sustain
        # Add a timestamp for the last sequence advance
        self.last_sequence_advance = 0

    def process_midi_events(self):
        if len(self.saving.is_playing_midi) == 0 and self.learning.is_started_midi is False:
            self.midiports.midipending = self.midiports.midi_queue
        else:
            self.midiports.midipending = self.midiports.midifile_queue

        while self.midiports.midipending:
            msg, msg_timestamp = self.midiports.midipending.popleft()

            if int(self.usersettings.get_setting_value("midi_logging")) == 1:
                if not msg.is_meta:
                    try:
                        self.learning.socket_send.append("midi_event" + str(msg))
                    except Exception as e:
                        logger.warning(f"[process midi events] Unexpected exception occurred: {e}")

            self.midiports.last_activity = time.time()

            if (msg.type == "note_off" or (
                    msg.type == "note_on" and msg.velocity == 0)) and self.ledsettings.mode != "Disabled":
                note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                if 0 <= note_position < self.ledstrip.led_number:
                    self.handle_note_off(msg, msg_timestamp, note_position)

            elif msg.type == 'note_on' and msg.velocity > 0 and self.ledsettings.mode != "Disabled":
                note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                if 0 <= note_position < self.ledstrip.led_number:
                    self.handle_note_on(msg, msg_timestamp, note_position)

            elif msg.type == "control_change":
                self.handle_control_change(msg, msg_timestamp)

            self.color_mode.MidiEvent(msg, None, self.ledstrip)

            self.saving.restart_time()

    def handle_note_off(self, msg, msg_timestamp, note_position):
        velocity = 0
        self.ledstrip.keylist_status[note_position] = 0

        if self.ledsettings.mode == "Fading":
            self.ledstrip.keylist[note_position] = 1000
        elif self.ledsettings.mode == "Normal":
            self.ledstrip.keylist[note_position] = 0
        elif self.ledsettings.mode == "Pedal":
            self.ledstrip.keylist[note_position] *= (100 - self.ledsettings.fadepedal_notedrop) / 100

        if self.ledstrip.keylist[note_position] <= 0:
            if self.ledsettings.backlight_brightness > 0 and self.menu.screensaver_is_running is not True:
                red_backlight = int(
                    self.ledsettings.get_backlight_color("Red")) * self.ledsettings.backlight_brightness_percent / 100
                green_backlight = int(
                    self.ledsettings.get_backlight_color("Green")) * self.ledsettings.backlight_brightness_percent / 100
                blue_backlight = int(
                    self.ledsettings.get_backlight_color("Blue")) * self.ledsettings.backlight_brightness_percent / 100
                color_backlight = Color(int(red_backlight), int(green_backlight), int(blue_backlight))
                self.ledstrip.strip.setPixelColor(note_position, color_backlight)
                self.ledstrip.set_adjacent_colors(note_position, color_backlight, True)
            else:
                self.ledstrip.strip.setPixelColor(note_position, Color(0, 0, 0))
                self.ledstrip.set_adjacent_colors(note_position, Color(0, 0, 0), False)

        if self.saving.is_recording:
            self.saving.add_track("note_off", msg.note, velocity, msg_timestamp)

    def handle_note_on(self, msg, msg_timestamp, note_position):
        velocity = msg.velocity

        color = self.color_mode.NoteOn(msg, msg_timestamp, None, note_position)
        if color is not None:
            red, green, blue = color
        else:
            red, green, blue = (0, 0, 0)

        self.ledstrip.keylist_color[note_position] = [red, green, blue]

        self.ledstrip.keylist_status[note_position] = 1
        if self.ledsettings.mode == "Velocity":
            brightness = (100 / (float(velocity) / 127)) / 100
        else:
            brightness = 1

        if self.ledsettings.mode == "Fading":
            self.ledstrip.keylist[note_position] = 1001
        elif self.ledsettings.mode == "Velocity":
            self.ledstrip.keylist[note_position] = 999 / float(brightness)
        elif self.ledsettings.mode == "Normal":
            self.ledstrip.keylist[note_position] = 1000
        elif self.ledsettings.mode == "Pedal":
            self.ledstrip.keylist[note_position] = 999

        channel = find_between(str(msg), "channel=", " ")
        if channel == "12" or channel == "11":
            if self.ledsettings.skipped_notes != "Finger-based":
                if channel == "12":
                    hand_color = self.learning.hand_colorR
                else:
                    hand_color = self.learning.hand_colorL

                red, green, blue = map(int, self.learning.hand_colorList[hand_color])
                s_color = Color(red, green, blue)
                self.ledstrip.strip.setPixelColor(note_position, s_color)
                self.ledstrip.set_adjacent_colors(note_position, s_color, False)
        else:
            if self.ledsettings.skipped_notes != "Normal":
                s_color = Color(int(int(red) / float(brightness)), int(int(green) / float(brightness)),
                                int(int(blue) / float(brightness)))
                self.ledstrip.strip.setPixelColor(note_position, s_color)
                self.ledstrip.set_adjacent_colors(note_position, s_color, False)

        if self.saving.is_recording:
            if self.ledsettings.color_mode == "Multicolor":
                import webcolors as wc
                self.saving.add_track("note_on", msg.note, velocity, msg_timestamp,
                                      wc.rgb_to_hex((red, green, blue)))
            else:
                self.saving.add_track("note_on", msg.note, velocity, msg_timestamp)

    def handle_control_change(self, msg, msg_timestamp):
        control = msg.control
        value = msg.value

        # Check if the control change is for the sustain pedal
        if control == 64:  # Sustain pedal
            self.last_sustain = value

        current_time = time.time()
        # Check if the sequence is active and next_step is defined
        if self.ledsettings.sequence_active and self.ledsettings.next_step is not None:
            try:
                # Ensure the control number matches the expected control number for sequence advancement
                if int(control) == int(self.ledsettings.control_number):
                    # Logic to advance the sequence:
                    # - If next_step is positive, advance when the pedal value exceeds next_step
                    # - If next_step is -1, advance when the pedal is released (value is 0)
                    if (int(self.ledsettings.next_step) > 0 and int(value) > int(self.ledsettings.next_step)) or \
                       (int(self.ledsettings.next_step) == -1 and int(value) == 0):
                        # Ensure at least 1 second has passed since the last sequence advancement
                        if (current_time - self.last_sequence_advance) > 1:
                            self.ledsettings.set_sequence(0, 1)
                            self.last_sequence_advance = current_time
            except TypeError:
                logger.warning("TypeError encountered in sequence logic")
            except Exception as e:
                logger.warning(f"[handle control change] Unexpected exception occurred: {e}")

        # Record the control change if recording is active
        if self.saving.is_recording:
            self.saving.add_control_change("control_change", 0, control, value, msg_timestamp)


class LEDEffectsProcessor:
    def __init__(self, ledstrip, ledsettings, menu, color_mode, last_sustain, pedal_deadzone):
        self.ledstrip = ledstrip
        self.ledsettings = ledsettings
        self.menu = menu
        self.color_mode = color_mode
        self.last_sustain = last_sustain
        self.pedal_deadzone = pedal_deadzone

    def process_fade_effects(self, event_loop_time):
        for n, strength in enumerate(self.ledstrip.keylist):
            if strength <= 0:
                continue

            if type(self.ledstrip.keylist_color[n]) is list:
                red = self.ledstrip.keylist_color[n][0]
                green = self.ledstrip.keylist_color[n][1]
                blue = self.ledstrip.keylist_color[n][2]
            else:
                red, green, blue = (0, 0, 0)

            led_changed = False
            new_color = self.color_mode.ColorUpdate(None, n, (red, green, blue))
            if new_color is not None:
                red, green, blue = new_color
                led_changed = True

            fading = 1

            if self.ledsettings.mode == "Velocity" or self.ledsettings.mode == "Pedal" or (
                    self.ledsettings.mode == "Fading" and self.ledstrip.keylist_status[n] == 0):
                fading = (strength / float(100)) / 10
                red = int(red * fading)
                green = int(green * fading)
                blue = int(blue * fading)

                decrease_amount = int((event_loop_time / float(self.ledsettings.fadingspeed / 1000)) * 1000)
                self.ledstrip.keylist[n] = max(0, self.ledstrip.keylist[n] - decrease_amount)
                led_changed = True

            if self.ledsettings.mode == "Velocity" or self.ledsettings.mode == "Pedal":
                if int(self.last_sustain) >= self.pedal_deadzone and self.ledstrip.keylist_status[n] == 0:
                    # Keep the lights on when the pedal is pressed
                    self.ledstrip.keylist[n] = 1000
                    led_changed = True
                elif int(self.last_sustain) < self.pedal_deadzone and self.ledstrip.keylist_status[n] == 0:
                    self.ledstrip.keylist[n] = 0
                    red, green, blue = (0, 0, 0)
                    led_changed = True

            if self.ledstrip.keylist[n] <= 0 and self.menu.screensaver_is_running is not True:
                backlight_level = float(self.ledsettings.backlight_brightness_percent) / 100
                red = int(self.ledsettings.get_backlight_color("Red")) * backlight_level
                green = int(self.ledsettings.get_backlight_color("Green")) * backlight_level
                blue = int(self.ledsettings.get_backlight_color("Blue")) * backlight_level
                led_changed = True

            if led_changed:
                self.ledstrip.strip.setPixelColor(n, Color(int(red), int(green), int(blue)))
                self.ledstrip.set_adjacent_colors(n, Color(int(red), int(green), int(blue)), False, fading)


class VisualizerApp:
    def __init__(self):
        self.fh = None
        self.ensure_singleton()
        os.chdir(sys.path[0])

        # State tracking
        self.last_sustain = 0
        self.pedal_deadzone = 10

        # Initialize components
        self.args = ArgumentParser().args
        self.component_initializer = ComponentInitializer(self.args)
        self.color_mode = ColorMode(self.component_initializer.ledsettings.color_mode,
                                    self.component_initializer.ledsettings)
        self.color_mode_name = self.component_initializer.ledsettings.color_mode
        self.gpio_handler = GPIOHandler(self.args, self.component_initializer.midiports, self.component_initializer.menu,
                                        self.component_initializer.ledstrip, self.component_initializer.ledsettings,
                                        self.component_initializer.usersettings)
        self.web_interface_manager = WebInterfaceManager(self.args, self.component_initializer.usersettings,
                                                         self.component_initializer.ledsettings,
                                                         self.component_initializer.ledstrip,
                                                         self.component_initializer.learning,
                                                         self.component_initializer.saving,
                                                         self.component_initializer.midiports,
                                                         self.component_initializer.menu,
                                                         self.component_initializer.hotspot,
                                                         self.component_initializer.platform)
        self.midi_event_processor = MIDIEventProcessor(self.component_initializer.midiports,
                                                       self.component_initializer.ledstrip,
                                                       self.component_initializer.ledsettings,
                                                       self.component_initializer.usersettings,
                                                       self.component_initializer.saving,
                                                       self.component_initializer.learning,
                                                       self.component_initializer.menu,
                                                       self.color_mode)
        self.led_effects_processor = LEDEffectsProcessor(self.component_initializer.ledstrip,
                                                         self.component_initializer.ledsettings,
                                                         self.component_initializer.menu,
                                                         self.color_mode,
                                                         self.last_sustain,
                                                         self.pedal_deadzone)

        # Frame rate counters
        self.event_loop_stamp = time.perf_counter()
        self.frame_count = 0
        self.frame_avg_stamp = time.perf_counter()
        self.backlight_cleared = False

        # State tracking
        self.display_cycle = 0
        self.screen_hold_time = 16
        self.ledshow_timestamp = time.time()

    def ensure_singleton(self):
        self.fh = open(os.path.realpath(__file__), 'r')
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as error:
            logger.warning(f"[ensure_singleton] Unexpected exception occurred: {error}")
            restart_script()

    def run(self):
        self.component_initializer.platform.manage_hotspot(self.component_initializer.hotspot,
                                                            self.component_initializer.usersettings,
                                                            self.component_initializer.midiports, True)

        while True:
            try:
                elapsed_time = time.perf_counter() - self.component_initializer.saving.start_time
            except Exception as e:
                logger.warning(f"[elapsed time calculation] Unexpected exception occurred: {e}")
                elapsed_time = 0

            self.check_screensaver()
            manage_idle_animation(self.component_initializer.ledstrip, self.component_initializer.ledsettings,
                                  self.component_initializer.menu, self.component_initializer.midiports)
            self.check_activity_backlight()
            self.update_display(elapsed_time)
            self.check_color_mode()
            self.check_settings_changes()
            self.component_initializer.platform.manage_hotspot(self.component_initializer.hotspot,
                                                                self.component_initializer.usersettings,
                                                                self.component_initializer.midiports)
            self.gpio_handler.process_gpio_keys()

            event_loop_time = time.perf_counter() - self.event_loop_stamp
            self.event_loop_stamp = time.perf_counter()

            self.led_effects_processor.process_fade_effects(event_loop_time)
            self.midi_event_processor.process_midi_events()

            self.component_initializer.ledstrip.strip.show()
            self.update_fps_stats()

    def update_fps_stats(self):
        self.frame_count += 1
        frame_seconds = time.perf_counter() - self.frame_avg_stamp

        if frame_seconds >= 2:
            fps = self.frame_count / frame_seconds
            self.component_initializer.ledstrip.current_fps = fps

            self.frame_avg_stamp = time.perf_counter()
            self.frame_count = 0

    def check_screensaver(self):
        if int(self.component_initializer.menu.screensaver_delay) > 0:
            if (time.time() - self.component_initializer.midiports.last_activity) > (int(self.component_initializer.menu.screensaver_delay) * 60):
                screensaver(self.component_initializer.menu, self.component_initializer.midiports,
                            self.component_initializer.saving, self.component_initializer.ledstrip,
                            self.component_initializer.ledsettings)

    def check_activity_backlight(self):
        if (time.time() - self.component_initializer.midiports.last_activity) > 120:
            if not self.backlight_cleared:
                self.component_initializer.ledsettings.backlight_stopped = True
                fastColorWipe(self.component_initializer.ledstrip.strip, True,
                              self.component_initializer.ledsettings)
                self.backlight_cleared = True
        else:
            if self.backlight_cleared:
                self.component_initializer.ledsettings.backlight_stopped = False
                fastColorWipe(self.component_initializer.ledstrip.strip, True,
                              self.component_initializer.ledsettings)
                self.backlight_cleared = False

    def update_display(self, elapsed_time):
        if self.display_cycle >= 3:
            self.display_cycle = 0
            if elapsed_time > self.screen_hold_time:
                self.component_initializer.menu.show()
        self.display_cycle += 1

    def check_color_mode(self):
        if self.component_initializer.ledsettings.color_mode != self.color_mode_name or self.component_initializer.ledsettings.incoming_setting_change:
            self.component_initializer.ledsettings.incoming_setting_change = False
            self.color_mode = ColorMode(self.component_initializer.ledsettings.color_mode,
                                        self.component_initializer.ledsettings)
            self.color_mode_name = self.component_initializer.ledsettings.color_mode
            # Reinitialize MIDIEventProcessor and LEDEffectsProcessor with the new color_mode
            self.midi_event_processor.color_mode = self.color_mode
            self.led_effects_processor.color_mode = self.color_mode
            logger.info(f"Color mode changed to {self.color_mode_name}")

    def check_settings_changes(self):
        if (time.time() - self.component_initializer.usersettings.last_save) > 1:
            if self.component_initializer.usersettings.pending_changes:
                self.color_mode.LoadSettings(self.component_initializer.ledsettings)
                self.component_initializer.usersettings.save_changes()

            if self.component_initializer.usersettings.pending_reset:
                self.component_initializer.usersettings.pending_reset = False
                self.component_initializer.ledsettings = LedSettings(self.component_initializer.usersettings)
                self.component_initializer.ledstrip = LedStrip(self.component_initializer.usersettings,
                                                                self.component_initializer.ledsettings)
                self.component_initializer.menu = MenuLCD("config/menu.xml", self.args,
                                                          self.component_initializer.usersettings,
                                                          self.component_initializer.ledsettings,
                                                          self.component_initializer.ledstrip,
                                                          self.component_initializer.learning,
                                                          self.component_initializer.saving,
                                                          self.component_initializer.midiports,
                                                          self.component_initializer.hotspot,
                                                          self.component_initializer.platform)
                self.component_initializer.menu.show()
                self.component_initializer.ledsettings.add_instance(self.component_initializer.menu,
                                                                     self.component_initializer.ledstrip)


if __name__ == "__main__":
    app = VisualizerApp()
    app.run()