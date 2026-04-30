#!/usr/bin/env python3

import sys
from types import SimpleNamespace

import pytest

sys.path.append("./")
sys.path.append("../")

import lib.component_initializer as component_initializer
from lib.component_initializer import ComponentInitializer


class FakeThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.daemon = daemon

    def start(self):
        pass


class FakePlatform:
    def disable_system_midi_scripts(self):
        pass

    def install_midi2abc(self):
        pass


class FakeMidiPorts:
    def __init__(self):
        self.instances = []
        self.last_activity = None
        self.monitor_started = False

    def add_instance(self, instance):
        self.instances.append(instance)

    def start_midi_monitor(self):
        self.monitor_started = True


class FakeLedSettings:
    def __init__(self, color_mode):
        self.color_mode = color_mode
        self.rainbow_colormap = "RawRainbow"
        self.rainbow_colormap_safe = "SafeRainbow"
        self.velocityrainbow_colormap = "RawVelocity"
        self.velocityrainbow_colormap_safe = "SafeVelocity"
        self.multicolor_range = [(20, 30), (31, 40)]
        self.multicolor = [(255, 0, 0), (0, 255, 0)]
        self.instances = []

    def add_instance(self, menu, ledstrip):
        self.instances.append((menu, ledstrip))


class FakeAddInstanceComponent:
    def __init__(self):
        self.instances = []

    def add_instance(self, instance):
        self.instances.append(instance)


class FakeMenu:
    def __init__(self):
        self.shown = False

    def show(self):
        self.shown = True


class FakeHotspot:
    def __init__(self):
        self.hotspot_script_time = None


def make_initializer(color_mode):
    initializer = ComponentInitializer.__new__(ComponentInitializer)
    initializer.args = SimpleNamespace(skipupdate=True)
    initializer.platform = FakePlatform()
    initializer.ledsettings = FakeLedSettings(color_mode)
    initializer.ledstrip = SimpleNamespace(led_gamma=2.4, strip=object())
    initializer.midiports = FakeMidiPorts()
    initializer.menu = FakeMenu()
    initializer.saving = FakeAddInstanceComponent()
    initializer.learning = FakeAddInstanceComponent()
    initializer.hotspot = FakeHotspot()
    return initializer


def patch_setup_side_effects(monkeypatch):
    monkeypatch.setattr(component_initializer.threading, "Thread", FakeThread)
    monkeypatch.setattr(component_initializer, "fastColorWipe", lambda *args, **kwargs: None)


def patch_colormap_calls(monkeypatch):
    calls = SimpleNamespace(
        generated=[],
        previews=0,
        multicolor=[],
        current_gamma=[],
    )
    gradients = {
        "RawRainbow": [(255, 0, 0), (0, 255, 0)],
        "SafeRainbow": [(0, 0, 255), (255, 0, 0)],
        "RawVelocity": [(255, 255, 0), (0, 255, 255)],
        "SafeVelocity": [(255, 0, 255), (255, 255, 255)],
    }

    monkeypatch.setattr(component_initializer.cmap, "gradients", gradients)
    monkeypatch.setattr(component_initializer.cmap, "load_colormaps", lambda: {})
    monkeypatch.setattr(
        component_initializer.cmap,
        "ensure_colormap_previews",
        lambda: setattr(calls, "previews", calls.previews + 1),
    )
    monkeypatch.setattr(
        component_initializer.cmap,
        "generate_colormaps",
        lambda gradients_arg, gamma, names=None: calls.generated.append((gradients_arg, gamma, names)),
    )
    monkeypatch.setattr(
        component_initializer.cmap,
        "update_multicolor",
        lambda multicolor_range, multicolor: calls.multicolor.append((multicolor_range, multicolor)),
    )
    monkeypatch.setattr(
        component_initializer.cmap,
        "set_current_gamma",
        lambda gamma: calls.current_gamma.append(gamma),
        raising=False,
    )

    return calls, gradients


def test_setup_components_skips_runtime_colormap_generation_for_single_mode(monkeypatch):
    patch_setup_side_effects(monkeypatch)
    calls, _gradients = patch_colormap_calls(monkeypatch)
    initializer = make_initializer("Single")

    initializer.setup_components()

    assert calls.generated == []
    assert calls.current_gamma == [initializer.ledstrip.led_gamma]
    assert calls.previews == 1
    assert calls.multicolor == [
        (initializer.ledsettings.multicolor_range, initializer.ledsettings.multicolor)
    ]


@pytest.mark.parametrize(
    ("color_mode", "expected_colormap"),
    [
        ("Rainbow", "SafeRainbow"),
        ("VelocityRainbow", "SafeVelocity"),
    ],
)
def test_setup_components_generates_selected_safe_colormap_for_rainbow_modes(
    monkeypatch, color_mode, expected_colormap
):
    patch_setup_side_effects(monkeypatch)
    calls, gradients = patch_colormap_calls(monkeypatch)
    initializer = make_initializer(color_mode)

    initializer.setup_components()

    assert calls.generated == [(gradients, initializer.ledstrip.led_gamma, [expected_colormap])]
    assert calls.current_gamma == [initializer.ledstrip.led_gamma]
