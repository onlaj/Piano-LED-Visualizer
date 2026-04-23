#!/usr/bin/env python3

import sys
import unittest
from collections import deque
from unittest.mock import patch

sys.path.append("./")
sys.path.append("../")

from lib.midiports import MidiPorts


class FakePlayPort:
    def __init__(self):
        self.sent = []

    def send(self, msg):
        self.sent.append(msg)


class FakeMidiMessage:
    def __init__(self, msg_type="note_on", channel=0, note=60, velocity=100, time=0):
        self.type = msg_type
        self.channel = channel
        self.note = note
        self.velocity = velocity
        self.time = time

    def __str__(self):
        return (
            f"{self.type} channel={self.channel} note={self.note} "
            f"velocity={self.velocity} time={self.time}"
        )


class TestMidiPorts(unittest.TestCase):
    def make_ports(self, *, midi_maxlen=4, websocket_maxlen=4, forward_maxlen=4):
        ports = MidiPorts.__new__(MidiPorts)
        ports.midifile_queue = deque(maxlen=500)
        ports.midi_queue = deque(maxlen=midi_maxlen)
        ports.websocket_midi_queue = deque(maxlen=websocket_maxlen)
        ports.live_forward_queue = deque(maxlen=forward_maxlen)
        ports.websocket_publish_queue = deque(maxlen=forward_maxlen)
        ports.drop_counter = 0
        ports.drop_counts = {}
        ports.ignored_counts = {}
        ports.forward_stats = {
            "live_sent": 0,
            "live_send_errors": 0,
            "websocket_sent": 0,
            "websocket_dropped": 0,
            "send_time_total_ms": 0.0,
            "send_time_max_ms": 0.0,
        }
        ports.last_activity = 0
        ports.inport = None
        ports.playport = FakePlayPort()
        ports.midipending = None
        ports.midi_monitor_thread = None
        ports.monitor_running = False
        ports.queue_reserved_noteoff_slots = 1
        ports.last_reconnect_time = None
        ports.reconnect_count = 0
        ports.actual_input_port = None
        ports.actual_play_port = None
        ports.last_resolved_input_port = None
        ports.last_resolved_play_port = None
        ports.last_resolution_reason = {}
        ports.ignored_message_types = {"clock", "active_sensing"}
        return ports

    def test_live_input_is_not_forwarded_synchronously(self):
        ports = self.make_ports()
        msg = FakeMidiMessage()

        ports.msg_callback(msg)

        self.assertEqual(len(ports.midi_queue), 1)
        self.assertEqual(
            len(ports.playport.sent),
            0,
            "Live MIDI input should not block inside the callback by sending immediately",
        )
        self.assertEqual(len(ports.live_forward_queue), 1)

        ports._flush_live_forward_queue_once()

        self.assertEqual(len(ports.playport.sent), 1)
        self.assertIs(ports.playport.sent[0], msg)

    def test_queue_reserves_space_for_note_off_without_evicting_accepted_events(self):
        ports = self.make_ports(midi_maxlen=4, forward_maxlen=16)
        first = FakeMidiMessage(note=60)
        second = FakeMidiMessage(note=61)
        third = FakeMidiMessage(note=62)
        dropped_note_on = FakeMidiMessage(note=63)
        note_off = FakeMidiMessage(msg_type="note_off", note=60, velocity=0)

        ports.msg_callback(first)
        ports.msg_callback(second)
        ports.msg_callback(third)
        ports.msg_callback(dropped_note_on)
        ports.msg_callback(note_off)

        queued = [msg.note for msg, _ in ports.midi_queue]
        queued_types = [msg.type for msg, _ in ports.midi_queue]

        self.assertEqual(queued, [60, 61, 62, 60])
        self.assertEqual(queued_types, ["note_on", "note_on", "note_on", "note_off"])
        self.assertEqual(ports.drop_counter, 1)
        self.assertEqual(ports.drop_counts["live_note_on"], 1)

    def test_websocket_input_queues_playback_instead_of_sending_synchronously(self):
        ports = self.make_ports()

        ports.add_websocket_midi_message("midi_eventnote_on channel=0 note=64 velocity=90 time=0")

        self.assertEqual(len(ports.websocket_midi_queue), 1)
        self.assertEqual(len(ports.live_forward_queue), 1)
        self.assertEqual(len(ports.playport.sent), 0)

        ports._flush_live_forward_queue_once()

        self.assertEqual(len(ports.playport.sent), 1)
        self.assertEqual(ports.playport.sent[0].note, 64)

    def test_realtime_clock_is_ignored_before_entering_live_queues(self):
        ports = self.make_ports()

        ports.msg_callback(FakeMidiMessage(msg_type="clock"))

        self.assertEqual(len(ports.midi_queue), 0)
        self.assertEqual(len(ports.live_forward_queue), 0)
        self.assertEqual(len(ports.websocket_publish_queue), 0)
        self.assertEqual(ports.ignored_counts["clock"], 1)

    def test_diagnostics_refresh_runtime_play_port_label_from_current_alsa_slot(self):
        ports = self.make_ports()
        ports.actual_play_port = "rtpmidid:PC_Robin 128:3"

        with patch("lib.midiports._get_cached_input_names", return_value=[]), patch(
            "lib.midiports._get_cached_output_names",
            return_value=[
                "rtpmidid:OSCMidi 128:3",
                "rtpmidid:PC_Robin 128:4",
            ],
        ):
            diagnostics = ports.get_rtp_diagnostics()

        self.assertEqual(diagnostics["actual_play_port"], "rtpmidid:OSCMidi 128:3")


if __name__ == "__main__":
    unittest.main()
