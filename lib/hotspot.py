import time


class Hotspot:
    def __init__(self):
        self.hotspot_script_time = 0
        self.time_without_wifi = 0
        self.last_wifi_check_time = 0
