from xml.etree import ElementTree as ET
import time
from functools import reduce
from lib.log_setup import logger


class UserSettings:
    def __init__(self, config="config/settings.xml", default_config="config/default_settings.xml"):
        self.cache = {}

        self.CONFIG_FILE = config
        self.DEFAULT_CONFIG_FILE = default_config
        self.pending_changes = False
        self.last_save = 0

        try:
            self.tree = ET.parse(self.CONFIG_FILE)
            self.root = self.tree.getroot()
            self.xml_to_dict(self.cache, self.root)
        except:
            logger.warning("Can't load settings file, restoring defaults")
            self.reset_to_default()

        self.pending_reset = False

        self.copy_missing()
        if self.pending_changes:
            self.save_changes()


    # get setting

    def __getitem__(self, key):
        if isinstance(key, str):
            return self.cache[key]
        elif hasattr(key, '__iter__'):
            # deep get
            return reduce(dict.__getitem__, key, self.cache)

    def get(self, key):
        try:
            return self.__getitem__(key)
        except:
            return None

    def get_setting_value(self, name):
        return self.get(name)

    def get_copy(self):
        return self.cache.copy()


    # set setting

    def __setitem__(self, key, value):
        val = str(value)
        self._xml_set(key, val)

        if isinstance(key, str):
            self.cache[key] = val
        elif hasattr(key, '__iter__'):
            d = reduce(dict.__getitem__, key[:-1], self.cache)
            d[key[-1]] = val

    def set(self, key, value):
        self.__setitem__(key, value)

    def change_setting_value(self, name, value):
        self.set(name, value)



    def get_cms(self, color_mode, key=None):
        if key is None:
            return self.get(("color_mode_settings", color_mode))

        return self.get(("color_mode_settings", color_mode, key))

    def set_cms(self, color_mode, key, value):
        return self.set(("color_mode_settings", color_mode, key), value)


    def _xml_set(self, key, value):
        if isinstance(key, str):
            xpath = key
        elif hasattr(key, '__iter__'):
            xpath = '/'.join(key)

        elem = self.root.find("./" + xpath)
        if elem is None:
            raise Exception("XML path not found: " + xpath) 

        elem.text = str(value)
        self.pending_changes = True

    def save_changes(self):
        if self.pending_changes:
            self.pending_changes = False

            self.tree.write(self.CONFIG_FILE)
            # Avoid re-parsing: we already have the tree structure in memory
            # Just refresh the root reference (it's already updated from _xml_set calls)
            # Only re-parse if we need to ensure file consistency, but for performance,
            # we can skip this since we're writing our in-memory tree
            # self.tree = ET.parse(self.CONFIG_FILE)  # Removed redundant parse
            # self.root = self.tree.getroot()  # Root is already current
            # Cache is already updated via _xml_set, so no need to rebuild
            self.last_save = time.time()

    def reset_to_default(self):
        self.tree = ET.parse(self.DEFAULT_CONFIG_FILE)
        self.tree.write(self.CONFIG_FILE)
        self.root = self.tree.getroot()
        self.xml_to_dict(self.cache, self.root)
        self.pending_reset = True
        self.last_save = time.time()

    def xml_to_dict(self, dict, node):
        """Recursively convert xml node into dict
        Assumes xml is simple <tag>text</tag> format, attributes ignored
        """
        for elem in node:
            if len(elem) == 0:
                # No subelements, get text as value
                dict[elem.tag] = elem.text
            else:
                dict[elem.tag] = {}
                self.xml_to_dict(dict[elem.tag], elem)

    def copy_missing(self):
        path = []
        for event, def_elem in ET.iterparse(self.DEFAULT_CONFIG_FILE, events=("start", "end")):
            if event == 'start':
                path.append(def_elem.tag)

                # iterparse makes path[0] the root "settings"; skip root
                if len(path[1:]) == 0:
                    continue

                # Find element in settings.xml
                findstr = './' + '/'.join(path[1:])
                elem = self.root.find(findstr)

                # If element is missing, copy it to the correct location
                if elem is None:
                    #ET.dump(def_elem)

                    # [1: - ignore 'settings' root element
                    # :-1] - get parent; do not include current (last) element
                    if len(path[1:-1]) == 0:
                        parent_elem = self.root
                    else:
                        parent_find = './' + '/'.join(path[1:-1])
                        parent_elem = self.root.find(parent_find)
                    
                    parent_elem.insert(0, def_elem)     # better indentation preservation when inserting at top, vs append
                    self.pending_changes = True

            elif event == 'end':
                path.pop()

        if self.pending_changes:
            self.xml_to_dict(self.cache, self.root)
