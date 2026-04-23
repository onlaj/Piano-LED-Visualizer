#!/usr/bin/env python3

import sys
import unittest

sys.path.append("./")
sys.path.append("../")

from lib.display_refresh_policy import DisplayRefreshPolicy


class TestDisplayRefreshPolicy(unittest.TestCase):
    def test_static_menu_is_restored_only_once_after_hold_time(self):
        policy = DisplayRefreshPolicy()

        first = policy.should_show_static_menu(elapsed_time=20, hold_time=16, scroll_needed=False, should_refresh=True)
        second = policy.should_show_static_menu(elapsed_time=20, hold_time=16, scroll_needed=False, should_refresh=True)

        self.assertTrue(first)
        self.assertFalse(second)

    def test_hold_period_reset_allows_future_restore(self):
        policy = DisplayRefreshPolicy()

        policy.should_show_static_menu(elapsed_time=20, hold_time=16, scroll_needed=False, should_refresh=True)
        policy.should_show_static_menu(elapsed_time=5, hold_time=16, scroll_needed=False, should_refresh=True)
        third = policy.should_show_static_menu(elapsed_time=20, hold_time=16, scroll_needed=False, should_refresh=True)

        self.assertTrue(third)

    def test_scrolling_menu_can_still_refresh_repeatedly(self):
        policy = DisplayRefreshPolicy()

        first = policy.should_show_static_menu(elapsed_time=20, hold_time=16, scroll_needed=True, should_refresh=True)
        second = policy.should_show_static_menu(elapsed_time=20, hold_time=16, scroll_needed=True, should_refresh=True)

        self.assertTrue(first)
        self.assertTrue(second)


if __name__ == "__main__":
    unittest.main()
