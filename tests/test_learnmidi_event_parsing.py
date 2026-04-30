#!/usr/bin/env python3

import inspect
import sys

import pytest

sys.path.append("./")
sys.path.append("../")

from lib import learnmidi


class StringHostileMidiMessage:
    def __init__(self, msg_type, note, velocity):
        self.type = msg_type
        self.note = note
        self.velocity = velocity

    def __str__(self):
        raise AssertionError("MIDI note parsing must not call str(msg)")


@pytest.mark.parametrize(
    ("msg_type", "velocity", "expected_velocity"),
    [
        ("note_on", 96, 96),
        ("note_on", 0, 0),
        ("note_off", 96, 0),
    ],
)
def test_extract_midi_note_velocity_reads_mido_attributes_without_string_parsing(
    msg_type,
    velocity,
    expected_velocity,
):
    msg = StringHostileMidiMessage(msg_type, note=64, velocity=velocity)

    assert learnmidi._extract_midi_note_velocity(msg) == (64, expected_velocity)


def test_learn_midi_note_drain_uses_attribute_helper_instead_of_string_parsing():
    source = inspect.getsource(learnmidi.LearnMIDI.learn_midi)

    assert "find_between(str(msg_in)" not in source
    assert "_extract_midi_note_velocity(msg_in)" in source
