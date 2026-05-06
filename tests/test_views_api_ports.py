#!/usr/bin/env python3

import sys
import unittest

sys.path.append("./")
sys.path.append("../")

from webinterface.views_api import (
    build_get_ports_response,
    configured_ports_missing_from_available,
    parse_aconnect_ports,
)


ACONNECT_SAMPLE = """client 16: 'USB AudioDevice' [type=kernel,card=0]
    0 'USB AudioDevice MIDI 1'
        Connecting To: 129:0
client 128: 'rtpmidid' [type=user,pid=1140]
    0 'Network Export  '
    1 'Announcements   '
    2 'OSCMidi         '
        Connected From: 130:0[real:0]
client 129: 'RtMidiIn Client' [type=user,pid=2537]
    0 'RtMidi input    '
        Connected From: 16:0
client 130: 'RtMidiOut Client' [type=user,pid=2537]
    0 'RtMidi output   '
        Connecting To: 128:2[real:0]
"""


class TestViewsApiPorts(unittest.TestCase):
    def test_parse_aconnect_ports_keeps_rtmidi_clients_visible_in_graph(self):
        ports = parse_aconnect_ports(ACONNECT_SAMPLE, "all")
        port_ids = {port["id"] for port in ports}

        self.assertIn("129:0", port_ids)
        self.assertIn("130:0", port_ids)
        self.assertIn("128:2", port_ids)
        self.assertIn("16:0", port_ids)

    def test_parse_aconnect_ports_hides_fake_rtp_meta_ports_from_graph(self):
        ports = parse_aconnect_ports(ACONNECT_SAMPLE, "all")
        port_ids = {port["id"] for port in ports}

        self.assertNotIn("128:0", port_ids)
        self.assertNotIn("128:1", port_ids)

    def test_configured_ports_missing_from_available_reports_absent_usb_without_selecting_it(self):
        missing = configured_ports_missing_from_available(
            [
                "Midi Through:Midi Through Port-0 14:0",
                "rtpmidid:PC_Robin 128:2",
            ],
            "USB AudioDevice:USB AudioDevice MIDI 1 16:0",
            "default",
            None,
        )

        self.assertEqual(
            missing,
            [
                "USB AudioDevice:USB AudioDevice MIDI 1 16:0",
            ],
        )

    def test_get_ports_response_exposes_rtpmidi_network_diagnostics(self):
        response = build_get_ports_response(
            raw_input_ports=["USB AudioDevice:USB AudioDevice MIDI 1 16:0"],
            raw_output_ports=["rtpmidid:OSCMidi 129:2"],
            configured_input="USB AudioDevice:USB AudioDevice MIDI 1 16:0",
            configured_secondary_input="default",
            configured_play="rtpmidid:OSCMidi 129:2",
            midi_logging="1",
            connected_ports="",
            rtp_diagnostics={
                "actual_input_port": "USB AudioDevice:USB AudioDevice MIDI 1 16:0",
                "actual_play_port": "rtpmidid:OSCMidi 129:2",
            },
            runtime_diagnostics={},
            rtpmidi_network_diagnostics={
                "play_network_ready": False,
                "rtpmidi_peer_status": "0",
                "rtpmidi_remote_host": "PC_Robin-2.local:5004",
                "rtpmidi_error_reason": "OSCMidi RTP peer is visible but not connected",
            },
        )

        self.assertEqual(response["input_ports"], ["USB AudioDevice:USB AudioDevice MIDI 1 16:0"])
        self.assertEqual(response["output_ports"], ["rtpmidid:OSCMidi 129:2"])
        self.assertFalse(response["play_network_ready"])
        self.assertEqual(response["rtp_diagnostics"]["play_network_ready"], False)
        self.assertEqual(response["rtpmidi_remote_host"], "PC_Robin-2.local:5004")

    def test_get_ports_response_lists_usb_device_as_selectable_play_output(self):
        response = build_get_ports_response(
            raw_input_ports=["USB AudioDevice:USB AudioDevice MIDI 1 16:0"],
            raw_output_ports=[
                "USB AudioDevice:USB AudioDevice MIDI 1 16:0",
                "rtpmidid:OSCMidi 129:2",
            ],
            configured_input="USB AudioDevice:USB AudioDevice MIDI 1 16:0",
            configured_secondary_input="default",
            configured_play="USB AudioDevice:USB AudioDevice MIDI 1 16:0",
            midi_logging="0",
            connected_ports="",
            rtp_diagnostics={},
            runtime_diagnostics={},
            rtpmidi_network_diagnostics={},
        )

        self.assertIn("USB AudioDevice:USB AudioDevice MIDI 1 16:0", response["output_ports"])
        self.assertEqual(response["play_port"], "USB AudioDevice:USB AudioDevice MIDI 1 16:0")


if __name__ == "__main__":
    unittest.main()
