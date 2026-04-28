#!/usr/bin/env python3

import sys
import unittest

sys.path.append("./")
sys.path.append("../")

from webinterface.views_api import configured_ports_missing_from_available, parse_aconnect_ports


ACONNECT_SAMPLE = """client 16: 'USB AudioDevice' [type=kernel,card=0]
    0 'USB AudioDevice MIDI 1'
        Connecting To: 129:0
client 128: 'rtpmidid' [type=user,pid=1140]
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


if __name__ == "__main__":
    unittest.main()
