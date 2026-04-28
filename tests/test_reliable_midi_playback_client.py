#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path

import mido

sys.path.append("./")
sys.path.append("../")

from lib.reliable_midi_playback_client import compile_midi_file, compile_midi_messages


class TestReliableMidiPlaybackClient(unittest.TestCase):
    def test_compile_preserves_exact_duplicate_simultaneous_events(self):
        mid = mido.MidiFile(ticks_per_beat=480)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.Message("note_on", note=60, velocity=100, time=0))
        track.append(mido.Message("note_on", note=60, velocity=100, time=0))
        track.append(mido.Message("control_change", control=64, value=127, time=240))
        track.append(mido.Message("note_off", note=60, velocity=0, time=0))

        compiled = compile_midi_messages(mid)

        self.assertEqual(compiled.total, 4)
        self.assertEqual([event["seq"] for event in compiled.events], [0, 1, 2, 3])
        self.assertEqual([event["data"] for event in compiled.events[:2]], [[0x90, 60, 100], [0x90, 60, 100]])
        self.assertEqual(compiled.events[0]["dueUs"], compiled.events[1]["dueUs"])
        self.assertEqual(compiled.events[2]["data"], [0xB0, 64, 127])
        self.assertEqual(compiled.events[3]["data"], [0x80, 60, 0])

    def test_compile_la_campanella_counts_all_non_meta_messages(self):
        compiled = compile_midi_file(Path("Songs") / "La Campanella.mid")
        note_on_count = sum(
            1
            for event in compiled.events
            if len(event["data"]) >= 3 and event["data"][0] & 0xF0 == 0x90 and event["data"][2] > 0
        )

        self.assertEqual(compiled.total, 8556)
        self.assertEqual(note_on_count, 4266)
        self.assertEqual(compiled.events[-1]["seq"], 8555)


if __name__ == "__main__":
    unittest.main()
