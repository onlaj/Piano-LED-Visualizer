#!/usr/bin/env python3

import sys
import unittest

sys.path.append("./")
sys.path.append("../")

from lib.midi_queues import MidiQueues


class FakeMidiMessage:
    def __init__(self, msg_type="note_on", note=60, velocity=100):
        self.type = msg_type
        self.note = note
        self.velocity = velocity


class TestMidiQueues(unittest.TestCase):
    def test_live_input_fans_out_to_visualizer_and_learning_consumers(self):
        queues = MidiQueues(live_maxlen=8)
        msg = FakeMidiMessage(note=64)

        queued = queues.enqueue_live(msg, timestamp=10.0)

        self.assertTrue(queued)
        self.assertEqual(queues.drain_live_for_visualizer(), [(msg, 10.0)])
        self.assertEqual(queues.drain_live_for_learning(), [(msg, 10.0)])
        self.assertEqual(queues.drain_live_for_visualizer(), [])
        self.assertEqual(queues.drain_live_for_learning(), [])

    def test_live_drop_policy_reserves_space_for_note_off_per_consumer(self):
        queues = MidiQueues(live_maxlen=4, reserved_noteoff_slots=1)

        self.assertTrue(queues.enqueue_live(FakeMidiMessage(note=60), timestamp=1.0))
        self.assertTrue(queues.enqueue_live(FakeMidiMessage(note=61), timestamp=2.0))
        self.assertTrue(queues.enqueue_live(FakeMidiMessage(note=62), timestamp=3.0))
        self.assertFalse(queues.enqueue_live(FakeMidiMessage(note=63), timestamp=4.0))
        self.assertTrue(queues.enqueue_live(FakeMidiMessage("note_off", note=60, velocity=0), timestamp=5.0))

        visualizer_notes = [msg.note for msg, _ in queues.drain_live_for_visualizer()]
        learning_notes = [msg.note for msg, _ in queues.drain_live_for_learning()]

        self.assertEqual(visualizer_notes, [60, 61, 62, 60])
        self.assertEqual(learning_notes, [60, 61, 62, 60])
        self.assertEqual(queues.drop_counts["live_note_on"], 1)

    def test_clear_file_queue_does_not_clear_live_or_learning_queues(self):
        queues = MidiQueues(live_maxlen=8)
        live_msg = FakeMidiMessage(note=60)
        file_msg = FakeMidiMessage(note=72)

        queues.enqueue_live(live_msg, timestamp=1.0)
        queues.enqueue_file(file_msg, timestamp=2.0)
        queues.clear_file()

        self.assertEqual(queues.drain_file(), [])
        self.assertEqual(queues.drain_live_for_visualizer(), [(live_msg, 1.0)])
        self.assertEqual(queues.drain_live_for_learning(), [(live_msg, 1.0)])

    def test_forward_live_queue_uses_locked_helpers(self):
        queues = MidiQueues(forward_maxlen=4)
        msg = FakeMidiMessage(note=60)

        self.assertTrue(queues.enqueue_live_forward(msg, timestamp=12.5, source="websocket"))

        self.assertEqual(queues.snapshot_depths()["live_forward"], 1)
        self.assertEqual(queues.pop_live_forward(), (msg, 12.5, "websocket"))
        self.assertIsNone(queues.pop_live_forward())

    def test_scheduled_forward_peek_pop_and_source_clear(self):
        queues = MidiQueues(scheduled_forward_maxlen=4)
        midifile_msg = FakeMidiMessage(note=60)
        live_msg = FakeMidiMessage(note=61)

        self.assertTrue(
            queues.enqueue_scheduled_forward(
                midifile_msg,
                enqueued_at=1.0,
                due_time=20.0,
                source="midifile",
            )
        )
        self.assertTrue(
            queues.enqueue_scheduled_forward(
                live_msg,
                enqueued_at=1.0,
                due_time=10.0,
                source="live",
            )
        )

        self.assertIsNone(queues.peek_due_scheduled_forward(now_perf=9.0))
        self.assertEqual(
            queues.peek_due_scheduled_forward(now_perf=10.0),
            (live_msg, 1.0, 10.0, "live"),
        )

        self.assertEqual(queues.clear_scheduled_forward(source="midifile"), 1)
        self.assertEqual(queues.snapshot_depths()["scheduled_forward"], 1)
        self.assertEqual(
            queues.pop_due_scheduled_forward(now_perf=10.0),
            (live_msg, 1.0, 10.0, "live"),
        )


if __name__ == "__main__":
    unittest.main()
