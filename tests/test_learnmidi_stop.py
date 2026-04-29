#!/usr/bin/env python3

import sys
import threading
import unittest

import mido

sys.path.append("./")
sys.path.append("../")

from lib.learnmidi import LearnMIDI
from lib.midi_queues import MidiQueues


class FakeMidiPorts:
    def __init__(self):
        self.queues = MidiQueues(scheduled_forward_maxlen=8)
        self.panic_count = 0

    def clear_scheduled_rtp_messages(self, source=None):
        return self.queues.clear_scheduled_forward(source=source)

    def send_all_notes_off(self):
        self.panic_count += 1


class TestLearnMidiStop(unittest.TestCase):
    def test_stop_learning_clears_learning_scheduled_messages_pending_notes_and_sends_panic(self):
        midiports = FakeMidiPorts()
        learning_msg = mido.Message("note_on", note=60, velocity=100)
        live_msg = mido.Message("note_on", note=61, velocity=100)
        midiports.queues.enqueue_scheduled_forward(
            learning_msg,
            enqueued_at=1.0,
            due_time=10.0,
            source="learning",
        )
        midiports.queues.enqueue_scheduled_forward(
            live_msg,
            enqueued_at=1.0,
            due_time=20.0,
            source="live",
        )
        learning = LearnMIDI.__new__(LearnMIDI)
        learning._state_lock = threading.RLock()
        learning.learning_state = "running"
        learning.is_started_midi = True
        learning.pending_software_notes = [learning_msg]
        learning.midiports = midiports

        learning.stop_learning()

        self.assertEqual(learning.learning_state, "stopping")
        self.assertFalse(learning.is_started_midi)
        self.assertEqual(learning.pending_software_notes, [])
        self.assertEqual(midiports.panic_count, 1)
        self.assertEqual(midiports.queues.snapshot_depths()["scheduled_forward"], 1)
        self.assertEqual(
            midiports.queues.pop_due_scheduled_forward(now_perf=20.0),
            (live_msg, 1.0, 20.0, "live"),
        )


if __name__ == "__main__":
    unittest.main()
