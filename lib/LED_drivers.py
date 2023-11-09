import time

class PixelStrip_Emu():
    def __init__(self, numleds=176):
        self.leds = numleds
        self.VIS_FPS = 100

        self.led_state = [0] * self.leds

    def numPixels(self):
        return self.leds

    def setBrightness(self, brightness):
        pass

    def setPixelColor(self, pos, color):
        if 0 < pos < self.leds:
            self.led_state[pos] = color

    def getPixels(self):
        return self.led_state

    def show(self):
        time.sleep(1/self.VIS_FPS)
