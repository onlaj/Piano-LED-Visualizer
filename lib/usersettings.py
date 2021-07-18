from xml.etree import ElementTree as ET


class UserSettings:
    def __init__(self):
        self.pending_changes = False
        try:
            self.tree = ET.parse("settings.xml")
            self.root = self.tree.getroot()
        except:
            print("Can't load settings file, restoring defaults")
            self.reset_to_default()

        self.pending_reset = False

    def get_setting_value(self, name):
        value = self.root.find(name).text
        return value

    def change_setting_value(self, name, value):
        self.root.find(str(name)).text = str(value)
        self.pending_changes = True

    def save_changes(self):
        if self.pending_changes:
            self.pending_changes = False

            self.tree.write("settings.xml")
            self.tree = ET.parse("settings.xml")
            self.root = self.tree.getroot()

    def reset_to_default(self):
        self.tree = ET.parse("default_settings.xml")
        self.tree.write("settings.xml")
        self.root = self.tree.getroot()
        self.pending_reset = True
