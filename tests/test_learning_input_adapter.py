#!/usr/bin/env python3

import sys
import unittest

sys.path.append("./")
sys.path.append("../")

from lib.learning_input_adapter import LearningInputAdapter
from lib.midi_queues import MidiQueues


class FakeMidiMessage:
    def __init__(self, msg_type="note_on", note=60, velocity=100):
        self.type = msg_type
        self.note = note
        self.velocity = velocity


class TestLearningInputAdapter(unittest.TestCase):
    def test_drain_note_events_uses_learning_queue_without_stealing_visualizer_events(self):
        queues = MidiQueues(live_maxlen=8)
        adapter = LearningInputAdapter(queues)
        note = FakeMidiMessage(note=65)
        control = FakeMidiMessage("control_change")

        queues.enqueue_live(note, timestamp=1.0)
        queues.enqueue_live(control, timestamp=2.0)

        self.assertEqual(adapter.drain_note_events(), [(note, 1.0)])
        self.assertEqual(queues.drain_live_for_visualizer(), [(note, 1.0), (control, 2.0)])


if __name__ == "__main__":
    unittest.main()
