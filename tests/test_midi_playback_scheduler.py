#!/usr/bin/env python3

import sys
import unittest
from unittest.mock import patch

import mido

sys.path.append("./")
sys.path.append("../")

from lib.midi_playback_scheduler import MidiPlaybackScheduler, PlaybackState
from lib.midi_queues import MidiQueues
from lib.reliable_midi_playback_client import ReliablePlaybackError


class FakeMidiPorts:
    def __init__(self):
        self.queues = MidiQueues(live_maxlen=8, file_maxlen=8, scheduled_forward_maxlen=8)
        self.midifile_queue = self.queues.file_queue
        self.scheduled = []
        self.file_enqueued = []
        self.panic_count = 0
        self.usersettings = FakeUserSettings()

    def schedule_rtp_message(self, msg, due_time, source="scheduled_forward"):
        self.scheduled.append((msg, due_time, source))
        self.queues.enqueue_scheduled_forward(msg, enqueued_at=0.0, due_time=due_time, source=source)
        return True

    def clear_scheduled_rtp_messages(self, source=None):
        return self.queues.clear_scheduled_forward(source=source)

    def send_all_notes_off(self):
        self.panic_count += 1

    def should_process_locally(self, msg):
        return msg.type in {"note_on", "note_off", "control_change"}

    def enqueue_file_message(self, msg, timestamp):
        self.file_enqueued.append((msg, timestamp))
        return self.queues.enqueue_file(msg, timestamp=timestamp)


class FakeUserSettings:
    def __init__(self, values=None):
        self.values = {
            "reliable_midi_host": "oscmidi-rtp.local",
            "reliable_midi_port": "5056",
        }
        if values:
            self.values.update(values)

    def get_setting_value(self, name):
        return self.values.get(name)


class FakeReliableHandle:
    def __init__(self, start_perf=100.5):
        self.start_perf = start_perf
        self.waited = False
        self.stopped = False

    def wait_completed(self, timeout=None):
        self.waited = True
        return {"type": "completed", "processed": self.processed, "dropped": 0}

    def stop(self):
        self.stopped = True


class FakeReliableClient:
    def __init__(self, handle=None, error=None):
        self.handle = handle or FakeReliableHandle()
        self.handle.processed = 0
        self.error = error
        self.calls = []

    def play_events(self, song, compiled, start_delay_ms=500):
        self.calls.append((song, compiled, start_delay_ms))
        if self.error:
            raise self.error
        self.handle.processed = compiled.total
        return self.handle


class FakeMenu:
    def __init__(self):
        self.messages = []

    def render_message(self, first, second, duration):
        self.messages.append((first, second, duration))


class FakeSaving:
    def __init__(self):
        self.is_playing_midi = {}
        self.t = None


class TestMidiPlaybackScheduler(unittest.TestCase):
    def test_stop_clears_only_file_queue_and_keeps_live_queue(self):
        midiports = FakeMidiPorts()
        scheduler = MidiPlaybackScheduler(midiports, FakeSaving(), FakeMenu(), None, None)
        live_msg = mido.Message("note_on", note=60, velocity=100)
        file_msg = mido.Message("note_on", note=72, velocity=100)
        midiports.queues.enqueue_live(live_msg, timestamp=1.0)
        midiports.queues.enqueue_file(file_msg, timestamp=2.0)

        scheduler.stop()

        self.assertEqual(list(midiports.queues.file_queue), [])
        self.assertEqual(midiports.queues.drain_live_for_visualizer(), [(live_msg, 1.0)])
        self.assertEqual(midiports.queues.drain_live_for_learning(), [(live_msg, 1.0)])
        self.assertEqual(scheduler.state, PlaybackState.STOPPED)

    def test_stop_clears_only_midifile_scheduled_messages_and_sends_panic(self):
        midiports = FakeMidiPorts()
        scheduler = MidiPlaybackScheduler(midiports, FakeSaving(), FakeMenu(), None, None)
        midifile_msg = mido.Message("note_on", note=60, velocity=100)
        live_msg = mido.Message("note_on", note=72, velocity=100)
        midiports.queues.enqueue_scheduled_forward(
            midifile_msg,
            enqueued_at=1.0,
            due_time=10.0,
            source="midifile",
        )
        midiports.queues.enqueue_scheduled_forward(
            live_msg,
            enqueued_at=1.0,
            due_time=20.0,
            source="live",
        )

        scheduler.stop()

        self.assertEqual(midiports.panic_count, 1)
        self.assertEqual(midiports.queues.snapshot_depths()["scheduled_forward"], 1)
        self.assertEqual(
            midiports.queues.pop_due_scheduled_forward(now_perf=20.0),
            (live_msg, 1.0, 20.0, "live"),
        )

    def test_playback_uses_reliable_by_default_without_rtp_scheduling(self):
        midiports = FakeMidiPorts()
        saving = FakeSaving()
        client = FakeReliableClient()
        scheduler = MidiPlaybackScheduler(
            midiports,
            saving,
            FakeMenu(),
            None,
            None,
            reliable_client_factory=lambda _settings: client,
        )
        mid = mido.MidiFile(ticks_per_beat=480)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.Message("note_on", note=60, velocity=100, time=0))
        track.append(mido.Message("note_off", note=60, velocity=0, time=0))

        with patch("lib.midi_playback_scheduler.mido.MidiFile", return_value=mid), patch(
            "lib.midi_playback_scheduler.time.perf_counter", side_effect=[100.0, 100.0, 100.0, 100.0, 100.0]
        ), patch("lib.midi_playback_scheduler.time.sleep"):
            scheduler.play("song.mid")

        self.assertEqual([msg.note for msg, _ in midiports.file_enqueued], [60, 60])
        self.assertEqual(midiports.queues.drain_file(), [])
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(midiports.scheduled, [])
        self.assertEqual(scheduler.state, PlaybackState.STOPPED)

    def test_reliable_playback_submits_score_without_scheduling_rtp(self):
        midiports = FakeMidiPorts()
        client = FakeReliableClient()
        scheduler = MidiPlaybackScheduler(
            midiports,
            FakeSaving(),
            FakeMenu(),
            None,
            None,
            reliable_client_factory=lambda _settings: client,
        )
        mid = mido.MidiFile(ticks_per_beat=480)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.Message("note_on", note=60, velocity=100, time=0))
        track.append(mido.Message("note_on", note=60, velocity=100, time=0))
        track.append(mido.Message("note_off", note=60, velocity=0, time=240))

        with patch("lib.midi_playback_scheduler.mido.MidiFile", return_value=mid), patch(
            "lib.midi_playback_scheduler.time.perf_counter", side_effect=[100.0] * 20
        ), patch("lib.midi_playback_scheduler.time.sleep"):
            self.assertTrue(scheduler.play("song.mid"))

        self.assertEqual(len(client.calls), 1)
        _song, compiled, start_delay_ms = client.calls[0]
        self.assertEqual(start_delay_ms, 500)
        self.assertEqual(compiled.total, 3)
        self.assertEqual([event["data"] for event in compiled.events[:2]], [[0x90, 60, 100], [0x90, 60, 100]])
        self.assertEqual(midiports.scheduled, [])
        self.assertEqual([msg.note for msg, _ in midiports.file_enqueued], [60, 60, 60])
        self.assertTrue(client.handle.waited)

    def test_reliable_failure_refuses_playback_without_rtp_fallback(self):
        midiports = FakeMidiPorts()
        client = FakeReliableClient(error=ReliablePlaybackError("connect failed"))
        scheduler = MidiPlaybackScheduler(
            midiports,
            FakeSaving(),
            FakeMenu(),
            None,
            None,
            reliable_client_factory=lambda _settings: client,
        )
        mid = mido.MidiFile(ticks_per_beat=480)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.Message("note_on", note=60, velocity=100, time=0))

        with patch("lib.midi_playback_scheduler.mido.MidiFile", return_value=mid):
            self.assertFalse(scheduler.play("song.mid"))

        self.assertEqual(midiports.scheduled, [])
        self.assertEqual(midiports.file_enqueued, [])
        self.assertEqual(scheduler.state, PlaybackState.ERROR)


if __name__ == "__main__":
    unittest.main()
