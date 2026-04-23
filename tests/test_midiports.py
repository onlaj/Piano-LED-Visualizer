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


class FakeInputBackend:
    def __init__(self):
        self.calls = []

    def ignore_types(self, sysex=True, timing=True, active_sense=True):
        self.calls.append(
            {
                "sysex": sysex,
                "timing": timing,
                "active_sense": active_sense,
            }
        )


class FakeInputPort:
    def __init__(self):
        self._rt = FakeInputBackend()


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
        ports.scheduled_forward_queue = deque(maxlen=forward_maxlen)
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
            "scheduled_sent": 0,
            "scheduled_late_messages": 0,
            "scheduled_late_max_ms": 0.0,
            "scheduled_late_last_ms": 0.0,
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

    def test_enqueue_rtp_message_routes_software_notes_through_forward_queue(self):
        ports = self.make_ports()
        msg = FakeMidiMessage(note=72)

        queued = ports.enqueue_rtp_message(msg)

        self.assertTrue(queued)
        self.assertEqual(len(ports.playport.sent), 0)
        self.assertEqual(len(ports.live_forward_queue), 1)

        ports._flush_live_forward_queue_once()

        self.assertEqual(len(ports.playport.sent), 1)
        self.assertIs(ports.playport.sent[0], msg)

    def test_enqueue_rtp_message_ignores_transport_messages_before_rtp_queue(self):
        ports = self.make_ports()

        clock_queued = ports.enqueue_rtp_message(FakeMidiMessage(msg_type="clock"))
        start_queued = ports.enqueue_rtp_message(FakeMidiMessage(msg_type="start"))

        self.assertFalse(clock_queued)
        self.assertFalse(start_queued)
        self.assertEqual(len(ports.live_forward_queue), 0)
        self.assertEqual(ports.ignored_counts["clock"], 1)
        self.assertEqual(ports.ignored_counts["start"], 1)

    def test_schedule_rtp_message_waits_until_due_time(self):
        ports = self.make_ports(forward_maxlen=16)
        msg = FakeMidiMessage(note=74)

        with patch("lib.midiports.time.perf_counter", return_value=100.0):
            queued = ports.schedule_rtp_message(msg, due_time=100.5)

        self.assertTrue(queued)
        self.assertEqual(len(ports.playport.sent), 0)
        self.assertEqual(len(ports.scheduled_forward_queue), 1)

        with patch("lib.midiports.time.perf_counter", return_value=100.1):
            self.assertFalse(ports._flush_live_forward_queue_once())
        self.assertEqual(len(ports.playport.sent), 0)

        with patch("lib.midiports.time.perf_counter", side_effect=[100.6, 100.7]):
            self.assertTrue(ports._flush_live_forward_queue_once())

        self.assertEqual(len(ports.playport.sent), 1)
        self.assertIs(ports.playport.sent[0], msg)

    def test_immediate_rtp_messages_are_not_blocked_by_future_scheduled_messages(self):
        ports = self.make_ports(forward_maxlen=16)
        scheduled = FakeMidiMessage(note=80)
        immediate = FakeMidiMessage(note=81)

        with patch("lib.midiports.time.perf_counter", return_value=100.0):
            ports.schedule_rtp_message(scheduled, due_time=101.0)
            ports.enqueue_rtp_message(immediate)

        with patch("lib.midiports.time.perf_counter", side_effect=[100.1, 100.2]):
            self.assertTrue(ports._flush_live_forward_queue_once())

        self.assertEqual([msg.note for msg in ports.playport.sent], [81])
        self.assertEqual(len(ports.scheduled_forward_queue), 1)

    def test_scheduled_rtp_lateness_is_tracked_in_diagnostics(self):
        ports = self.make_ports(forward_maxlen=16)
        msg = FakeMidiMessage(note=82)

        with patch("lib.midiports.time.perf_counter", return_value=100.0):
            ports.schedule_rtp_message(msg, due_time=100.0)

        with patch("lib.midiports.time.perf_counter", side_effect=[100.25, 100.30, 100.30]), patch(
            "lib.midiports._get_cached_input_names", return_value=[]
        ), patch("lib.midiports._get_cached_output_names", return_value=[]):
            ports._flush_live_forward_queue_once()
            diagnostics = ports.get_rtp_diagnostics()

        self.assertEqual(diagnostics["scheduled_late_messages"], 1)
        self.assertGreaterEqual(diagnostics["scheduled_late_max_ms"], 200.0)

    def test_configure_input_backend_filters_enables_rtmidi_timing_filter(self):
        ports = self.make_ports()
        input_port = FakeInputPort()

        ports._configure_input_backend_filters(input_port)

        self.assertEqual(
            input_port._rt.calls,
            [
                {
                    "sysex": False,
                    "timing": True,
                    "active_sense": True,
                }
            ],
        )

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

    def test_runtime_diagnostics_include_queue_depth_and_age_peaks(self):
        ports = self.make_ports()

        with patch("lib.midiports.time.perf_counter", side_effect=[100.0, 100.0, 100.001, 103.0]), patch(
            "lib.midiports._get_cached_input_names", return_value=[]
        ), patch("lib.midiports._get_cached_output_names", return_value=[]):
            ports.msg_callback(FakeMidiMessage())
            diagnostics = ports.get_runtime_diagnostics()

        live_input = diagnostics["queues"]["live_input"]
        live_forward = diagnostics["queues"]["live_forward"]

        self.assertEqual(live_input["current_depth"], 1)
        self.assertEqual(live_input["max_depth"], 1)
        self.assertEqual(live_input["current_oldest_age_ms"], 3000.0)
        self.assertEqual(live_input["max_oldest_age_ms"], 3000.0)
        self.assertEqual(live_forward["current_depth"], 1)

    def test_websocket_publish_loop_does_not_back_off_while_queue_still_has_backlog(self):
        ports = self.make_ports()
        ports.worker_running = True
        ports.websocket_publish_queue.extend([(FakeMidiMessage(), 0.0), (FakeMidiMessage(), 0.0)])

        def fake_flush():
            ports.websocket_publish_queue.popleft()
            ports.worker_running = False
            return False

        ports._flush_websocket_publish_queue_once = fake_flush

        with patch("lib.midiports.time.sleep") as sleep_mock:
            ports._websocket_publish_loop()

        sleep_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
