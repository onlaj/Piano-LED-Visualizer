#!/usr/bin/env python3

import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
