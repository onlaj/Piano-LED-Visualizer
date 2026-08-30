"""Routing decisions for Learning mode.

Synthesia (and similar teaching apps) multiplex two independent streams on a
single MIDI port:

  light stream   note_on velocity 1 turns a guide on, note_off turns it off.
                 The channel selects the hand / finger.
  sound stream   note_on velocity > 1 starts a note, note_on velocity 0 ends
                 it.  This stream never uses note_off.

Because the two streams are scheduled separately, a light-off can arrive after
the sound-on of the next occurrence of the same note.  Forwarding light traffic
to the piano therefore cuts notes short (issue #618), so the streams have to be
kept apart: lights drive the LEDs, sound drives the piano.

A note_off for a lit guide is still light-stream traffic.  In Watch and Listen
that means the LED goes off immediately, even if other guides stay lit.  When
the player pressed only some notes of a waiting chord, Synthesia also sends
note_off for those notes; those LEDs stay on until the whole chord advances.

This module holds no MIDI ports and no settings.  Messages are duck-typed, so
anything exposing type/channel/note/velocity works.
"""

import time

TO_LEDS = 1
TO_PIANO = 2
TO_COMPUTER = 4

# Synthesia's finger-based key light channels.  1-5 and 11 are left hand,
# 6-10 and 12 are right hand.
GUIDE_CHANNELS = frozenset(range(1, 13))
RIGHT_HAND_CHANNELS = frozenset((6, 7, 8, 9, 10, 12))

# "all sound off" and "all notes off"
ALL_NOTES_OFF = frozenset((120, 123))

GUIDE_VELOCITY = 1

# Synthesia releases a completed chord with note_offs a few milliseconds apart.
# A partial press is a single note_off, or seconds later if remaining notes are
# pressed one by one.  Only treat the chord as done inside this window.
GUIDE_OFF_WINDOW = 0.1


class LearningRouter:
    """Decides where each message goes while Learning mode is active."""

    def __init__(self, clock=None):
        self._clock = clock
        self.guides = {}  # note -> channel of the lit guide
        self.released = {}  # note -> time of a recent guide note_off
        self.piano_held = set()  # notes currently held down on our piano
        self.pressed_guides = set()  # guides the player hit while they were lit
        self.forwarded = set()  # notes we started on the piano
        self._led_offs = []  # extra notes to turn off when a whole chord advances

    def _now(self):
        if self._clock is not None:
            return self._clock()
        return time.perf_counter()

    def reset(self):
        self.guides.clear()
        self.released.clear()
        self.piano_held.clear()
        self.pressed_guides.clear()
        self.forwarded.clear()
        self._led_offs = []

    def release_forwarded(self):
        """Take the notes we started on the piano so they can be silenced."""
        notes = sorted(self.forwarded)
        self.forwarded.clear()
        return notes

    def take_led_offs(self):
        """Notes besides the current message that should now lose their guide LED."""
        notes = self._led_offs
        self._led_offs = []
        return notes

    def from_piano(self, msg):
        """Track what the player is holding.  Piano traffic always goes out."""
        msg_type = getattr(msg, "type", None)
        if msg_type == "note_on":
            if getattr(msg, "velocity", 0) > 0:
                self.piano_held.add(msg.note)
                if msg.note in self.guides:
                    self.pressed_guides.add(msg.note)
            else:
                self.piano_held.discard(msg.note)
        elif msg_type == "note_off":
            self.piano_held.discard(msg.note)
        return TO_COMPUTER

    def from_computer(self, msg, block_control=True):
        msg_type = getattr(msg, "type", None)

        if msg_type == "note_on":
            velocity = getattr(msg, "velocity", 0)
            if velocity == GUIDE_VELOCITY:
                self.guides[msg.note] = getattr(msg, "channel", 0)
                self.released.pop(msg.note, None)
                self.pressed_guides.discard(msg.note)
                return TO_LEDS
            if velocity == 0:
                if msg.note in self.forwarded:
                    self.forwarded.discard(msg.note)
                    return TO_PIANO
                return 0
            if msg.note in self.piano_held:
                # our own key coming back from the computer
                return 0
            self.forwarded.add(msg.note)
            return TO_PIANO

        if msg_type == "note_off":
            if msg.note in self.guides:
                now = self._now()
                cutoff = now - GUIDE_OFF_WINDOW
                self.released = {n: t for n, t in self.released.items() if t >= cutoff}
                self.released[msg.note] = now
                all_released = self.released.keys() >= self.guides.keys()
                # The player pressed this guide but not the rest of the chord,
                # so Synthesia is not advancing.  Keep every LED on.
                # Watch and Listen has no player press, so a subset note_off
                # must turn that LED off while the others stay.
                if not all_released and msg.note in self.pressed_guides:
                    return 0
                if all_released:
                    self._led_offs = sorted(n for n in self.guides if n != msg.note)
                    self.guides.clear()
                    self.released.clear()
                    self.pressed_guides.clear()
                else:
                    self.guides.pop(msg.note, None)
                    self.released.pop(msg.note, None)
                    self.pressed_guides.discard(msg.note)
                return TO_LEDS
            self.forwarded.discard(msg.note)
            # no guide was lit, so this is a peer that releases with note_off
            return TO_PIANO

        if msg_type == "control_change":
            if getattr(msg, "control", None) in ALL_NOTES_OFF:
                self.guides.clear()
                self.released.clear()
                self.pressed_guides.clear()
                self._led_offs = []
                return TO_LEDS
            return 0 if block_control else TO_PIANO

        if msg_type == "program_change":
            return 0 if block_control else TO_PIANO

        return TO_PIANO


def is_right_hand(channel):
    return channel in RIGHT_HAND_CHANNELS


def is_guide_channel(channel):
    return channel in GUIDE_CHANNELS
