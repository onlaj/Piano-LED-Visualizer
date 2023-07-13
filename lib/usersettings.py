from xml.etree import ElementTree as ET
import time

class UserSettings:
    def __init__(self):
        self.pending_changes = False
        self.last_save = 0
        try:
            self.tree = ET.parse("config/settings.xml")
            self.root = self.tree.getroot()
        except:
            print("Can't load settings file, restoring defaults")
            self.reset_to_default()

        self.pending_reset = False

        self.default_tree = ET.parse("config/default_settings.xml")
        self.default_root = self.default_tree.getroot()

    def get_setting_value(self, name):
        elem = self.root.find(name)
        if elem is None:
            elem = self.default_root.find(name)

        if elem is None:
            return None

        return elem.text

    def change_setting_value(self, name, value):
        elem = self.root.find(str(name))
        if elem is None:
            elem = ET.Element(str(name))
            elem.text = str(value)
            self.root.append(elem)
            # Appended item will have no whitespace formatting

            # ElementTree.indent only available in Python 3.9+
            # This will reformat the whole file and remove extraneous line-breaks, so leaving commented out
            #if "indent" in dir(ET):
            #    ET.indent(self.root)
        else:
            elem.text = str(value)

        self.pending_changes = True

    def save_changes(self):
        if self.pending_changes:
            self.pending_changes = False

            self.tree.write("config/settings.xml")
            self.tree = ET.parse("config/settings.xml")
            self.root = self.tree.getroot()
            self.last_save = time.time()

    def reset_to_default(self):
        self.tree = ET.parse("config/default_settings.xml")
        self.tree.write("config/settings.xml")
        self.root = self.tree.getroot()
        self.pending_reset = True
        self.last_save = time.time()
