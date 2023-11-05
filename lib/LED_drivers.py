import time

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

class PixelStrip_Emu():
    def __init__(self, numleds=176):
        self.leds = numleds
        self.VIS_FPS = 100
        self.WEB_FPS = 10

        self.led_state = [0] * self.leds

    def numPixels(self):
        return self.leds

    def setBrightness(self, brightness):
        pass

    def setPixelColor(self, pos, color):
        if 0 < pos < self.leds:
            self.led_state[pos] = color

    def show(self):
        time.sleep(1/self.VIS_FPS)
