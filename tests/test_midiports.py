#!/usr/bin/env python3

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lib.midiports import MidiPorts, _close_input_safely


class FakeSettings:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.changed = {}

    def get_setting_value(self, name):
        return self.values.get(name)

    def change_setting_value(self, name, value):
        self.values[name] = value
        self.changed[name] = value


class FakePort:
    def close(self):
        pass


class TestMidiPortHelpers(unittest.TestCase):
    def setUp(self):
        self.ports = MidiPorts.__new__(MidiPorts)

    def test_extract_descriptive_port_name_strips_trailing_client_port(self):
        self.assertEqual(
            self.ports._extract_descriptive_port_name(
                "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6"
            ),
            "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1",
        )

    def test_extract_descriptive_port_name_keeps_name_without_id(self):
        self.assertEqual(
            self.ports._extract_descriptive_port_name("Some Piano"),
            "Some Piano",
        )

    def test_extract_descriptive_port_name_handles_default(self):
        self.assertIsNone(self.ports._extract_descriptive_port_name("default"))

    def test_extract_device_name_uses_first_token(self):
        self.assertEqual(
            self.ports._extract_device_name(
                "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6"
            ),
            "rtpmidid",
        )

    def test_resolve_port_name_exact_match(self):
        available = ["rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6"]
        self.assertEqual(
            self.ports._resolve_port_name(
                "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6",
                available,
            ),
            available[0],
        )

    def test_resolve_port_name_matches_renamed_port(self):
        configured = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6"
        available = ["rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:9"]
        self.assertEqual(
            self.ports._resolve_port_name(configured, available),
            available[0],
        )

    def test_resolve_port_name_returns_none_when_absent(self):
        configured = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6"
        available = ["Midi Through-Midi Through Port-0"]
        self.assertIsNone(self.ports._resolve_port_name(configured, available))

    def test_resolve_port_name_handles_default_and_empty(self):
        self.assertIsNone(self.ports._resolve_port_name("default", ["a"]))
        self.assertIsNone(self.ports._resolve_port_name("a", []))
        self.assertIsNone(self.ports._resolve_port_name(None, ["a"]))


class TestFindAndSetPiano(unittest.TestCase):
    def setUp(self):
        self.opened_inputs = []
        self.opened_outputs = []

        def fake_open_input(name, *args, **kwargs):
            self.opened_inputs.append(name)
            return FakePort()

        def fake_open_output(name, *args, **kwargs):
            self.opened_outputs.append(name)
            return FakePort()

        self.patches = [
            patch("lib.midiports._refresh_port_cache", lambda: None),
            patch("lib.midiports.mido.open_input", side_effect=fake_open_input),
            patch("lib.midiports.mido.open_output", side_effect=fake_open_output),
            patch("lib.midiports.time.sleep", lambda *_: None),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def _make_instance(self, configured, available_inputs, available_outputs=None):
        if available_outputs is None:
            available_outputs = available_inputs

        instance = MidiPorts.__new__(MidiPorts)
        instance.usersettings = FakeSettings({"piano_port": configured})
        instance.piano_in = None
        instance.piano_in_name = None
        instance.piano_out = None
        instance.inport = None
        instance.playport = None

        patchers = [
            patch("lib.midiports._get_cached_input_names", return_value=list(available_inputs)),
            patch("lib.midiports._get_cached_output_names", return_value=list(available_outputs)),
        ]
        for p in patchers:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patchers])
        return instance

    def test_configured_port_is_persisted_when_renamed(self):
        configured = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6"
        available = ["rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:9"]
        instance = self._make_instance(configured, available)

        instance.find_and_set_piano()

        self.assertEqual(instance.usersettings.values["piano_port"], available[0])
        self.assertIn(available[0], self.opened_inputs)

    def test_absent_configured_port_uses_fallback_without_changing_settings(self):
        configured = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6"
        available = ["Midi Through-Midi Through Port-0", "Network Export-Network Export 0"]
        instance = self._make_instance(configured, available)

        instance.find_and_set_piano()

        self.assertIsNotNone(instance.piano_in)
        self.assertEqual(instance.usersettings.values["piano_port"], configured)
        self.assertNotIn("piano_port", instance.usersettings.changed)

    def test_default_setup_discovers_and_persists_a_port(self):
        available = ["Some Piano-Some Piano MIDI 1"]
        instance = self._make_instance("default", available)

        instance.find_and_set_piano()

        self.assertEqual(instance.usersettings.values["piano_port"], available[0])
        self.assertIn(available[0], self.opened_inputs)

    def test_no_usable_port_leaves_instance_unopened(self):
        available = ["Midi Through-Midi Through Port-0"]
        instance = self._make_instance(
            "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6",
            available,
        )

        instance.find_and_set_piano()

        self.assertIsNone(instance.piano_in)


    def test_device_name_match_does_not_persist_settings(self):
        configured = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6"
        available = ["rtpmidid:Network Export 128:0", "rtpmidid:arch-piano 128:1"]
        instance = self._make_instance(configured, available)

        instance.find_and_set_piano()

        self.assertIsNotNone(instance.piano_in)
        self.assertEqual(instance.usersettings.values["piano_port"], configured)
        self.assertNotIn("piano_port", instance.usersettings.changed)


class TestPianoReopen(unittest.TestCase):
    def _make_instance(self, configured, available_inputs):
        instance = MidiPorts.__new__(MidiPorts)
        instance.usersettings = FakeSettings({"piano_port": configured})
        instance.piano_in = None
        instance.piano_in_name = None
        instance.piano_out = None
        return instance

    def test_piano_needs_reopen_on_port_number_change(self):
        configured = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:5"
        available = ["rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:4"]
        instance = self._make_instance(configured, available)
        instance.piano_in_name = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:5"

        self.assertTrue(instance._piano_needs_reopen(available))

    def test_piano_does_not_reopen_when_port_unchanged(self):
        configured = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:4"
        available = ["rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:4"]
        instance = self._make_instance(configured, available)
        instance.piano_in_name = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:4"

        self.assertFalse(instance._piano_needs_reopen(available))

    def test_piano_does_not_reopen_when_configured_absent(self):
        instance = self._make_instance("default", ["rtpmidid:Network Export 128:0"])
        instance.piano_in_name = None

        self.assertFalse(instance._piano_needs_reopen(["rtpmidid:Network Export 128:0"]))


class OrderedPort:
    """Fake input that records a close() before cancel_callback() or close_port().

    Recorded rather than raised, because _close_port() swallows exceptions.
    """

    def __init__(self, calls, closed=False):
        self.calls = calls
        self.closed = closed
        self.violation = False
        self._rt = self

    def cancel_callback(self):
        self.calls.append("cancel")

    def close_port(self):
        if "cancel" not in self.calls:
            self.violation = True
        self.calls.append("close_port")

    def close(self):
        if "cancel" not in self.calls or "close_port" not in self.calls:
            self.violation = True
        self.calls.append("close")
        self.closed = True


class TestCloseInputSafely(unittest.TestCase):
    def setUp(self):
        sleep_patch = patch("lib.midiports.time.sleep")
        self.sleep = sleep_patch.start()
        self.addCleanup(sleep_patch.stop)

    def test_callback_is_cancelled_before_close(self):
        calls = []
        port = OrderedPort(calls)
        _close_input_safely(port)
        self.assertEqual(calls, ["cancel", "close_port", "close"])
        self.assertFalse(port.violation)

    def test_sleeps_between_cancel_and_close(self):
        calls = []
        self.sleep.side_effect = lambda *_: calls.append("sleep")
        _close_input_safely(OrderedPort(calls))
        self.assertEqual(calls, ["cancel", "sleep", "close_port", "close"])

    def test_none_is_ignored(self):
        _close_input_safely(None)
        self.sleep.assert_not_called()

    def test_port_without_rt_is_still_closed(self):
        port = FakePort()
        closed = []
        port.close = lambda: closed.append(True)
        _close_input_safely(port)
        self.assertEqual(closed, [True])

    def test_already_closed_port_is_skipped(self):
        calls = []
        _close_input_safely(OrderedPort(calls, closed=True))
        self.assertEqual(calls, [])
        self.sleep.assert_not_called()

    def test_cancel_error_does_not_prevent_close(self):
        calls = []
        port = OrderedPort(calls)

        def fail():
            raise RuntimeError("cancel failed")

        port.cancel_callback = fail
        _close_input_safely(port)
        self.assertTrue(port.closed)


class TestReconnectPorts(unittest.TestCase):
    PORT = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6"
    RENUMBERED = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:9"

    def setUp(self):
        self.patches = [
            patch("lib.midiports._refresh_port_cache", lambda: None),
            patch("lib.midiports.time.sleep", lambda *_: None),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def _make_instance(self, available_inputs, piano_in_name, piano_in, configured=PORT):
        instance = MidiPorts.__new__(MidiPorts)
        instance.usersettings = FakeSettings({"piano_port": configured})
        instance.piano_in = piano_in
        instance.piano_in_name = piano_in_name
        instance.piano_out = FakePort()
        instance.open_piano_ports = MagicMock()
        instance.open_computer_ports = MagicMock()
        instance._open_piano_output_for_input = MagicMock()

        inputs_patch = patch(
            "lib.midiports._get_cached_input_names", return_value=list(available_inputs)
        )
        inputs_patch.start()
        self.addCleanup(inputs_patch.stop)
        return instance

    def test_healthy_piano_is_not_reopened(self):
        instance = self._make_instance([self.PORT], self.PORT, OrderedPort([]))
        instance.reconnect_ports()
        instance.open_piano_ports.assert_not_called()
        instance.open_computer_ports.assert_called_once()

    def test_renumbered_port_is_reopened(self):
        instance = self._make_instance([self.RENUMBERED], self.PORT, OrderedPort([]))
        instance.reconnect_ports()
        instance.open_piano_ports.assert_called_once()

    def test_missing_input_is_reopened(self):
        instance = self._make_instance([self.PORT], None, None)
        instance.reconnect_ports()
        instance.open_piano_ports.assert_called_once()

    def test_closed_input_is_reopened(self):
        instance = self._make_instance([self.PORT], self.PORT, OrderedPort([], closed=True))
        instance.reconnect_ports()
        instance.open_piano_ports.assert_called_once()

    def test_absent_configured_port_is_reopened(self):
        instance = self._make_instance([], self.PORT, OrderedPort([]))
        instance.reconnect_ports()
        instance.open_piano_ports.assert_called_once()

    def test_fallback_is_kept_while_configured_port_is_absent(self):
        instance = self._make_instance(["Other Piano 20:0"], "Other Piano 20:0", OrderedPort([]))
        instance.reconnect_ports()
        instance.open_piano_ports.assert_not_called()

    def test_configured_port_replaces_fallback_when_it_returns(self):
        instance = self._make_instance(
            ["Other Piano 20:0", self.PORT], "Other Piano 20:0", OrderedPort([])
        )
        instance.reconnect_ports()
        instance.open_piano_ports.assert_called_once()

    def test_missing_output_is_retried_without_reopening_input(self):
        instance = self._make_instance([self.PORT], self.PORT, OrderedPort([]))
        instance.piano_out = None
        instance.reconnect_ports()
        instance.open_piano_ports.assert_not_called()
        instance._open_piano_output_for_input.assert_called_once_with(self.PORT)

    def test_default_setting_keeps_healthy_discovered_port(self):
        instance = self._make_instance(
            ["Some Piano 20:0"], "Some Piano 20:0", OrderedPort([]), configured="default"
        )
        instance.reconnect_ports()
        instance.open_piano_ports.assert_not_called()

    def test_default_setting_reopens_when_discovered_port_is_gone(self):
        instance = self._make_instance(
            ["Other Piano 20:0"], "Some Piano 20:0", OrderedPort([]), configured="default"
        )
        instance.reconnect_ports()
        instance.open_piano_ports.assert_called_once()


class TestInputPortsCloseSafely(unittest.TestCase):
    PORT = "rtpmidid:Roland Digital Piano-Roland Digital Piano MIDI 1 128:6"

    def setUp(self):
        self.patches = [
            patch("lib.midiports._refresh_port_cache", lambda: None),
            patch("lib.midiports._get_cached_input_names", return_value=[self.PORT]),
            patch("lib.midiports.time.sleep", lambda *_: None),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_piano_reopen_closes_old_input_safely(self):
        calls = []
        old = OrderedPort(calls)
        new = OrderedPort([])
        instance = MidiPorts.__new__(MidiPorts)
        instance.usersettings = FakeSettings({"piano_port": self.PORT})
        instance.piano_in = old
        instance.piano_in_name = "old"
        instance.inport = old
        instance.route_midi_message = lambda msg, source: None

        with patch("lib.midiports.mido.open_input", return_value=new):
            self.assertTrue(instance._open_piano_input(self.PORT, sync_settings=False))

        self.assertEqual(calls, ["cancel", "close_port", "close"])
        self.assertFalse(old.violation)
        self.assertIs(instance.piano_in, new)
        self.assertIs(instance.inport, new)
        self.assertEqual(instance.piano_in_name, self.PORT)

    def test_computer_reopen_closes_old_input_safely(self):
        calls = []
        old = OrderedPort(calls)
        instance = MidiPorts.__new__(MidiPorts)
        instance.usersettings = FakeSettings({"computer_port": "default"})
        instance.computer_in = old
        instance.computer_out = None
        instance.release_forwarded_notes = lambda *args, **kwargs: None
        instance._router = MagicMock()

        instance.open_computer_ports()

        self.assertEqual(calls, ["cancel", "close_port", "close"])
        self.assertFalse(old.violation)
        self.assertIsNone(instance.computer_in)


if __name__ == "__main__":
    unittest.main()
