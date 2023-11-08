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


# Color from older version of rpi-ws281x
def Color(red, green, blue, white=0):
    """Convert the provided red, green, blue color to a 24-bit color value.
    Each color component should be a value 0-255 where 0 is the lowest intensity
    and 255 is the highest intensity.
    """
    return (white << 24) | (red << 16) | (green << 8) | blue
