import sys
import types
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


if "rpi_ws281x" not in sys.modules:
    sys.modules["rpi_ws281x"] = types.SimpleNamespace(Color=lambda red, green, blue: (red, green, blue))

import lib.led_effects_processor as effects_module
from lib.led_effects_processor import LEDEffectsProcessor


class RecordingStrip:
    def __init__(self):
        self.calls = []

    def setPixelColor(self, led, color):
        self.calls.append((led, color))


class FakeLedStrip:
    def __init__(self, keylist, keylist_color=None):
        self.led_number = len(keylist)
        self.keylist = list(keylist)
        self.keylist_status = [0] * len(keylist)
        self.keylist_sustained = [0] * len(keylist)
        self.keylist_color = keylist_color or [[10, 20, 30] for _ in keylist]
        self.active_pulses = []
        self.strip = RecordingStrip()
        self.adjacent_calls = []

    def set_adjacent_colors(self, led, color, led_turn_off, fading=1):
        self.adjacent_calls.append((led, color, led_turn_off, fading))


class FakeColorMode:
    def ColorUpdate(self, msg, led, color):
        return None


class FakeMenu:
    screensaver_is_running = False


class FakeSettings:
    def __init__(self, mode="Velocity"):
        self.mode = mode
        self.fadingspeed = 1000
        self.velocity_speed = 1000
        self.pedal_speed = 1000
        self.backlight_brightness_percent = 50
        self.pulse_animation_distance = 4
        self.pulse_animation_speed = 1000
        self.pulse_flicker_strength = 0
        self.pulse_flicker_speed = 1
        self.backlight_calls = []

    def get_backlight_color(self, channel):
        self.backlight_calls.append(channel)
        return {"Red": 20, "Green": 40, "Blue": 60}[channel]


class RemoveForbiddenList(list):
    def remove(self, item):
        raise AssertionError("pulse cleanup should rebuild survivors instead of removing repeatedly")


def _processor(ledstrip, ledsettings, last_sustain=0):
    return LEDEffectsProcessor(
        ledstrip,
        ledsettings,
        FakeMenu(),
        FakeColorMode(),
        last_sustain=last_sustain,
        pedal_deadzone=10,
    )


def test_process_fade_effects_reuses_color_object_for_single_led_update(monkeypatch):
    colors = []

    def color(red, green, blue):
        value = object()
        colors.append((red, green, blue, value))
        return value

    monkeypatch.setattr(effects_module, "Color", color)
    ledstrip = FakeLedStrip([100])
    ledstrip.keylist_status[0] = 1
    processor = _processor(ledstrip, FakeSettings(mode="Velocity"))

    assert processor.process_fade_effects(0) is True

    assert len(colors) == 1
    assert ledstrip.strip.calls[0][1] is colors[0][3]
    assert ledstrip.adjacent_calls[0][1] is colors[0][3]


def test_process_fade_effects_reads_backlight_once_per_pass():
    ledstrip = FakeLedStrip([1, 1])
    settings = FakeSettings(mode="Fading")
    processor = _processor(ledstrip, settings)

    assert processor.process_fade_effects(1.0) is True

    assert settings.backlight_calls == ["Red", "Green", "Blue"]


def test_process_fade_effects_uses_dynamic_ledstrip_sustain_value():
    ledstrip = FakeLedStrip([100])
    ledstrip.sustain_value = 127
    processor = _processor(ledstrip, FakeSettings(mode="Velocity"), last_sustain=0)

    assert processor.process_fade_effects(0) is True

    assert ledstrip.keylist[0] == 1000


def test_process_fade_effects_preserves_constructor_sustain_fallback():
    ledstrip = FakeLedStrip([100])
    processor = _processor(ledstrip, FakeSettings(mode="Velocity"), last_sustain=127)

    assert processor.process_fade_effects(0) is True

    assert ledstrip.keylist[0] == 1000


def test_process_pulse_effects_rebuilds_surviving_pulses_instead_of_removing(monkeypatch):
    monkeypatch.setattr(effects_module.time, "perf_counter", lambda: 100.0)
    expired = {
        "state": "release",
        "start_time": 98.0,
        "release_time": 98.0,
        "velocity": 1.0,
        "position": 2,
        "color": (100, 0, 0),
    }
    survivor = {
        "state": "release",
        "start_time": 99.5,
        "release_time": 99.5,
        "velocity": 1.0,
        "position": 5,
        "color": (0, 100, 0),
    }
    ledstrip = FakeLedStrip([0] * 10)
    ledstrip.active_pulses = RemoveForbiddenList([expired, survivor])
    processor = _processor(ledstrip, FakeSettings(mode="Pulse"))

    assert processor.process_pulse_effects() is True

    assert ledstrip.active_pulses == [survivor]
