#!/usr/bin/env python3

import sys
import unittest

sys.path.append("./")
sys.path.append("../")

from lib.midiport_resolver import (
    PortResolutionStatus,
    pick_default_input_port,
    pick_default_output_port,
    refresh_runtime_port_name,
    is_fake_rtp_port,
    resolve_input_port,
    resolve_output_port,
)


class TestMidiPortResolver(unittest.TestCase):
    def test_fake_rtp_ports_are_rejected(self):
        self.assertTrue(is_fake_rtp_port("rtpmidid:Network Export 128:1"))
        self.assertTrue(is_fake_rtp_port("rtpmidid:Announcements 128:2"))
        self.assertFalse(is_fake_rtp_port("rtpmidid:OSCMidiRobin64! 128:3"))

    def test_output_resolution_prefers_real_rtp_session(self):
        resolution = resolve_output_port(
            "rtpmidid:OSCMidiRobin64! 128:9",
            [
                "rtpmidid:Network Export 128:1",
                "rtpmidid:Announcements 128:2",
                "rtpmidid:OSCMidiRobin64! 130:3",
            ],
        )

        self.assertEqual(resolution.status, PortResolutionStatus.RESOLVED_COMPATIBLE)
        self.assertEqual(resolution.selected_port, "rtpmidid:OSCMidiRobin64! 130:3")

    def test_output_resolution_does_not_fallback_to_fake_rtp_port(self):
        resolution = resolve_output_port(
            "rtpmidid:OSCMidiRobin64! 128:9",
            [
                "rtpmidid:Network Export 128:1",
                "rtpmidid:Announcements 128:2",
            ],
        )

        self.assertEqual(resolution.status, PortResolutionStatus.UNAVAILABLE)
        self.assertIsNone(resolution.selected_port)

    def test_output_resolution_rejects_input_only_targets(self):
        resolution = resolve_output_port(
            "USB AudioDevice:USB AudioDevice MIDI 1 16:0",
            [
                "USB AudioDevice:USB AudioDevice MIDI 1 16:0",
                "rtpmidid:OSCMidi 128:2",
            ],
            available_inputs=[
                "USB AudioDevice:USB AudioDevice MIDI 1 16:0",
            ],
        )

        self.assertEqual(resolution.status, PortResolutionStatus.UNAVAILABLE)
        self.assertIsNone(resolution.selected_port)
        self.assertIn("invalid", resolution.reason.lower())

    def test_default_output_selection_skips_internal_and_input_only_ports(self):
        selected = pick_default_output_port(
            [
                "USB AudioDevice:USB AudioDevice MIDI 1 16:0",
                "RtMidiIn Client:RtMidi input 129:0",
                "rtpmidid:OSCMidi 128:2",
            ],
            available_inputs=[
                "USB AudioDevice:USB AudioDevice MIDI 1 16:0",
            ],
        )

        self.assertEqual(selected, "rtpmidid:OSCMidi 128:2")

    def test_input_resolution_matches_same_device_across_dynamic_alsa_ids(self):
        resolution = resolve_input_port(
            "mio:mio MIDI 1 16:0",
            [
                "mio:mio MIDI 1 24:0",
                "Another Device 28:0",
            ],
        )

        self.assertEqual(resolution.status, PortResolutionStatus.RESOLVED_COMPATIBLE)
        self.assertEqual(resolution.selected_port, "mio:mio MIDI 1 24:0")

    def test_default_input_selection_waits_instead_of_using_internal_ports(self):
        selected = pick_default_input_port(
            [
                "Midi Through:Midi Through Port-0 14:0",
                "rtpmidid:Network Export 129:0",
                "rtpmidid:Announcements 129:1",
                "rtpmidid:PC_Robin 129:2",
                "RtMidiIn Client:RtMidi input 128:0",
            ]
        )

        self.assertIsNone(selected)

    def test_default_input_selection_prefers_local_usb_over_rtp_sessions(self):
        selected = pick_default_input_port(
            [
                "Midi Through:Midi Through Port-0 14:0",
                "rtpmidid:PC_Robin 129:2",
                "USB AudioDevice:USB AudioDevice MIDI 1 20:0",
            ]
        )

        self.assertEqual(selected, "USB AudioDevice:USB AudioDevice MIDI 1 20:0")

    def test_input_resolution_rejects_stale_internal_midi_through_setting(self):
        resolution = resolve_input_port(
            "Midi Through:Midi Through Port-0 14:0",
            [
                "Midi Through:Midi Through Port-0 14:0",
            ],
        )

        self.assertEqual(resolution.status, PortResolutionStatus.UNAVAILABLE)
        self.assertIsNone(resolution.selected_port)
        self.assertIn("invalid", resolution.reason.lower())

    def test_runtime_port_name_prefers_same_alsa_slot_over_stale_session_name(self):
        refreshed = refresh_runtime_port_name(
            "rtpmidid:PC_Robin 128:3",
            [
                "rtpmidid:Network Export 128:0",
                "rtpmidid:OSCMidi 128:3",
                "rtpmidid:PC_Robin 128:4",
            ],
        )

        self.assertEqual(refreshed, "rtpmidid:OSCMidi 128:3")


if __name__ == "__main__":
    unittest.main()
