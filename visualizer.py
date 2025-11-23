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
from lib.state_manager import StateManager

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
        self.ci = self.component_initializer
        
        # Check and enable SPI if running on Raspberry Pi
        if hasattr(self.ci.platform, 'check_and_enable_spi'):
            self.ci.platform.check_and_enable_spi()
        
        self.color_mode = ColorMode(self.ci.ledsettings.color_mode,
                                    self.ci.ledsettings)
        self.color_mode_name = self.ci.ledsettings.color_mode
        
        # Initialize state manager first
        self.state_manager = StateManager(self.ci.usersettings)
        
        self.gpio_handler = GPIOHandler(self.args, self.ci.midiports, self.ci.menu,
                                        self.ci.ledstrip, self.ci.ledsettings,
                                        self.ci.usersettings, self.state_manager)
        self.web_interface_manager = WebInterfaceManager(self.args, self.ci.usersettings,
                                                         self.ci.ledsettings,
                                                         self.ci.ledstrip,
                                                         self.ci.learning,
                                                         self.ci.saving,
                                                         self.ci.midiports,
                                                         self.ci.menu,
                                                         self.ci.hotspot,
                                                         self.ci.platform,
                                                         self.state_manager)
        self.midi_event_processor = MIDIEventProcessor(self.ci.midiports,
                                                       self.ci.ledstrip,
                                                       self.ci.ledsettings,
                                                       self.ci.usersettings,
                                                       self.ci.saving,
                                                       self.ci.learning,
                                                       self.ci.menu,
                                                       self.color_mode,
                                                       self.state_manager)
        self.led_effects_processor = LEDEffectsProcessor(self.ci.ledstrip,
                                                         self.ci.ledsettings,
                                                         self.ci.menu,
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
        self._last_menu_tick = 0.0

    def handle_shutdown(self, signum, frame):
        # Turn off all LEDs before shutting down
        stop_animations(self.ci.menu)
        fastColorWipe(self.ci.ledstrip.strip, True, self.ci.ledsettings)
        sys.exit(0)
    
    def ensure_singleton(self):
        self.fh = open(os.path.realpath(__file__), 'r')
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as error:
            logger.warning(f"[ensure_singleton] Unexpected exception occurred: {error}")
            restart_script()

    def run(self):
        ci = self.ci
        platform = ci.platform
        platform.manage_hotspot(ci.hotspot, ci.usersettings, ci.midiports, True)

        while True:
            loop_start = time.perf_counter()
            try:
                elapsed_time = loop_start - ci.saving.start_time
            except Exception as e:
                logger.warning(f"[elapsed time calculation] Unexpected exception occurred: {e}")
                elapsed_time = 0

            menu = ci.menu
            ledstrip = ci.ledstrip
            ledsettings = ci.ledsettings
            midiports = ci.midiports
            usersettings = ci.usersettings
            hotspot = ci.hotspot
            now_wall = time.time()

            # Update system state (syncs with midiports and menu activity)
            self.state_manager.update_state(midiports, menu, now_wall)
            
            # Get dynamic sleep interval based on current state
            sleep_interval = self.state_manager.get_loop_delay()

            self.check_screensaver(midiports, menu, now_wall)
            manage_idle_animation(ledstrip, ledsettings, menu, midiports, self.state_manager)
            self.check_activity_backlight(ledstrip, ledsettings, midiports, now_wall)
            self.update_display(elapsed_time, menu)
            self.check_color_mode(ledsettings)
            self.check_settings_changes(usersettings, now_wall)
            platform.manage_hotspot(hotspot, usersettings, midiports, False, now_wall)
            self.gpio_handler.process_gpio_keys()

            event_loop_time = loop_start - self.event_loop_stamp
            self.event_loop_stamp = loop_start

            fade_processed = self.led_effects_processor.process_fade_effects(event_loop_time)
            midi_processed = self.midi_event_processor.process_midi_events()

            # Only update LEDs if effects changed them or MIDI events occurred
            should_update = fade_processed or midi_processed
            
            if should_update:
                ledstrip.strip.show()
                self.update_fps_stats()
            else:
                # In IDLE with no activity, set FPS to reflect actual state
                ledstrip.current_fps = 1.0 / max(sleep_interval, 0.001) if sleep_interval > 0 else 0
            time.sleep(sleep_interval)  # Dynamic delay based on system state

    def update_fps_stats(self):
        self.frame_count += 1
        frame_seconds = time.perf_counter() - self.frame_avg_stamp

        if frame_seconds >= 2:
            fps = self.frame_count / frame_seconds
            self.ci.ledstrip.current_fps = fps

            self.frame_avg_stamp = time.perf_counter()
            self.frame_count = 0

    def check_screensaver(self, midiports, menu, current_time=None):
        ci = self.ci
        
        # Stop screensaver during active use
        if self.state_manager.is_active_use() and menu.screensaver_is_running:
            menu.screensaver_is_running = False
            menu.show()
            return
        
        # Check if screensaver should start using state manager
        if self.state_manager.should_run_screensaver(menu):
            screensaver(menu, midiports, ci.saving, ci.ledstrip, ci.ledsettings, self.state_manager)

    def check_activity_backlight(self, ledstrip, ledsettings, midiports, current_time):
        now = current_time
        if (now - midiports.last_activity) > 120:
            if not self.backlight_cleared:
                ledsettings.backlight_stopped = True
                fastColorWipe(ledstrip.strip, True, ledsettings)
                self.backlight_cleared = True
        else:
            if self.backlight_cleared:
                ledsettings.backlight_stopped = False
                fastColorWipe(ledstrip.strip, True, ledsettings)
                self.backlight_cleared = False

    def update_display(self, elapsed_time, menu):
        now = time.monotonic()
        tick_interval = 0.2  # ~5 fps animation 
        #(still really drop led fps but go back to normal 
        # when selecting a non-animated line)

        # Cache getattr results to avoid repeated lookups
        scroll_needed = getattr(menu, "scroll_needed", False)
        screen_on = getattr(menu, "screen_on", 1)
        
        # Tick only if menu.scroll_needed is True
        if scroll_needed and screen_on == 1:
            if now - self._last_menu_tick >= tick_interval:
                try:
                    menu.update()  # advance cut_count/scroll_hold
                except Exception as e:
                    logger.debug(f"menu.update() tick skipped: {e}")
                self._last_menu_tick = now

        # State-based refresh logic
        if self.state_manager.should_refresh_screen():
            if elapsed_time > self.screen_hold_time:
                menu.show()


    def check_color_mode(self, ledsettings):
        if ledsettings.color_mode != self.color_mode_name or ledsettings.incoming_setting_change:
            ledsettings.incoming_setting_change = False
            self.color_mode = ColorMode(ledsettings.color_mode, ledsettings)
            self.color_mode_name = ledsettings.color_mode
            # Reinitialize MIDIEventProcessor and LEDEffectsProcessor with the new color_mode
            self.midi_event_processor.color_mode = self.color_mode
            self.led_effects_processor.color_mode = self.color_mode
            logger.info(f"Color mode changed to {self.color_mode_name}")

    def check_settings_changes(self, usersettings, current_time):
        ci = self.ci
        now = current_time
        if (now - usersettings.last_save) <= 1:
            return

        if usersettings.pending_changes:
            self.color_mode.LoadSettings(ci.ledsettings)
            usersettings.save_changes()

        if usersettings.pending_reset:
            usersettings.pending_reset = False
            ci.ledsettings = LedSettings(usersettings)
            ci.ledstrip = LedStrip(usersettings, ci.ledsettings)
            ci.menu = MenuLCD("config/menu.xml", self.args,
                              usersettings,
                              ci.ledsettings,
                              ci.ledstrip,
                              ci.learning,
                              ci.saving,
                              ci.midiports,
                              ci.hotspot,
                              ci.platform)
            ci.menu.show()
            ci.ledsettings.add_instance(ci.menu, ci.ledstrip)


if __name__ == "__main__":
    app = VisualizerApp()
    app.run()
