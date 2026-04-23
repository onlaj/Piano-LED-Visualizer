#!/usr/bin/env python3

import sys
import unittest

sys.path.append("./")
sys.path.append("../")

from lib.midiport_resolver import (
    PortResolutionStatus,
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
