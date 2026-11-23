#!/usr/bin/env python3

import sys
import os
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lib.midiports import MidiPorts


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


if __name__ == "__main__":
    unittest.main()
