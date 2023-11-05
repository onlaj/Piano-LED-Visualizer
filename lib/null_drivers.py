import time

class GPIOnull():
    def __init__(self):
        pass

    def __getattr__(self, name):
        return self.pass_func

    def pass_func(self, *args, **kwargs):
        pass

    def input(self, pin):
        if pin == 12: # SENSECOVER
            return 1
        else:
            return None

class SPInull():
    def __getattr__(self, name):
        return self.pass_func

    def pass_func(self, *args, **kwargs):
        pass

class PixelStrip_null():
    def __init__(self, numleds):
        self.leds = numleds

    def __getattr__(self, name):
        return self.pass_func

    def pass_func(self, *args, **kwargs):
        pass

    def numPixels(self):
        return self.leds

    def show(self):
        fps = 100
        time.sleep(1/fps)
