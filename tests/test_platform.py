#!/usr/bin/env python3

import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.append('./')
sys.path.append('../')
from lib.platform import PlatformRasp  # noqa: E402

IWCONFIG_CONNECTED = """wlan0     IEEE 802.11  ESSID:"HomeWifi"
          Mode:Managed  Frequency:5.18 GHz  Access Point: AA:BB:CC:DD:EE:FF
"""


def fake_check_output(iwconfig=None, default_route=""):
    """Stand-in for subprocess.check_output; None means the tool is missing."""

    def check_output(cmd, *args, **kwargs):
        if cmd[0] == "iwconfig":
            if iwconfig is None:
                raise FileNotFoundError("iwconfig")
            return iwconfig
        if cmd[:2] == ["ip", "route"]:
            return default_route
        raise AssertionError(f"unexpected command: {cmd}")

    return check_output


class TestGetCurrentConnections(unittest.TestCase):
    def get(self, **kwargs):
        with patch("lib.platform.subprocess.check_output", side_effect=fake_check_output(**kwargs)):
            return PlatformRasp.get_current_connections()

    def test_wifi_connection(self):
        self.assertEqual(self.get(iwconfig=IWCONFIG_CONNECTED),
                         (True, "HomeWifi", "AA:BB:CC:DD:EE:FF"))

    def test_hotspot_mode(self):
        self.assertFalse(self.get(iwconfig="wlan0  Mode:Master")[0])

    def test_without_iwconfig_default_route_is_online(self):
        success, name, _ = self.get(default_route="default via 192.168.1.1 dev eth0")
        self.assertTrue(success)
        self.assertEqual(name, "Connected")

    def test_without_iwconfig_and_without_route_is_offline(self):
        self.assertFalse(self.get(default_route="")[0])

    def test_no_wifi_interface_but_wired_connection_is_online(self):
        success, _, _ = self.get(iwconfig="lo  no wireless extensions.\n",
                                 default_route="default via 192.168.1.1 dev eth0")
        self.assertTrue(success)

    def test_iwconfig_error_is_reported(self):
        def failing(cmd, *args, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)

        with patch("lib.platform.subprocess.check_output", side_effect=failing):
            self.assertEqual(PlatformRasp.get_current_connections(),
                             (False, "Error occurred while getting Wi-Fi information.", ""))


class TestManageHotspot(unittest.TestCase):
    def hotspot_enabled_after(self, checks, **kwargs):
        platform = PlatformRasp()
        hotspot = SimpleNamespace(hotspot_script_time=0, last_wifi_check_time=0, time_without_wifi=0)
        usersettings = MagicMock()
        usersettings.get.return_value = 0
        midiports = SimpleNamespace(last_activity=0)
        start = 1000000
        with patch("lib.platform.subprocess.check_output", side_effect=fake_check_output(**kwargs)), \
                patch.object(PlatformRasp, "enable_hotspot") as enable_hotspot:
            for check in range(checks + 1):
                platform.manage_hotspot(hotspot, usersettings, midiports, current_time=start + check * 61)
        return enable_hotspot.called

    def test_wired_connection_without_iwconfig_keeps_hotspot_off(self):
        self.assertFalse(self.hotspot_enabled_after(10, default_route="default via 192.168.1.1 dev eth0"))

    def test_wired_connection_without_wifi_interface_keeps_hotspot_off(self):
        self.assertFalse(self.hotspot_enabled_after(10, iwconfig="lo  no wireless extensions.\n",
                                                    default_route="default via 192.168.1.1 dev eth0"))

    def test_no_connection_enables_hotspot(self):
        self.assertTrue(self.hotspot_enabled_after(10, default_route=""))


if __name__ == '__main__':
    unittest.main()
