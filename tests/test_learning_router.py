#!/usr/bin/env python3
"""Replays real Synthesia transcripts through the Learning mode router."""

import sys
sys.path.append('./')
sys.path.append('../')
import unittest
from lib.learning_router import TO_COMPUTER, TO_LEDS, TO_PIANO, LearningRouter


class Msg:
    """Stand-in for mido.Message so the tests need no MIDI backend."""

    def __init__(self, type, channel=0, note=0, velocity=0, control=0, value=0, program=0):
        self.type = type
        self.channel = channel
        self.note = note
        self.velocity = velocity
        self.control = control
        self.value = value
        self.program = program

    def __repr__(self):
        return "{} channel={} note={} velocity={}".format(
            self.type, self.channel, self.note, self.velocity
        )


def guide_on(note, channel):
    return Msg("note_on", channel=channel, note=note, velocity=1)


def sound_on(note, velocity, channel=0):
    return Msg("note_on", channel=channel, note=note, velocity=velocity)


def sound_off(note, channel=0):
    return Msg("note_on", channel=channel, note=note, velocity=0)


def light_off(note, channel=0):
    return Msg("note_off", channel=channel, note=note, velocity=0)


class TestLearningRouter(unittest.TestCase):
    def setUp(self):
        self.router = LearningRouter()

    def computer(self, msg, block_control=True):
        return self.router.from_computer(msg, block_control)

    def piano(self, msg):
        return self.router.from_piano(msg)

    # --- transcript 1: opening a song -----------------------------------

    def test_song_open_reset_never_reaches_piano(self):
        """The reset burst Synthesia sends on song open is control traffic."""
        piano_bound = []
        for channel in range(16):
            for msg in (
                Msg("control_change", channel=channel, control=123),
                Msg("control_change", channel=channel, control=120),
                Msg("control_change", channel=channel, control=121),
                Msg("program_change", channel=channel, program=0),
                Msg("control_change", channel=channel, control=7, value=100),
                Msg("control_change", channel=channel, control=39),
                Msg("control_change", channel=channel, control=11, value=127),
                Msg("control_change", channel=channel, control=43, value=127),
            ):
                if self.computer(msg) & TO_PIANO:
                    piano_bound.append(msg)

        self.assertEqual(piano_bound, [])

    def test_all_notes_off_drives_leds_and_clears_guides(self):
        self.computer(guide_on(86, 9))
        self.assertEqual(self.router.guides, {86: 9})

        msg = Msg("control_change", control=123)
        self.assertEqual(self.computer(msg), TO_LEDS)
        self.assertEqual(self.router.guides, {})

    def test_program_change_passes_when_blocking_is_off(self):
        msg = Msg("program_change", program=0)
        self.assertEqual(self.computer(msg, block_control=False), TO_PIANO)
        self.assertEqual(self.computer(msg, block_control=True), 0)

    # --- transcript 2: one guide note, pressed and released --------------

    def test_single_guide_note_press_and_release(self):
        # 16:26:11.614 [computer] note_on channel=9 note=86 velocity=1
        self.assertEqual(self.computer(guide_on(86, 9)), TO_LEDS)

        # 16:27:24.035 [piano] note_on channel=0 note=86 velocity=52
        self.assertEqual(self.piano(sound_on(86, 52)), TO_COMPUTER)

        # 16:27:24.072 / .100 [computer] our own note coming back
        self.assertEqual(self.computer(sound_on(86, 52)), 0)
        self.assertEqual(self.computer(sound_on(86, 49)), 0)

        # 16:27:24.107 [computer] note_off channel=0 note=86 -> guide release
        self.assertEqual(self.computer(light_off(86)), TO_LEDS)
        self.assertEqual(self.router.guides, {})

        # 16:27:24.109 [piano] note_on channel=0 note=86 velocity=0 (release)
        self.assertEqual(self.piano(sound_off(86)), TO_COMPUTER)
        self.assertEqual(self.router.piano_held, set())

        # 16:27:24.127 / .128 [computer] echoes of the release, nothing sounding
        self.assertEqual(self.computer(sound_off(86)), 0)
        self.assertEqual(self.computer(light_off(86)), TO_PIANO)

        # 16:27:24.420 [computer] note_on channel=12 note=88 velocity=1
        self.assertEqual(self.computer(guide_on(88, 12)), TO_LEDS)

    # --- transcript 3: two-note chord -----------------------------------

    def test_chord_guides_stay_lit_until_both_notes_are_pressed(self):
        # 16:33:22.008 / .023 both guides light up
        self.computer(guide_on(55, 1))
        self.computer(guide_on(67, 10))
        self.assertEqual(sorted(self.router.guides), [55, 67])

        # only note 67 is pressed, so Synthesia does not advance
        self.piano(sound_on(67, 48))
        self.assertEqual(self.computer(sound_on(67, 48)), 0)
        self.assertEqual(self.computer(sound_on(67, 64, channel=1)), 0)
        self.piano(sound_off(67))
        self.assertEqual(self.computer(sound_off(67)), 0)

        # 16:34:08.100 [computer] note_off channel=1 note=67
        # only part of the chord was pressed, so both lights stay on
        self.assertEqual(self.computer(light_off(67, channel=1)), 0)
        self.assertEqual(sorted(self.router.guides), [55, 67])
        self.assertEqual(self.router.take_led_offs(), [])

    def test_partial_chord_channel_0_note_off_also_keeps_lights(self):
        """Synthesia may send the partial-chord note_off on channel 0."""
        self.computer(guide_on(53, 11))
        self.computer(guide_on(56, 11))
        self.computer(guide_on(60, 12))

        self.piano(sound_on(60, 44))
        self.assertEqual(self.computer(sound_on(60, 44)), 0)
        self.assertEqual(self.computer(sound_on(60, 64)), 0)
        self.piano(sound_off(60))
        self.assertEqual(self.computer(sound_off(60)), 0)

        self.assertEqual(self.computer(light_off(60)), 0)
        self.assertEqual(sorted(self.router.guides), [53, 56, 60])

    def test_chord_pressed_correctly_clears_both_guides(self):
        self.computer(guide_on(55, 1))
        self.computer(guide_on(67, 10))

        self.piano(sound_on(67, 74))
        self.piano(sound_on(55, 51))
        for msg in (
            sound_on(67, 74),
            sound_on(67, 64, channel=1),
            sound_on(55, 51),
            sound_on(55, 64),
        ):
            self.assertEqual(self.computer(msg), 0)

        # first release is still incomplete; the second completes the chord
        self.assertEqual(self.computer(light_off(55)), 0)
        self.assertEqual(self.computer(light_off(67)), TO_LEDS)
        self.assertEqual(self.router.take_led_offs(), [55])
        self.assertEqual(self.router.guides, {})

        # the next pair of guides is for the same two notes we still hold
        self.assertEqual(self.computer(guide_on(55, 11)), TO_LEDS)
        self.assertEqual(self.computer(guide_on(67, 12)), TO_LEDS)

    def test_chord_notes_pressed_seconds_apart_keep_lights(self):
        """Pressing the remaining chord notes later is still not a completed chord."""
        clock = {"t": 0.0}
        self.router = LearningRouter(clock=lambda: clock["t"])
        self.computer(guide_on(55, 1))
        self.computer(guide_on(67, 10))

        clock["t"] = 1.0
        self.piano(sound_on(67, 48))
        self.piano(sound_off(67))
        self.assertEqual(self.computer(light_off(67, channel=1)), 0)
        clock["t"] = 3.0
        self.piano(sound_on(55, 48))
        self.piano(sound_off(55))
        self.assertEqual(self.computer(light_off(55)), 0)
        self.assertEqual(sorted(self.router.guides), [55, 67])

    # --- transcript 4: right hand only ----------------------------------

    def test_left_hand_note_is_played_by_the_piano(self):
        # 16:36:12.502 [computer] note_on channel=10 note=67 velocity=1
        self.computer(guide_on(67, 10))

        # 16:36:18.119 [piano] we press 67
        self.piano(sound_on(67, 61))

        # 16:36:18.162 / .171 [computer] our own 67 coming back - dropped
        self.assertEqual(self.computer(sound_on(67, 61)), 0)
        self.assertEqual(self.computer(sound_on(67, 64, channel=1)), 0)

        # 16:36:18.191 [computer] guide release for 67
        self.assertEqual(self.computer(light_off(67)), TO_LEDS)

        # 16:36:18.199 [computer] note_on channel=0 note=55 velocity=64
        # the left hand note Synthesia plays for us
        self.assertEqual(self.computer(sound_on(55, 64)), TO_PIANO)
        self.assertEqual(self.router.forwarded, {55})

        # its release must reach the piano too
        self.assertEqual(self.computer(sound_off(55)), TO_PIANO)
        self.assertEqual(self.router.forwarded, set())

    # --- issue #618 -----------------------------------------------------

    def test_repeated_note_keeps_sounding_when_light_off_arrives_late(self):
        """https://github.com/onlaj/Piano-LED-Visualizer/issues/618

        In Watch and Listen the light stream lags the sound stream, so the
        light-off for the first occurrence can arrive after the sound-on for
        the second.  Forwarding it would cut the new note short.
        """
        self.computer(guide_on(86, 9))
        self.assertEqual(self.computer(sound_on(86, 64)), TO_PIANO)
        self.assertEqual(self.computer(sound_off(86)), TO_PIANO)

        # second occurrence starts before the first light-off shows up
        self.computer(guide_on(86, 9))
        self.assertEqual(self.computer(sound_on(86, 64)), TO_PIANO)

        # late light-off: LEDs only, the piano keeps the new note
        self.assertEqual(self.computer(light_off(86)), TO_LEDS)
        self.assertEqual(self.router.forwarded, {86})

    def test_watch_and_listen_note_reaches_the_piano_and_is_released(self):
        self.computer(guide_on(55, 1))
        self.assertEqual(self.computer(sound_on(55, 64)), TO_PIANO)
        self.assertEqual(self.computer(sound_off(55)), TO_PIANO)
        self.assertEqual(self.computer(light_off(55)), TO_LEDS)

    def test_watch_and_listen_subset_guide_off_turns_that_led_off(self):
        """Melody notes end while accompaniment guides stay lit."""
        for note, channel in ((41, 11), (48, 11), (53, 11), (65, 12), (70, 12)):
            self.computer(guide_on(note, channel))
        self.assertEqual(self.computer(sound_on(70, 49)), TO_PIANO)
        self.assertEqual(self.computer(sound_off(70)), TO_PIANO)

        self.assertEqual(self.computer(light_off(70)), TO_LEDS)
        self.assertEqual(sorted(self.router.guides), [41, 48, 53, 65])

        self.assertEqual(self.computer(sound_on(68, 49)), TO_PIANO)
        self.assertEqual(self.computer(guide_on(68, 12)), TO_LEDS)
        self.assertEqual(sorted(self.router.guides), [41, 48, 53, 65, 68])

        # later the held chord ends together, then new guides appear
        for note in (41, 48, 53, 65, 68):
            self.assertEqual(self.computer(light_off(note)), TO_LEDS)
        self.assertEqual(self.router.guides, {})

    # --- compatibility with software that has no key lights -------------

    def test_note_off_reaches_piano_when_no_guide_is_lit(self):
        self.assertEqual(self.computer(sound_on(60, 100)), TO_PIANO)
        self.assertEqual(self.computer(light_off(60)), TO_PIANO)
        self.assertEqual(self.router.forwarded, set())

    def test_non_note_messages_pass_through(self):
        msg = Msg("pitchwheel")
        self.assertEqual(self.computer(msg), TO_PIANO)

    # --- stuck note cleanup ---------------------------------------------

    def test_release_forwarded_returns_only_notes_we_started(self):
        self.computer(sound_on(60, 90))
        self.computer(sound_on(64, 90))
        self.piano(sound_on(72, 90))

        self.assertEqual(self.router.release_forwarded(), [60, 64])
        self.assertEqual(self.router.release_forwarded(), [])
        self.assertEqual(self.router.piano_held, {72})

    def test_reset_clears_all_state(self):
        self.computer(guide_on(86, 9))
        self.computer(sound_on(60, 90))
        self.piano(sound_on(72, 90))

        self.router.reset()
        self.assertEqual(self.router.guides, {})
        self.assertEqual(self.router.released, {})
        self.assertEqual(self.router.forwarded, set())
        self.assertEqual(self.router.piano_held, set())
        self.assertEqual(self.router.pressed_guides, set())


if __name__ == "__main__":
    unittest.main()
