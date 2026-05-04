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
from lib.display_refresh_policy import DisplayRefreshPolicy

from lib.log_setup import logger


def restart_script():
    """Restart the current script."""
    python = sys.executable
    os.execl(python, python, *sys.argv)


class VisualizerApp:
    def __init__(self):
        self.ci = None
        self.component_initializer = None
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
                                                         self.pedal_deadzone,
                                                         runtime_diagnostics=self.ci.midiports.runtime_diagnostics)
        self.runtime_diagnostics = self.ci.midiports.runtime_diagnostics
        self._instrument_strip_show()

        # Frame rate counters
        self.event_loop_stamp = time.perf_counter()
        self.frame_count = 0
        self.frame_avg_stamp = time.perf_counter()
        self.last_frame_time = time.perf_counter()
        self.backlight_cleared = False

        # State tracking
        self.display_cycle = 0
        self.screen_hold_time = 16
        self.ledshow_timestamp = time.time()
        self._last_menu_tick = 0.0
        self.display_refresh_policy = DisplayRefreshPolicy()

    def _instrument_strip_show(self):
        strip = self.ci.ledstrip.strip
        if getattr(strip.show, "_plv_runtime_wrapped", False):
            return

        original_show = strip.show
        diagnostics = self.runtime_diagnostics

        def instrumented_show(*args, **kwargs):
            show_started = time.perf_counter()
            try:
                return original_show(*args, **kwargs)
            finally:
                diagnostics.increment_counter("strip_show_calls")
                diagnostics.record_duration("strip_show", time.perf_counter() - show_started)

        instrumented_show._plv_runtime_wrapped = True
        strip.show = instrumented_show

    def _run_timed(self, metric_name, callback, *args):
        started = time.perf_counter()
        result = callback(*args)
        self.runtime_diagnostics.record_duration(metric_name, time.perf_counter() - started)
        return result

    def handle_shutdown(self, signum, frame):
        ci = getattr(self, "ci", None)
        if ci is not None:
            try:
                stop_animations(ci.menu)
                fastColorWipe(ci.ledstrip.strip, True, ci.ledsettings)
            except Exception as error:
                logger.warning(f"[shutdown] Could not clear LEDs cleanly: {error}")
        os._exit(0)
    
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
            self.runtime_diagnostics.set_metadata("system_state", self.state_manager.current_state.value)
            
            # Get dynamic sleep interval based on current state
            sleep_interval = self.state_manager.get_loop_delay()
            self.runtime_diagnostics.set_gauge("requested_loop_sleep_ms", round(sleep_interval * 1000.0, 4))

            self._run_timed("check_screensaver", self.check_screensaver, midiports, menu, now_wall)
            self._run_timed(
                "manage_idle_animation",
                manage_idle_animation,
                ledstrip,
                ledsettings,
                menu,
                midiports,
                self.state_manager,
            )
            self._run_timed("check_activity_backlight", self.check_activity_backlight, ledstrip, ledsettings, midiports, now_wall)
            self._run_timed("update_display", self.update_display, elapsed_time, menu)
            self._run_timed("check_color_mode", self.check_color_mode, ledsettings)
            self._run_timed("check_settings_changes", self.check_settings_changes, usersettings, now_wall)
            self._run_timed("manage_hotspot", platform.manage_hotspot, hotspot, usersettings, midiports, False, now_wall)
            self._run_timed("process_gpio_keys", self.gpio_handler.process_gpio_keys)

            event_loop_time = loop_start - self.event_loop_stamp
            self.event_loop_stamp = loop_start

            midiports.refresh_queue_diagnostics(now_perf=loop_start)
            fade_started = time.perf_counter()
            fade_processed = self.led_effects_processor.process_fade_effects(event_loop_time)
            self.runtime_diagnostics.record_duration("process_fade_effects", time.perf_counter() - fade_started)
            midi_started = time.perf_counter()
            midi_processed = self.midi_event_processor.process_midi_events()
            self.runtime_diagnostics.record_duration("process_midi_events", time.perf_counter() - midi_started)

            # Only update LEDs if effects changed them or MIDI events occurred
            should_update = fade_processed or midi_processed
            self.runtime_diagnostics.set_gauge("led_update_requested", int(bool(should_update)))
            
            if should_update:
                ledstrip.strip.show()
                self.update_fps_stats()
            else:
                # Clear FPS after short inactivity so UI doesn't show stale values
                now_perf = time.perf_counter()
                if (now_perf - self.last_frame_time) > 1.0:
                    ledstrip.current_fps = 0.0
            midiports.refresh_queue_diagnostics()
            self.runtime_diagnostics.record_duration("main_loop", time.perf_counter() - loop_start)
            time.sleep(sleep_interval)  # Dynamic delay based on system state

    def update_fps_stats(self):
        now = time.perf_counter()

        # If we had a long pause between frames, reset the averaging window
        if (now - self.last_frame_time) > 2.0:
            self.frame_count = 0
            self.frame_avg_stamp = now

        self.frame_count += 1
        frame_seconds = now - self.frame_avg_stamp

        if frame_seconds >= 1.0:
            fps = self.frame_count / frame_seconds if frame_seconds > 0 else 0
            self.ci.ledstrip.current_fps = fps

            self.frame_avg_stamp = now
            self.frame_count = 0

        self.last_frame_time = now

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
        should_refresh = self.state_manager.should_refresh_screen()
        if self.display_refresh_policy.should_show_static_menu(
            elapsed_time=elapsed_time,
            hold_time=self.screen_hold_time,
            scroll_needed=scroll_needed,
            should_refresh=should_refresh,
        ):
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
