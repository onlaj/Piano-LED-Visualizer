#!/usr/bin/env python3
"""Tests de régression pour les bugs trouvés lors de l'audit de novembre 2026."""

import datetime
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import mido

sys.path.append("./")
sys.path.append("../")

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestProfileManagerLearningSettings(unittest.TestCase):
    def test_get_learning_settings_returns_saved_values(self):
        from lib.profile_manager import ProfileManager

        with tempfile.TemporaryDirectory() as tmp:
            songs = os.path.join(tmp, "Songs")
            os.makedirs(songs)
            Path(songs, "song.mid").write_bytes(b"x")
            manager = ProfileManager(os.path.join(tmp, "p.db"), songs_dir=songs)
            profile_id = manager.get_or_create_profile("robin")
            manager.update_learning_setting(profile_id, "song.mid", "tempo", 80)

            settings = manager.get_learning_settings(profile_id, "song.mid")

            self.assertEqual(settings["tempo"], 80)


class TestSaveMidiWithoutRecording(unittest.TestCase):
    def test_save_without_recording_does_not_raise(self):
        from lib.savemidi import SaveMIDI

        saver = SaveMIDI()
        saver.add_instance(SimpleNamespace(render_message=lambda *a, **k: None))
        saver.save("never-recorded")  # ne doit pas lever AttributeError


class TestScheduleAcrossMidnight(unittest.TestCase):
    SCHEDULE = [{"enabled": True, "days": [0], "startTime": "22:00", "endTime": "02:00"}]  # lundi 22:00 -> mardi 02:00

    def _at(self, year, month, day, hour, minute):
        import lib.functions as functions

        class FakeDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(year, month, day, hour, minute)

        fake_module = SimpleNamespace(datetime=FakeDateTime, time=datetime.time)
        with patch.object(functions, "datetime", fake_module):
            return functions.is_within_schedule(self.SCHEDULE)

    def test_evening_part_belongs_to_start_day(self):
        self.assertTrue(self._at(2026, 10, 26, 23, 0))  # lundi 23:00

    def test_after_midnight_part_belongs_to_previous_day(self):
        self.assertTrue(self._at(2026, 10, 27, 1, 0))  # mardi 01:00

    def test_early_morning_of_start_day_is_outside(self):
        self.assertFalse(self._at(2026, 10, 26, 1, 0))  # lundi 01:00 (plage du dimanche soir)

    def test_after_end_time_is_outside(self):
        self.assertFalse(self._at(2026, 10, 27, 3, 0))

    def test_same_day_range_unchanged(self):
        import lib.functions as functions

        schedule = [{"enabled": True, "days": [0], "startTime": "08:00", "endTime": "18:00"}]

        class FakeDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 26, 12, 0)

        with patch.object(functions, "datetime", SimpleNamespace(datetime=FakeDateTime, time=datetime.time)):
            self.assertTrue(functions.is_within_schedule(schedule))


class TestStateManagerReloadsConfig(unittest.TestCase):
    def test_idle_timeout_change_is_applied_without_restart(self):
        from lib.state_manager import StateManager

        class Settings:
            def __init__(self):
                self.values = {"idle_timeout_minutes": "10"}
                self.last_save = 1

            def get_setting_value(self, name):
                return self.values.get(name)

        settings = Settings()
        manager = StateManager(settings)
        self.assertEqual(manager.idle_timeout_seconds, 600)

        settings.values["idle_timeout_minutes"] = "2"
        settings.last_save = 2
        manager.update_state()

        self.assertEqual(manager.idle_timeout_seconds, 120)


class TestNotesTime(unittest.TestCase):
    def test_meta_message_deltas_are_accumulated(self):
        from lib.learnmidi import compute_notes_time

        mid = mido.MidiFile(ticks_per_beat=480)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
        track.append(mido.Message("note_on", note=60, velocity=80, time=0))
        track.append(mido.Message("note_off", note=60, velocity=0, time=480))
        track.append(mido.MetaMessage("marker", text="B", time=480))
        track.append(mido.Message("note_on", note=62, velocity=80, time=480))
        track.append(mido.Message("note_off", note=62, velocity=0, time=480))

        times = compute_notes_time(mid)

        self.assertEqual([round(t, 3) for t in times], [0, 0.5, 1.5, 2.0])


class TestRenameMovesSheetMusic(unittest.TestCase):
    def test_non_bundle_rename_moves_sidecar_and_cache(self):
        import webinterface.views_api as views_api
        from webinterface import webinterface, app_state

        previous_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                os.makedirs("Songs/cache")
                Path("Songs/old.mid").write_bytes(b"MThd")
                Path("Songs/old.musicxml").write_text("<x/>")
                Path("Songs/cache/old.mid.p").write_bytes(b"x")
                songs_dir = Path("Songs").resolve()
                menu = SimpleNamespace(last_activity=0, is_idle_animation_running=False)
                with patch.object(views_api, "SONGS_DIR", songs_dir), \
                        patch.object(app_state, "menu", menu, create=True), \
                        patch.object(app_state, "state_manager", None, create=True):
                    client = webinterface.test_client()
                    response = client.get(
                        "/api/change_setting",
                        query_string={"setting_name": "change_song_name", "value": "old.mid", "second_value": "new.mid"},
                    )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.get_json()["success"])
                self.assertEqual(sorted(os.listdir("Songs")), ["cache", "new.mid", "new.musicxml"])
                self.assertEqual(os.listdir("Songs/cache"), ["new.mid.p"])
            finally:
                os.chdir(previous_cwd)


class TestStartEndPointWithoutSong(unittest.TestCase):
    def test_set_current_time_points_without_song_do_not_crash(self):
        from webinterface import webinterface, app_state

        learning = SimpleNamespace(song_tracks=[], current_idx=0, start_point=0, end_point=100)
        menu = SimpleNamespace(last_activity=0, is_idle_animation_running=False)
        with patch.object(app_state, "learning", learning, create=True), \
                patch.object(app_state, "menu", menu, create=True), \
                patch.object(app_state, "state_manager", None, create=True):
            client = webinterface.test_client()
            for name in ("set_current_time_as_start_point", "set_current_time_as_end_point"):
                response = client.get("/api/change_setting", query_string={"setting_name": name, "value": ""})
                self.assertEqual(response.status_code, 200, name)
                self.assertFalse(response.get_json()["success"], name)


class TestHostnameSuffix(unittest.TestCase):
    def test_only_exact_local_suffix_is_removed(self):
        from lib.platform import _strip_local_suffix

        self.assertEqual(_strip_local_suffix("piano"), "piano")
        self.assertEqual(_strip_local_suffix("piano.local"), "piano")
        self.assertEqual(_strip_local_suffix("Radio.LOCAL"), "Radio")
        self.assertEqual(_strip_local_suffix("local"), "local")


class TestSpeedColorZeroMaxNotes(unittest.TestCase):
    def test_zero_max_notes_does_not_divide_by_zero(self):
        from lib.color_mode import ColorMode

        ledsettings = SimpleNamespace(
            speed_slowest={"red": 0, "green": 255, "blue": 0},
            speed_fastest={"red": 255, "green": 0, "blue": 0},
            speed_period_in_seconds=3.0,
            speed_max_notes=0,
        )
        color_mode = ColorMode("Speed", ledsettings)
        color_mode.NoteOn(None, 0, None, 10)  # ne doit pas lever ZeroDivisionError


class TestNoDirectHardwareImports(unittest.TestCase):
    def test_lib_modules_use_driver_shim(self):
        allowed = {"rpi_drivers.py", "null_drivers.py"}
        offenders = []
        for path in (PROJECT_ROOT / "lib").glob("*.py"):
            if path.name in allowed:
                continue
            if re.search(r"^\s*(from|import)\s+rpi_ws281x\b", path.read_text(encoding="utf-8"), re.MULTILINE):
                offenders.append(path.name)
        self.assertEqual(offenders, [])


class TestAutoinstallRetry(unittest.TestCase):
    def test_failed_command_is_retried_under_set_e(self):
        script = (PROJECT_ROOT / "autoinstall.sh").read_text(encoding="utf-8")
        match = re.search(r"^execute_command\(\) \{.*?^\}", script, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(match)
        harness = "\n".join([
            "set -euo pipefail",
            "ping() { return 0; }",
            "sleep() { :; }",
            match.group(0),
            'execute_command "false" "check_internet"',
        ])
        result = subprocess.run(["bash", "-c", harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.count("Command failed with exit code 1."), 18)


if __name__ == "__main__":
    unittest.main()
