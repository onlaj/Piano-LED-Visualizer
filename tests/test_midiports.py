#!/usr/bin/env python3

import sys
import unittest
from collections import deque
from unittest.mock import patch

sys.path.append("./")
sys.path.append("../")

from lib.midi_queues import MidiQueues
from lib.midiports import MidiPorts


class FakePlayPort:
    def __init__(self, fail_times=0):
        self.sent = []
        self.fail_times = fail_times

    def send(self, msg):
        if self.fail_times:
            self.fail_times -= 1
            raise RuntimeError("temporary RTP send failure")
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
    def __init__(
        self,
        msg_type="note_on",
        channel=0,
        note=60,
        velocity=100,
        time=0,
        control=64,
        value=127,
    ):
        self.type = msg_type
        self.channel = channel
        self.note = note
        self.velocity = velocity
        self.time = time
        self.control = control
        self.value = value

    def __str__(self):
        if self.type == "control_change":
            return (
                f"{self.type} channel={self.channel} control={self.control} "
                f"value={self.value} time={self.time}"
            )
        return (
            f"{self.type} channel={self.channel} note={self.note} "
            f"velocity={self.velocity} time={self.time}"
        )


class TestMidiPorts(unittest.TestCase):
    def make_ports(self, *, midi_maxlen=4, websocket_maxlen=4, forward_maxlen=4):
        ports = MidiPorts.__new__(MidiPorts)
        ports.queues = MidiQueues(
            live_maxlen=midi_maxlen,
            file_maxlen=500,
            websocket_maxlen=websocket_maxlen,
            forward_maxlen=forward_maxlen,
            scheduled_forward_maxlen=forward_maxlen,
            websocket_publish_maxlen=forward_maxlen,
            reserved_noteoff_slots=1,
        )
        ports.midifile_queue = ports.queues.file_queue
        ports.midi_queue = ports.queues.live_visualizer_queue
        ports.websocket_midi_queue = ports.queues.websocket_queue
        ports.learning_midi_queue = ports.queues.live_learning_queue
        ports.live_forward_queue = ports.queues.live_forward_queue
        ports.scheduled_forward_queue = ports.queues.scheduled_forward_queue
        ports.websocket_publish_queue = ports.queues.websocket_publish_queue
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
        ports.on_input_connected = None
        ports.queue_reserved_noteoff_slots = 1
        ports.last_reconnect_time = None
        ports.reconnect_count = 0
        ports.actual_input_port = None
        ports.actual_play_port = None
        ports.last_resolved_input_port = None
        ports.last_resolved_play_port = None
        ports.last_resolution_reason = {}
        ports.port_runtime_reconnects = 0
        ports.ignored_message_types = {"clock", "active_sensing"}
        ports.forward_backoff_until = 0.0
        return ports

    def test_live_input_is_not_forwarded_synchronously(self):
        ports = self.make_ports()
        msg = FakeMidiMessage()

        ports.msg_callback(msg)

        self.assertEqual(len(ports.midi_queue), 1)
        self.assertEqual(len(ports.learning_midi_queue), 1)
        self.assertEqual(
            len(ports.playport.sent),
            0,
            "Live MIDI input should not block inside the callback by sending immediately",
        )
        self.assertEqual(len(ports.live_forward_queue), 1)

        ports._flush_live_forward_queue_once()

        self.assertEqual(len(ports.playport.sent), 1)
        self.assertIs(ports.playport.sent[0], msg)

    def test_learning_queue_does_not_steal_live_visualizer_input(self):
        ports = self.make_ports()
        msg = FakeMidiMessage(note=67)

        ports.msg_callback(msg)

        learning_msg, _ = ports.learning_midi_queue.popleft()
        visualizer_msg, _ = ports.midi_queue.popleft()

        self.assertIs(learning_msg, msg)
        self.assertIs(visualizer_msg, msg)

    def test_live_and_forward_critical_queues_do_not_drop_when_capacity_hint_is_small(self):
        ports = self.make_ports(midi_maxlen=4, forward_maxlen=16)
        first = FakeMidiMessage(note=60)
        second = FakeMidiMessage(note=61)
        third = FakeMidiMessage(note=62)
        fourth = FakeMidiMessage(note=63)
        note_off = FakeMidiMessage(msg_type="note_off", note=60, velocity=0)

        ports.msg_callback(first)
        ports.msg_callback(second)
        ports.msg_callback(third)
        ports.msg_callback(fourth)
        ports.msg_callback(note_off)

        queued = [msg.note for msg, _ in ports.midi_queue]
        queued_types = [msg.type for msg, _ in ports.midi_queue]

        self.assertEqual(queued, [60, 61, 62, 63, 60])
        self.assertEqual(queued_types, ["note_on", "note_on", "note_on", "note_on", "note_off"])
        self.assertEqual(ports.drop_counter, 0)
        self.assertEqual(ports.drop_counts, {})

    def test_websocket_input_queues_playback_instead_of_sending_synchronously(self):
        ports = self.make_ports()

        ports.add_websocket_midi_message("midi_eventnote_on channel=0 note=64 velocity=90 time=0")

        self.assertEqual(len(ports.websocket_midi_queue), 1)
        self.assertEqual(len(ports.live_forward_queue), 1)
        self.assertEqual(len(ports.playport.sent), 0)

        ports._flush_live_forward_queue_once()

        self.assertEqual(len(ports.playport.sent), 1)
        self.assertEqual(ports.playport.sent[0].note, 64)

    def test_websocket_control_change_routes_sustain_to_forward_queue(self):
        ports = self.make_ports()

        ports.add_websocket_midi_message(
            "midi_eventcontrol_change channel=0 control=64 value=127 time=0"
        )

        self.assertEqual(len(ports.websocket_midi_queue), 1)
        self.assertEqual(len(ports.live_forward_queue), 1)

        ports._flush_live_forward_queue_once()

        self.assertEqual(len(ports.playport.sent), 1)
        self.assertEqual(ports.playport.sent[0].type, "control_change")
        self.assertEqual(ports.playport.sent[0].control, 64)
        self.assertEqual(ports.playport.sent[0].value, 127)

    def test_failed_playport_send_keeps_live_forward_message_for_retry(self):
        ports = self.make_ports()
        ports.playport = FakePlayPort(fail_times=1)
        msg = FakeMidiMessage(note=65)

        ports.enqueue_rtp_message(msg)

        with patch("lib.midiports.time.perf_counter", side_effect=[100.0, 100.1, 100.2]):
            self.assertFalse(ports._flush_live_forward_queue_once())

        self.assertEqual(len(ports.playport.sent), 0)
        self.assertEqual(len(ports.live_forward_queue), 1)

        with patch("lib.midiports.time.perf_counter", side_effect=[101.0, 101.1]):
            self.assertTrue(ports._flush_live_forward_queue_once())

        self.assertEqual(len(ports.live_forward_queue), 0)
        self.assertEqual(ports.playport.sent, [msg])

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

    def test_input_reconnect_reopens_port_when_saved_device_returns_with_new_alsa_id(self):
        ports = self.make_ports()
        ports.usersettings = type(
            "FakeSettings",
            (),
            {"get_setting_value": lambda self, name: "mio:mio MIDI 1 16:0"},
        )()
        ports.inport = FakeInputPort()
        ports.actual_input_port = "mio:mio MIDI 1 16:0"
        opened = []

        def fake_open_input(port_name, callback=None):
            opened.append(port_name)
            return FakeInputPort()

        with patch("lib.midiports._get_cached_input_names", return_value=["mio:mio MIDI 1 24:0"]), patch(
            "lib.midiports._get_cached_output_names", return_value=[]
        ), patch("lib.midiports.mido.open_input", side_effect=fake_open_input):
            changed = ports._reconnect_input(force=False)

        self.assertTrue(changed)
        self.assertEqual(opened, ["mio:mio MIDI 1 24:0"])
        self.assertEqual(ports.actual_input_port, "mio:mio MIDI 1 24:0")
        self.assertEqual(ports.port_runtime_reconnects, 1)

    def test_input_connected_callback_fires_once_when_usb_input_is_opened(self):
        ports = self.make_ports()
        ports.usersettings = type(
            "FakeSettings",
            (),
            {"get_setting_value": lambda self, name: "default"},
        )()
        connected = []
        ports.on_input_connected = connected.append

        def fake_open_input(port_name, callback=None):
            return FakeInputPort()

        with patch(
            "lib.midiports._get_cached_input_names",
            return_value=["USB AudioDevice:USB AudioDevice MIDI 1 16:0"],
        ), patch("lib.midiports._get_cached_output_names", return_value=[]), patch(
            "lib.midiports.mido.open_input",
            side_effect=fake_open_input,
        ):
            self.assertTrue(ports._reconnect_input(force=True))
            self.assertFalse(ports._reconnect_input(force=False))

        self.assertEqual(connected, ["USB AudioDevice:USB AudioDevice MIDI 1 16:0"])

    def test_auto_reconnect_iteration_retries_when_input_is_missing_until_usb_appears(self):
        ports = self.make_ports()
        ports.usersettings = type(
            "FakeSettings",
            (),
            {"get_setting_value": lambda self, name: "default"},
        )()
        reconnects = []
        ports.reconnect_ports = lambda force=False: reconnects.append(force)

        with patch(
            "lib.midiports._get_cached_input_names",
            return_value=["USB AudioDevice:USB AudioDevice MIDI 1 16:0"],
        ), patch(
            "lib.midiports._get_cached_output_names",
            return_value=[],
        ), patch(
            "lib.midiports._refresh_port_cache",
            return_value=None,
        ):
            state = ports._auto_reconnect_once(False, False, False)

        self.assertEqual(reconnects, [False])
        self.assertEqual(state, (True, False, False))

    def test_output_reconnect_reopens_port_when_saved_device_returns_with_new_alsa_id(self):
        ports = self.make_ports()
        ports.usersettings = type(
            "FakeSettings",
            (),
            {
                "get_setting_value": lambda self, name: "rtpmidid:OSCMidi 128:3",
                "change_setting_value": lambda self, name, value: None,
            },
        )()
        ports.playport = FakePlayPort()
        ports.actual_play_port = "rtpmidid:OSCMidi 128:3"
        opened = []

        def fake_open_output(port_name):
            opened.append(port_name)
            return FakePlayPort()

        with patch("lib.midiports._get_cached_input_names", return_value=[]), patch(
            "lib.midiports._get_cached_output_names", return_value=["rtpmidid:OSCMidi 130:3"]
        ), patch("lib.midiports.mido.open_output", side_effect=fake_open_output):
            changed = ports._reconnect_output(force=False)

        self.assertTrue(changed)
        self.assertEqual(opened, ["rtpmidid:OSCMidi 130:3"])
        self.assertEqual(ports.actual_play_port, "rtpmidid:OSCMidi 130:3")
        self.assertEqual(ports.port_runtime_reconnects, 1)

    def test_explicit_missing_play_port_does_not_fallback_or_rewrite_setting(self):
        ports = self.make_ports()
        changed_settings = []
        ports.usersettings = type(
            "FakeSettings",
            (),
            {
                "get_setting_value": lambda self, name: "rtpmidid:SavedSession 128:3",
                "change_setting_value": lambda self, name, value: changed_settings.append((name, value)),
            },
        )()
        ports.playport = None
        ports.actual_play_port = None

        with patch("lib.midiports._get_cached_input_names", return_value=[]), patch(
            "lib.midiports._get_cached_output_names", return_value=["rtpmidid:OtherSession 130:3"]
        ), patch("lib.midiports.mido.open_output") as open_output:
            changed = ports._reconnect_output(force=False)

        self.assertFalse(changed)
        open_output.assert_not_called()
        self.assertEqual(changed_settings, [])
        self.assertIsNone(ports.actual_play_port)

    def test_runtime_diagnostics_include_queue_depth_and_age_peaks(self):
        ports = self.make_ports()

        with patch("lib.midiports.time.perf_counter", side_effect=[100.0, 100.0, 103.0]), patch(
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

    def test_live_forward_loop_does_not_sleep_while_backlog_remains(self):
        ports = self.make_ports(forward_maxlen=4)
        ports.worker_running = True
        ports.live_forward_queue.extend(
            [
                (FakeMidiMessage(note=60), 0.0, "stress"),
                (FakeMidiMessage(note=61), 0.0, "stress"),
            ]
        )

        def fake_flush():
            if ports.live_forward_queue:
                ports.live_forward_queue.popleft()
                if not ports.live_forward_queue:
                    ports.worker_running = False
                return True
            ports.worker_running = False
            return False

        ports._flush_live_forward_queue_once = fake_flush

        with patch("lib.midiports.time.sleep") as sleep_mock:
            ports._live_forward_loop()

        sleep_mock.assert_not_called()

    def test_stress_live_and_scheduled_forward_paths_are_lossless(self):
        total = 50_000
        ports = self.make_ports(midi_maxlen=4, forward_maxlen=4)
        ports.playport = FakePlayPort()

        for index in range(total):
            ports.msg_callback(FakeMidiMessage(note=index % 128))
            ports.schedule_rtp_message(
                FakeMidiMessage(note=(index + 1) % 128),
                due_time=float(index),
                enqueued_at=0.0,
                source="stress_scheduled",
            )

        self.assertEqual(len(ports.midi_queue), total)
        self.assertEqual(len(ports.live_forward_queue), total)
        self.assertEqual(len(ports.scheduled_forward_queue), total)
        self.assertEqual(ports.drop_counter, 0)

        with patch("lib.midiports.time.perf_counter", return_value=float(total)):
            while ports.live_forward_queue or ports.scheduled_forward_queue:
                ports._flush_live_forward_queue_once()

        self.assertEqual(len(ports.playport.sent), total * 2)
        self.assertEqual(len(ports.live_forward_queue), 0)
        self.assertEqual(len(ports.scheduled_forward_queue), 0)
        self.assertEqual(ports.drop_counter, 0)


if __name__ == "__main__":
    unittest.main()
