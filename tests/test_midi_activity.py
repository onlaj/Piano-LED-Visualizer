#!/usr/bin/env python3

import sys
import os
import threading
import time
import unittest
from collections import deque
from unittest.mock import MagicMock, patch

import mido

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# use the null GPIO driver, the tests must not touch the pins
sys.modules["RPi.GPIO"] = None

from lib import functions  # noqa: E402
from lib.midiports import MidiPorts  # noqa: E402

# the main loop needs neither the web interface nor the components it would
# start, and importing them creates the profiles database and score log
with patch.dict(sys.modules, {"webinterface": MagicMock(),
                              "lib.component_initializer": MagicMock(),
                              "lib.webinterface_manager": MagicMock()}):
    import visualizer


class FakeSettings:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get_setting_value(self, name):
        return self.values.get(name)


class TestMidiActivityEvent(unittest.TestCase):
    def _make_instance(self):
        instance = MidiPorts.__new__(MidiPorts)
        instance.usersettings = FakeSettings({})
        instance._midi_mode_cache = "light_show"
        instance.last_activity = 0
        instance.midi_activity_event = threading.Event()
        instance._router = type("Router", (), {"from_piano": lambda self, msg: None, "reset": lambda self: None})()
        instance._enqueue_for_leds = lambda msg, source: None
        instance._maybe_forward_to_websocket = lambda msg: None
        instance._queue_thru = lambda dest, msg: None
        instance.log_midi = lambda msg, source: None
        return instance

    def test_route_piano_sets_activity(self):
        instance = self._make_instance()
        msg = mido.Message("note_on", note=60, velocity=100)
        instance.route_midi_message(msg, "piano")
        self.assertTrue(instance.midi_activity_event.is_set())
        self.assertGreater(instance.last_activity, 0)

    def test_route_computer_does_not_set_activity(self):
        instance = self._make_instance()
        msg = mido.Message("note_on", note=60, velocity=100)
        instance.route_midi_message(msg, "computer")
        self.assertFalse(instance.midi_activity_event.is_set())
        self.assertEqual(instance.last_activity, 0)


class StopLoop(Exception):
    pass


class TestMainLoopWait(unittest.TestCase):
    def run_loop(self, loop_delay, passes, on_pass=None):
        """Run VisualizerApp.run() for a number of passes and return when each started."""
        app = visualizer.VisualizerApp.__new__(visualizer.VisualizerApp)
        app.ci = MagicMock()
        app.ci.saving.start_time = time.perf_counter()
        app.ci.midiports.midi_activity_event = threading.Event()
        app.state_manager = MagicMock()
        app.state_manager.get_loop_delay.return_value = loop_delay
        app.gpio_handler = MagicMock()
        app.led_effects_processor = MagicMock()
        app.led_effects_processor.process_fade_effects.return_value = False
        app.midi_event_processor = MagicMock()
        app.event_loop_stamp = time.perf_counter()
        for name in ("check_screensaver", "check_activity_backlight", "update_display",
                     "check_color_mode", "check_settings_changes"):
            setattr(app, name, MagicMock())

        started = []

        def process_midi_events():
            started.append(time.perf_counter())
            if len(started) > passes:
                raise StopLoop()
            if on_pass:
                on_pass(len(started), app.ci.midiports.midi_activity_event)
            return False

        app.midi_event_processor.process_midi_events.side_effect = process_midi_events
        with patch.object(visualizer, "manage_idle_animation"):
            with self.assertRaises(StopLoop):
                app.run()
        return started

    def test_idle_wait_returns_when_piano_is_played(self):
        def on_pass(n, event):
            if n == 1:
                threading.Timer(0.05, event.set).start()

        started = self.run_loop(2.0, 1, on_pass)
        self.assertLess(started[1] - started[0], 1.0)

    def test_idle_wait_is_not_cut_short_by_activity_already_handled(self):
        def on_pass(n, event):
            if n == 1:
                event.set()

        started = self.run_loop(0.3, 2, on_pass)
        self.assertLess(started[1] - started[0], 0.2)
        self.assertGreaterEqual(started[2] - started[1], 0.25)


class TestScreensaverWait(unittest.TestCase):
    def test_does_not_spin_when_activity_leaves_no_queued_notes(self):
        # e.g. the notes were already taken from the queue by a learning session
        menu = MagicMock()
        menu.screensaver_settings = {"local_ip": "0", "ram": "0", "temp": "0",
                                     "network_usage": "0", "sd_card_space": "0"}
        menu.screen_off_delay = 0
        saving = MagicMock()
        saving.start_time = time.perf_counter()
        midiports = MagicMock()
        midiports.midi_queue = deque()
        midiports.midi_activity_event = threading.Event()
        midiports.midi_activity_event.set()

        end = time.perf_counter() + 0.5
        gpio = MagicMock()
        gpio.input.side_effect = lambda pin: 0 if time.perf_counter() > end else 1
        with patch.object(functions, "GPIO", gpio), patch.object(functions, "manage_idle_animation"):
            functions.screensaver(menu, midiports, saving, MagicMock(), MagicMock())

        # refreshes every 0.2 s
        self.assertLessEqual(menu.render_screensaver.call_count, 5)


if __name__ == "__main__":
    unittest.main()
