#!/usr/bin/env python3

import sys
import unittest

sys.path.append("./")
sys.path.append("../")

from lib.rtpmidi_diagnostics import parse_rtpmidid_cli_output, parse_rtpmidid_status


DISCONNECTED_STATUS = {
    "result": {
        "mdns": {
            "remote_announcements": [
                {"hostname": "PC_Robin-2.local", "name": "OSCMidi", "port": 5004}
            ]
        },
        "router": [
            {
                "id": 7,
                "type": "network_rtpmidi_client_t",
                "peer": {
                    "status": "0",
                    "remote": {"hostname": "null", "name": "", "port": 0, "ssrc": 0},
                },
                "stats": {"recv": 5690, "sent": 0},
            },
            {
                "id": 5,
                "type": "local_alsa_listener_t",
                "name": "RtMidiOut Client-RtMidi output <-> OSCMidi",
                "status": "CONNECTED",
                "endpoints": [{"hostname": "PC_Robin-2.local", "port": "5004"}],
                "send_to": [7],
                "stats": {"recv": 0, "sent": 6095},
            },
        ],
    }
}


CONNECTED_STATUS = {
    "result": {
        "mdns": {
            "remote_announcements": [
                {"hostname": "PC_Robin-2.local", "name": "OSCMidi", "port": 5004}
            ]
        },
        "router": [
            {
                "id": 7,
                "type": "network_rtpmidi_client_t",
                "peer": {
                    "status": "CONNECTED",
                    "remote": {
                        "hostname": "PC_Robin-2.local",
                        "name": "OSCMidi",
                        "port": 5004,
                        "ssrc": 12345,
                    },
                },
                "stats": {"recv": 10, "sent": 20},
            },
            {
                "id": 5,
                "type": "local_alsa_listener_t",
                "name": "RtMidiOut Client-RtMidi output <-> OSCMidi",
                "status": "CONNECTED",
                "endpoints": [{"hostname": "PC_Robin-2.local", "port": "5004"}],
                "send_to": [7],
                "stats": {"recv": 2, "sent": 30},
            },
        ],
    }
}


class TestRtpMidiDiagnostics(unittest.TestCase):
    def test_cli_output_parser_ignores_echoed_request_line(self):
        output = """>>> {"method": "status", "params": []}
{
  "id": null,
  "result": {
    "router": []
  }
}
"""

        parsed = parse_rtpmidid_cli_output(output)

        self.assertIn("result", parsed)
        self.assertEqual(parsed["result"]["router"], [])

    def test_announced_osc_session_is_not_ready_until_network_peer_connects(self):
        diagnostics = parse_rtpmidid_status(
            DISCONNECTED_STATUS,
            play_port="rtpmidid:OSCMidi 129:2",
        )

        self.assertFalse(diagnostics["play_network_ready"])
        self.assertEqual(diagnostics["rtpmidi_peer_status"], "0")
        self.assertEqual(diagnostics["rtpmidi_remote_host"], "PC_Robin-2.local:5004")
        self.assertIn("not connected", diagnostics["rtpmidi_error_reason"].lower())

    def test_connected_osc_session_is_ready_when_network_peer_has_remote_identity(self):
        diagnostics = parse_rtpmidid_status(
            CONNECTED_STATUS,
            play_port="rtpmidid:OSCMidi 129:2",
        )

        self.assertTrue(diagnostics["play_network_ready"])
        self.assertEqual(diagnostics["rtpmidi_peer_status"], "CONNECTED")
        self.assertEqual(diagnostics["rtpmidi_remote_host"], "PC_Robin-2.local:5004")
        self.assertIsNone(diagnostics["rtpmidi_error_reason"])


if __name__ == "__main__":
    unittest.main()
