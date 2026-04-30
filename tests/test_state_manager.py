#!/usr/bin/env python3

import sys
import unittest
from unittest.mock import patch

sys.path.append("./")
sys.path.append("../")

from lib.state_manager import StateManager, SystemState


class FakeUserSettings:
    def get_setting_value(self, _name):
        return None


class TestStateManager(unittest.TestCase):
    def test_active_use_loop_delay_is_more_aggressive_than_normal(self):
        manager = StateManager(FakeUserSettings())
        manager.current_state = SystemState.ACTIVE_USE
        active_delay = manager.get_loop_delay()

        manager.current_state = SystemState.NORMAL
        normal_delay = manager.get_loop_delay()

        self.assertLess(active_delay, normal_delay)

    def test_update_midi_activity_uses_supplied_timestamp_without_time_lookup(self):
        manager = StateManager(FakeUserSettings())
        supplied_time = 1234.5

        with patch("lib.state_manager.time.time", side_effect=AssertionError("time.time should not be called")):
            manager.update_midi_activity(current_time=supplied_time)

        self.assertEqual(manager.last_midi_activity, supplied_time)
        self.assertEqual(manager.last_user_activity, supplied_time)


if __name__ == "__main__":
    unittest.main()
