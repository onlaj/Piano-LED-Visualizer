#!/usr/bin/env python3

import sys
sys.path.append('./')
sys.path.append('../')
import os
import unittest
from lib.usersettings import UserSettings


class TestUserSettings(unittest.TestCase):
    def load_usersettings(self, default_file="default-test1.xml"):
        self.us = UserSettings(self.config_path + "settings-test.xml", self.config_path + default_file)

    def setUp(self):
        abspath = os.path.abspath(__file__)
        self.config_path = os.path.dirname(abspath) + "/config-test/"

        self.load_usersettings()
        self.us.reset_to_default()

        self.keys = ["screen_on", ["screen_on"], ["color_mode_settings", "VelocityRainbow", "scale"]]
        self.orig_vals = ["1", "1", "120"]
        self.notfound_keys = ["NotFound", ["NotFound"], ["color_mode_settings", "NotFound"], ["color_mode_settings", "NotFound1", "NotFound2"]]

    def test_01_get(self):
        for i,k in enumerate(self.keys):
            self.assertEqual(self.us.get(k), self.orig_vals[i])
            self.assertEqual(self.us.get_setting_value(k), self.orig_vals[i])
            self.assertEqual(self.us[k], self.orig_vals[i])

    def test_02_set(self):
        for k in self.keys:
            old = self.us.get(k)

            self.us.change_setting_value(k, "888")
            self.assertEqual(self.us.get(k), "888")

            self.us[k] = "999"
            self.assertEqual(self.us.get(k), "999")

            self.us.set(k, old)
            self.assertEqual(self.us.get(k), old)
    
    def test_03_get_dict(self):
        key = "VelocityRainbow"
        val = {'offset': '210', 'scale': '120', 'curve': '0'}

        get1 = self.us.get(["color_mode_settings", key])
        get2 = self.us.get_cms(key)

        self.assertEqual(get1, get2)
        self.assertEqual(get1, val)

    def test_04_get_notfound(self):
        for k in self.notfound_keys:
            self.assertIsNone(self.us.get(k))
            with self.assertRaises(Exception):
                self.us[k]
        
    def test_05_set_notfound(self):
        for k in self.notfound_keys:
            with self.assertRaises(Exception):
                self.us.set(k, "error")
                self.us[k] = "error"

    def test_06_save(self):
        for k in self.keys:
            old = self.us.get(k)

            self.us.set(k, "000")
            self.us.save_changes()

            self.load_usersettings()
            self.assertEqual(self.us.get(k), "000", "Setting not saved to file.")

            self.us.set(k, old)
            self.us.save_changes()
            self.assertEqual(self.us.get(k), old)    

    def test_07_missing(self):
        self.load_usersettings("default-test1.xml")
        self.us.reset_to_default()
        self.assertIsNone(self.us.get("missing"))
        self.load_usersettings("default-test2.xml")

        self.assertEqual(self.us.get("missing"), "miss1")
        self.assertEqual(self.us.get("missing_nest"), {"sub": "sub"})
        self.assertEqual(self.us.get(["color_mode_settings", "VelocityRainbow", "missing"]), "miss2")
        self.assertEqual(self.us.get(["color_mode_settings", "missing_color_mode", "param"]), "1")

        self.assertEqual(self.us.get_cms("VelocityRainbow", "offset"), "210")


if __name__ == '__main__':
    unittest.main()
