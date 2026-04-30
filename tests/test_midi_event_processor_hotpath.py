import sys
import types
from collections import deque
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

rpi_ws281x = types.ModuleType("rpi_ws281x")
rpi_ws281x.Color = lambda red, green, blue: (int(red), int(green), int(blue))
rpi_ws281x.PixelStrip = object
rpi_ws281x.ws = types.SimpleNamespace()
sys.modules["rpi_ws281x"] = rpi_ws281x

from lib.midi_event_processor import MIDIEventProcessor


class FakeMessage:
    def __init__(
        self,
        msg_type="note_on",
        channel=0,
        note=60,
        velocity=100,
        control=64,
        value=127,
        text_channel=None,
    ):
        self.type = msg_type
        self.channel = channel
        self.note = note
        self.velocity = velocity
        self.control = control
        self.value = value
        self.text_channel = channel if text_channel is None else text_channel
        self.str_calls = 0

    def __str__(self):
        self.str_calls += 1
        if self.type == "control_change":
            return (
                f"control_change channel={self.text_channel} control={self.control} "
                f"value={self.value} time=0"
            )
        return (
            f"{self.type} channel={self.text_channel} note={self.note} "
            f"velocity={self.velocity} time=0"
        )


class FakeStrip:
    def __init__(self):
        self.pixels = []

    def setPixelColor(self, position, color):
        self.pixels.append((position, color))


class FakeLedStrip:
    def __init__(self, led_number=16, note_position=None):
        self.led_number = led_number
        self.strip = FakeStrip()
        self.keylist = [0] * led_number
        self.keylist_status = [0] * led_number
        self.keylist_sustained = [0] * led_number
        self.keylist_color = [[0, 0, 0] for _ in range(led_number)]
        self.keylist_external_software = [0] * led_number
        self.active_pulses = []
        self.sustain_value = 0
        self.adjacent_calls = []
        self.note_position = note_position
        self.note_position_calls = []
        self.shift = 0
        self.leds_per_meter = 72
        self.reverse = False
        if note_position is not None:
            self.get_note_position = self._get_note_position

    def set_adjacent_colors(self, position, color, is_backlight):
        self.adjacent_calls.append((position, color, is_backlight))

    def _get_note_position(self, note, ledsettings):
        self.note_position_calls.append((note, ledsettings))
        return self.note_position


class FakeLedSettings:
    def __init__(self):
        self.mode = "Normal"
        self.color_mode = "Fixed"
        self.skipped_notes = "Normal"
        self.backlight_brightness = 0
        self.backlight_brightness_percent = 100
        self.backlight_red = 0
        self.backlight_green = 0
        self.backlight_blue = 0
        self.sequence_active = False
        self.next_step = None
        self.control_number = 64
        self.note_offsets = []
        self.sequence_calls = []

    def set_sequence(self, start, step):
        self.sequence_calls.append((start, step))


class FakeUserSettings:
    def get_setting_value(self, name):
        if name == "midi_logging":
            return "0"
        raise KeyError(name)


class FakeSaving:
    def __init__(self):
        self.is_playing_midi = False
        self.is_recording = False
        self.tracks = []
        self.control_changes = []
        self.restart_count = 0

    def restart_time(self):
        self.restart_count += 1

    def add_track(self, *args):
        self.tracks.append(args)

    def add_control_change(self, *args):
        self.control_changes.append(args)


class FakeLearning:
    def __init__(self):
        self.is_started_midi = False
        self.socket_send = []
        self.hand_colorR = "right"
        self.hand_colorL = "left"
        self.hand_colorList = {
            "right": (10, 20, 30),
            "left": (30, 20, 10),
        }


class FakeMenu:
    screensaver_is_running = False


class FakeColorMode:
    def __init__(self):
        self.midi_events = []

    def NoteOn(self, msg, msg_timestamp, unused, note_position):
        return 1, 2, 3

    def MidiEvent(self, msg, unused, ledstrip):
        self.midi_events.append(msg)


class FakeDiagnostics:
    def __init__(self):
        self.metadata = {}
        self.gauges = {}
        self.counters = {}

    def set_metadata(self, name, value):
        self.metadata[name] = value

    def set_gauge(self, name, value):
        self.gauges[name] = value

    def increment_counter(self, name, value):
        self.counters[name] = self.counters.get(name, 0) + value


class FakeMidiPorts:
    def __init__(self, messages):
        self.midi_queue = deque(messages)
        self.websocket_midi_queue = deque()
        self.midifile_queue = deque()
        self.midipending = None
        self.queues = None
        self.last_activity = 0
        self.diagnostics = FakeDiagnostics()
        self.refresh_count = 0

    def _ensure_runtime_diagnostics(self):
        return self.diagnostics

    def refresh_queue_diagnostics(self):
        self.refresh_count += 1


def make_processor(*, ledstrip=None, ledsettings=None, saving=None, state_manager=None, messages=()):
    return MIDIEventProcessor(
        FakeMidiPorts(messages),
        ledstrip or FakeLedStrip(),
        ledsettings or FakeLedSettings(),
        FakeUserSettings(),
        saving or FakeSaving(),
        FakeLearning(),
        FakeMenu(),
        FakeColorMode(),
        state_manager=state_manager,
    )


def test_note_on_external_channel_uses_message_attribute_not_string():
    ledstrip = FakeLedStrip()
    processor = make_processor(ledstrip=ledstrip)
    msg = FakeMessage(channel=12, text_channel=0)

    processor.handle_note_on(msg, 12.5, 4)

    assert ledstrip.keylist_external_software[4] == 1
    assert ledstrip.strip.pixels[-1] == (4, (10, 20, 30))
    assert msg.str_calls == 0


def test_note_off_external_channel_uses_message_attribute_not_string():
    ledstrip = FakeLedStrip()
    ledstrip.keylist[5] = 1000
    ledstrip.keylist_external_software[5] = 1
    processor = make_processor(ledstrip=ledstrip)
    msg = FakeMessage(msg_type="note_off", channel=11, velocity=0, text_channel=0)

    processor.handle_note_off(msg, 3.0, 5)

    assert ledstrip.keylist_external_software[5] == 0
    assert msg.str_calls == 0


def test_process_midi_events_prefers_ledstrip_note_position_method():
    ledstrip = FakeLedStrip(note_position=7)
    msg = FakeMessage(note=64, velocity=90)
    processor = make_processor(ledstrip=ledstrip, messages=[(msg, 1.25)])

    with patch("lib.midi_event_processor.get_note_position", return_value=2):
        processor.process_midi_events()

    assert ledstrip.note_position_calls == [(64, processor.ledsettings)]
    assert ledstrip.keylist_status[7] == 1
    assert ledstrip.keylist_status[2] == 0


def test_process_midi_events_falls_back_to_function_note_position():
    ledstrip = FakeLedStrip()
    msg = FakeMessage(note=65, velocity=90)
    processor = make_processor(ledstrip=ledstrip, messages=[(msg, 2.5)])

    with patch("lib.midi_event_processor.get_note_position", return_value=6):
        processor.process_midi_events()

    assert ledstrip.keylist_status[6] == 1


def test_sustain_control_updates_led_runtime_value():
    ledstrip = FakeLedStrip()
    processor = make_processor(ledstrip=ledstrip)
    msg = FakeMessage(msg_type="control_change", control=64, value=96)

    processor.handle_control_change(msg, 10.0)

    assert processor.last_sustain == 96
    assert ledstrip.sustain_value == 96


def test_control_change_recording_is_preserved():
    saving = FakeSaving()
    saving.is_recording = True
    processor = make_processor(saving=saving)
    msg = FakeMessage(msg_type="control_change", control=64, value=0)

    processor.handle_control_change(msg, 4.0)

    assert saving.control_changes == [("control_change", 0, 64, 0, 4.0)]


def test_control_change_sequence_behavior_is_preserved():
    ledsettings = FakeLedSettings()
    ledsettings.sequence_active = True
    ledsettings.next_step = 63
    ledsettings.control_number = 64
    processor = make_processor(ledsettings=ledsettings)
    msg = FakeMessage(msg_type="control_change", control=64, value=127)

    with patch("lib.midi_event_processor.time.time", return_value=101.0):
        processor.handle_control_change(msg, 0.0)

    assert ledsettings.sequence_calls == [(0, 1)]
    assert processor.last_sequence_advance == 101.0


def test_midi_activity_update_receives_current_time_when_supported():
    class TimestampStateManager:
        def __init__(self):
            self.calls = []

        def update_midi_activity(self, current_time=None):
            self.calls.append(current_time)

        def is_active_use(self):
            return False

    state_manager = TimestampStateManager()
    ledstrip = FakeLedStrip(note_position=3)
    msg = FakeMessage(note=67, velocity=80)
    processor = make_processor(
        ledstrip=ledstrip,
        state_manager=state_manager,
        messages=[(msg, 6.5)],
    )

    with patch("lib.midi_event_processor.time.time", return_value=123.25):
        processor.process_midi_events()

    assert processor.midiports.last_activity == 123.25
    assert state_manager.calls == [123.25]


def test_midi_activity_update_falls_back_for_legacy_state_manager():
    class LegacyStateManager:
        def __init__(self):
            self.calls = 0

        def update_midi_activity(self):
            self.calls += 1

        def is_active_use(self):
            return False

    state_manager = LegacyStateManager()
    ledstrip = FakeLedStrip(note_position=3)
    msg = FakeMessage(note=67, velocity=80)
    processor = make_processor(
        ledstrip=ledstrip,
        state_manager=state_manager,
        messages=[(msg, 6.5)],
    )

    processor.process_midi_events()

    assert state_manager.calls == 1
