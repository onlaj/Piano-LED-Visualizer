from types import SimpleNamespace
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.functions import get_note_position as legacy_get_note_position
from lib.ledstrip import LedStrip


def _expected_note_position(note, strip, ledsettings):
    note_offset = 0
    for threshold, offset in ledsettings.note_offsets:
        if note > threshold:
            note_offset += offset

    note_offset -= strip.shift
    density = strip.leds_per_meter / 72
    note_pos_raw = int(density * (note - 20) - note_offset)

    if strip.reverse:
        return max(0, strip.led_number - note_pos_raw)
    return max(0, note_pos_raw)


def _strip(led_number=176, leds_per_meter=144, shift=0, reverse=0):
    strip = LedStrip.__new__(LedStrip)
    strip.led_number = led_number
    strip.leds_per_meter = leds_per_meter
    strip.shift = shift
    strip.reverse = reverse
    return strip


def _settings(note_offsets):
    return SimpleNamespace(note_offsets=note_offsets)


def test_get_note_position_matches_legacy_mapping_with_offsets_shift_and_reverse():
    ledsettings = _settings([(30, 2), (60, -3), (84, 5)])
    strip = _strip(led_number=128, leds_per_meter=108, shift=4, reverse=1)

    for note in (21, 30, 31, 60, 61, 84, 85, 108):
        assert strip.get_note_position(note, ledsettings) == _expected_note_position(note, strip, ledsettings)


def test_note_position_cache_recomputes_when_mapping_inputs_change():
    ledsettings = _settings([(30, 1)])
    strip = _strip(led_number=100, leds_per_meter=72, shift=0, reverse=0)

    assert strip.get_note_position(60, ledsettings) == _expected_note_position(60, strip, ledsettings)

    strip.shift = 5
    assert strip.get_note_position(60, ledsettings) == _expected_note_position(60, strip, ledsettings)

    strip.reverse = 1
    assert strip.get_note_position(60, ledsettings) == _expected_note_position(60, strip, ledsettings)

    strip.led_number = 140
    assert strip.get_note_position(60, ledsettings) == _expected_note_position(60, strip, ledsettings)

    strip.leds_per_meter = 144
    assert strip.get_note_position(60, ledsettings) == _expected_note_position(60, strip, ledsettings)

    ledsettings.note_offsets.append((50, 7))
    assert strip.get_note_position(60, ledsettings) == _expected_note_position(60, strip, ledsettings)


def test_note_position_cache_reuses_same_cache_for_unchanged_configuration():
    ledsettings = _settings([(40, 2)])
    strip = _strip(led_number=90, leds_per_meter=72, shift=1, reverse=0)

    first = strip.get_note_position(64, ledsettings)
    cache = strip._note_position_cache

    assert strip.get_note_position(64, ledsettings) == first
    assert strip._note_position_cache is cache
    assert strip._note_position_cache[64] == first


def test_legacy_get_note_position_delegates_to_ledstrip_cache_when_available():
    ledsettings = _settings([(40, 2)])
    calls = []

    class CachedStrip:
        def get_note_position(self, note, settings):
            calls.append((note, settings))
            return 42

    strip = CachedStrip()

    assert legacy_get_note_position(64, strip, ledsettings) == 42
    assert calls == [(64, ledsettings)]
