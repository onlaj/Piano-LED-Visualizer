#!/usr/bin/env python3

import sys
import os
import fcntl
import signal
import time

from lib.argument_parser import ArgumentParser
from lib.component_initializer import ComponentInitializer
from lib.functions import fastColorWipe, screensaver, \
    manage_idle_animation, stop_animations
from lib.gpio_handler import GPIOHandler
from lib.led_effects_processor import LEDEffectsProcessor
from lib.ledsettings import LedSettings
from lib.ledstrip import LedStrip
from lib.menulcd import MenuLCD
from lib.midi_event_processor import MIDIEventProcessor
from lib.color_mode import ColorMode
from lib.webinterface_manager import WebInterfaceManager

from lib.log_setup import logger


def restart_script():
    """Restart the current script."""
    python = sys.executable
    os.execl(python, python, *sys.argv)


class VisualizerApp:
    def __init__(self):
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        self.fh = None
        self.ensure_singleton()
        os.chdir(sys.path[0])

        # State tracking
        self.last_sustain = 0
        self.pedal_deadzone = 10

        # Initialize components
        self.args = ArgumentParser().args
        self.component_initializer = ComponentInitializer(self.args)
        
        # Check and enable SPI if running on Raspberry Pi
        if hasattr(self.component_initializer.platform, 'check_and_enable_spi'):
            self.component_initializer.platform.check_and_enable_spi()
            
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

    def handle_shutdown(self, signum, frame):
        # Turn off all LEDs before shutting down
        stop_animations(self.component_initializer.menu)
        fastColorWipe(self.component_initializer.ledstrip.strip, True, self.component_initializer.ledsettings)
        sys.exit(0)
    
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
            time.sleep(0.01)

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