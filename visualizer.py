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


def parse_arguments():
    """Parse command line arguments."""
    appmode_default = 'platform'
    if isinstance(RPiException, RuntimeError):
        # If Raspberry GPIO fails (no Raspberry Pi detected) then set default to app mode
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


class VisualizerApp:
    def __init__(self):
        self.fh = None
        self.ensure_singleton()
        os.chdir(sys.path[0])
        self.args = parse_arguments()
        self.setup_gpio()
        self.setup_components()
        self.setup_web_interface()

        # Frame rate counters
        self.event_loop_stamp = time.perf_counter()
        self.frame_count = 0
        self.frame_avg_stamp = time.perf_counter()
        self.backlight_cleared = False

        # State tracking
        self.display_cycle = 0
        self.screen_hold_time = 16
        self.last_sustain = 0
        self.pedal_deadzone = 10
        self.ledshow_timestamp = time.time()
        self.color_mode_name = ""
        self.color_mode = None

    def ensure_singleton(self):
        """Ensure there is only one instance of the script running."""
        self.fh = open(os.path.realpath(__file__), 'r')
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as error:
            logger.warning(f"[ensure_singleton] Unexpected exception occurred: {error}")
            restart_script()

    def setup_gpio(self):
        """Set up GPIO pins for buttons and controls."""
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

        # pins are interpreted as BCM pins.
        GPIO.setmode(GPIO.BCM)
        # Sets the pin as input and sets Pull-up mode for the pin.
        GPIO.setup(self.KEYRIGHT, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEYLEFT, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEYUP, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEYDOWN, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEY1, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEY2, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.KEY3, GPIO.IN, GPIO.PUD_UP)
        GPIO.setup(self.JPRESS, GPIO.IN, GPIO.PUD_UP)

    def setup_components(self):
        """Initialize all application components."""
        # Setup platform
        if self.args.appmode == "platform":
            self.platform = PlatformRasp()
        else:
            self.platform = PlatformNull()

        if not self.args.skipupdate:
            self.platform.copy_connectall_script()

        self.platform.install_midi2abc()
        logger.info(self.args)

        # Initialize components
        self.usersettings = UserSettings()
        self.midiports = MidiPorts(self.usersettings)
        self.ledsettings = LedSettings(self.usersettings)
        self.ledstrip = LedStrip(self.usersettings, self.ledsettings, self.args.leddriver)

        # Set up colormaps
        cmap.gradients.update(cmap.load_colormaps())
        cmap.generate_colormaps(cmap.gradients, self.ledstrip.led_gamma)
        cmap.update_multicolor(self.ledsettings.multicolor_range, self.ledsettings.multicolor)

        # Run startup animation in a separate thread
        t = threading.Thread(target=startup_animation, args=(self.ledstrip, self.ledsettings))
        t.start()

        # Initialize remaining components
        self.learning = LearnMIDI(self.usersettings, self.ledsettings, self.midiports, self.ledstrip)
        self.hotspot = Hotspot(self.platform)
        self.saving = SaveMIDI()
        self.menu = MenuLCD("config/menu.xml", self.args, self.usersettings, self.ledsettings,
                            self.ledstrip, self.learning, self.saving, self.midiports,
                            self.hotspot, self.platform)

        # Register instances
        self.midiports.add_instance(self.menu)
        self.ledsettings.add_instance(self.menu, self.ledstrip)
        self.saving.add_instance(self.menu)
        self.learning.add_instance(self.menu)

        self.menu.show()
        self.midiports.last_activity = time.time()
        self.hotspot.hotspot_script_time = time.time()

        # Initial LED setup
        fastColorWipe(self.ledstrip.strip, True, self.ledsettings)

    def setup_web_interface(self):
        """Set up web interface if enabled."""
        self.websocket_loop = asyncio.new_event_loop()

        if self.args.webinterface != "false":
            logger.info('Starting webinterface')

            # Configure webinterface components
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

            # Start web server in a separate thread
            if not self.args.port:
                self.args.port = 80

            processThread = threading.Thread(
                target=serve,
                args=(webinterface,),
                kwargs={'host': '0.0.0.0', 'port': self.args.port, 'threads': 20},
                daemon=True
            )
            processThread.start()

            # Start websocket server in a separate thread
            processThread = threading.Thread(
                target=web_mod.start_server,
                args=(self.websocket_loop,),
                daemon=True
            )
            processThread.start()

            # Register the shutdown handler
            atexit.register(web_mod.stop_server, self.websocket_loop)

    def process_gpio_keys(self):
        """Handle GPIO button presses."""
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

    def process_fade_effects(self, event_loop_time):
        """Process fading effects for LED strip."""
        for n, strength in enumerate(self.ledstrip.keylist):
            # Only apply fade processing to activated leds
            if strength <= 0:
                continue

            # Restore saved led colors
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

            # Calculate fading for Fading and Velocity modes
            if self.ledsettings.mode == "Velocity" or self.ledsettings.mode == "Pedal" or (
                    self.ledsettings.mode == "Fading" and self.ledstrip.keylist_status[n] == 0):
                fading = (strength / float(100)) / 10
                red = int(red * fading)
                green = int(green * fading)
                blue = int(blue * fading)

                # Calculate how much to decrease based on fade speed and elapsed time
                decrease_amount = int((event_loop_time / float(self.ledsettings.fadingspeed / 1000)) * 1000)
                self.ledstrip.keylist[n] = max(0, self.ledstrip.keylist[n] - decrease_amount)
                led_changed = True

            if self.ledsettings.mode == "Velocity" or self.ledsettings.mode == "Pedal":
                # If sustain pedal is off and note is off, turn off fade processing
                if int(self.last_sustain) < self.pedal_deadzone and self.ledstrip.keylist_status[n] == 0:
                    self.ledstrip.keylist[n] = 0
                    red, green, blue = (0, 0, 0)
                    led_changed = True

            # If fade mode newly completed, apply backlight
            if self.ledstrip.keylist[n] <= 0 and self.menu.screensaver_is_running is not True:
                backlight_level = float(self.ledsettings.backlight_brightness_percent) / 100
                red = int(self.ledsettings.get_backlight_color("Red")) * backlight_level
                green = int(self.ledsettings.get_backlight_color("Green")) * backlight_level
                blue = int(self.ledsettings.get_backlight_color("Blue")) * backlight_level
                led_changed = True

            # Apply fade mode colors to ledstrip
            if led_changed:
                self.ledstrip.strip.setPixelColor(n, Color(int(red), int(green), int(blue)))
                self.ledstrip.set_adjacent_colors(n, Color(int(red), int(green), int(blue)), False, fading)

    def handle_note_off(self, msg, msg_timestamp, note_position):
        """Handle MIDI note off events."""
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
        """Handle MIDI note on events."""
        velocity = msg.velocity

        color = self.color_mode.NoteOn(msg, msg_timestamp, None, note_position)
        if color is not None:
            red, green, blue = color
        else:
            red, green, blue = (0, 0, 0)

        # Save ledstrip led colors
        self.ledstrip.keylist_color[note_position] = [red, green, blue]

        # Set initial fade processing state
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

        # Apply learning colors
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

        # Saving
        if self.saving.is_recording:
            if self.ledsettings.color_mode == "Multicolor":
                import webcolors as wc
                self.saving.add_track("note_on", msg.note, velocity, msg_timestamp,
                                      wc.rgb_to_hex((red, green, blue)))
            else:
                self.saving.add_track("note_on", msg.note, velocity, msg_timestamp)

    def handle_control_change(self, msg, msg_timestamp):
        """Handle MIDI control change events."""
        control = msg.control
        value = msg.value

        # midi control 64 = sustain pedal
        if control == 64:
            self.last_sustain = value

        if self.ledsettings.sequence_active and self.ledsettings.next_step is not None:
            try:
                if "+" in self.ledsettings.next_step:
                    if int(value) > int(self.ledsettings.next_step) and control == self.ledsettings.control_number:
                        self.ledsettings.set_sequence(0, 1)
                else:
                    if int(value) < int(self.ledsettings.next_step) and control == self.ledsettings.control_number:
                        self.ledsettings.set_sequence(0, 1)
            except TypeError:
                pass
            except Exception as e:
                logger.warning(f"[handle control change] Unexpected exception occurred: {e}")

        if self.saving.is_recording:
            self.saving.add_control_change("control_change", 0, control, value, msg_timestamp)

    def process_midi_events(self):
        """Process pending MIDI events."""
        # Prep midi event queue
        if len(self.saving.is_playing_midi) == 0 and self.learning.is_started_midi is False:
            self.midiports.midipending = self.midiports.midi_queue
        else:
            self.midiports.midipending = self.midiports.midifile_queue

        # loop through incoming midi messages
        while self.midiports.midipending:
            msg, msg_timestamp = self.midiports.midipending.popleft()

            if int(self.usersettings.get_setting_value("midi_logging")) == 1:
                if not msg.is_meta:
                    try:
                        self.learning.socket_send.append("midi_event" + str(msg))
                    except Exception as e:
                        logger.warning(f"[process midi events] Unexpected exception occurred: {e}")

            self.midiports.last_activity = time.time()

            # when a note is lifted (off)
            if (msg.type == "note_off" or (
                    msg.type == "note_on" and msg.velocity == 0)) and self.ledsettings.mode != "Disabled":
                note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                if 0 <= note_position < self.ledstrip.led_number:
                    self.handle_note_off(msg, msg_timestamp, note_position)

            # when a note is pressed
            elif msg.type == 'note_on' and msg.velocity > 0 and self.ledsettings.mode != "Disabled":
                note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                if 0 <= note_position < self.ledstrip.led_number:
                    self.handle_note_on(msg, msg_timestamp, note_position)

            # Midi control change event
            elif msg.type == "control_change":
                self.handle_control_change(msg, msg_timestamp)

            # Process other MIDI events
            self.color_mode.MidiEvent(msg, None, self.ledstrip)

            # Save event-loop update
            self.saving.restart_time()

    def update_fps_stats(self):
        """Update FPS statistics."""
        self.frame_count += 1
        frame_seconds = time.perf_counter() - self.frame_avg_stamp

        # calculate fps average over 2 seconds
        if frame_seconds >= 2:
            fps = self.frame_count / frame_seconds
            self.ledstrip.current_fps = fps

            # reset counters
            self.frame_avg_stamp = time.perf_counter()
            self.frame_count = 0

    def check_screensaver(self):
        """Check if screensaver should be activated."""
        if int(self.menu.screensaver_delay) > 0:
            if (time.time() - self.midiports.last_activity) > (int(self.menu.screensaver_delay) * 60):
                screensaver(self.menu, self.midiports, self.saving, self.ledstrip, self.ledsettings)

    def check_activity_backlight(self):
        """Manage backlight based on activity."""
        if (time.time() - self.midiports.last_activity) > 120:
            if not self.backlight_cleared:
                self.ledsettings.backlight_stopped = True
                fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
                self.backlight_cleared = True
        else:
            if self.backlight_cleared:
                self.ledsettings.backlight_stopped = False
                fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
                self.backlight_cleared = False

    def update_display(self, elapsed_time):
        """Update LCD display when needed."""
        if self.display_cycle >= 3:
            self.display_cycle = 0
            if elapsed_time > self.screen_hold_time:
                self.menu.show()
        self.display_cycle += 1

    def check_color_mode(self):
        """Create or update ColorMode if needed."""
        if self.ledsettings.color_mode != self.color_mode_name or self.ledsettings.incoming_setting_change:
            self.ledsettings.incoming_setting_change = False
            self.color_mode = ColorMode(self.ledsettings.color_mode, self.ledsettings)
            self.color_mode_name = self.ledsettings.color_mode

    def check_settings_changes(self):
        """Save settings if they have changed."""
        if (time.time() - self.usersettings.last_save) > 1:
            if self.usersettings.pending_changes:
                self.color_mode.LoadSettings(self.ledsettings)
                self.usersettings.save_changes()

            if self.usersettings.pending_reset:
                self.usersettings.pending_reset = False
                self.ledsettings = LedSettings(self.usersettings)
                self.ledstrip = LedStrip(self.usersettings, self.ledsettings)
                self.menu = MenuLCD("config/menu.xml", self.args, self.usersettings, self.ledsettings,
                                    self.ledstrip, self.learning, self.saving, self.midiports,
                                    self.hotspot, self.platform)
                self.menu.show()
                self.ledsettings.add_instance(self.menu, self.ledstrip)

    def run(self):
        """Run the main event loop."""
        self.platform.manage_hotspot(self.hotspot, self.usersettings, self.midiports, True)

        # Initialize color mode
        self.color_mode = ColorMode(self.ledsettings.color_mode, self.ledsettings)
        self.color_mode_name = self.ledsettings.color_mode

        # Main event loop
        while True:
            # Calculate elapsed time since saving started
            try:
                elapsed_time = time.perf_counter() - self.saving.start_time
            except Exception as e:
                logger.warning(f"[elapsed time calculation] Unexpected exception occurred: {e}")
                elapsed_time = 0

            # Check if screensaver should be shown
            self.check_screensaver()

            # Process IDLE animation
            manage_idle_animation(self.ledstrip, self.ledsettings, self.menu, self.midiports)

            # Check for activity to manage backlight
            self.check_activity_backlight()

            # Update display if needed
            self.update_display(elapsed_time)

            # Update color mode if needed
            self.check_color_mode()

            # Check for settings changes
            self.check_settings_changes()

            # Manage hotspot
            self.platform.manage_hotspot(self.hotspot, self.usersettings, self.midiports)

            # Process GPIO key presses
            self.process_gpio_keys()

            # Calculate time for event loop
            event_loop_time = time.perf_counter() - self.event_loop_stamp
            self.event_loop_stamp = time.perf_counter()

            # Process fade effects
            self.process_fade_effects(event_loop_time)

            # Process MIDI events
            self.process_midi_events()

            # Update the LED strip
            self.ledstrip.strip.show()

            # Update FPS statistics
            self.update_fps_stats()


if __name__ == "__main__":
    app = VisualizerApp()
    app.run()