from lib.functions import *
from lib.neopixel import Color
import colorsys
import mido

def ColorInt2RGB(color: int):
    return (color >> 16 & 0xFF, color >> 8 & 0xFF, color & 0xFF)

class ColorMode():
    def LoadSettings(self, ledsettings):
        """Called whenever settings change"""
        pass

    def NoteOn(self, midi_event, midi_state):
        """Primary high-level function for ColorMode

        Called on midi note-on
        Use midi_event and return a color int to be applied to LED
        """
        pass

    def MidiEvent(self, midi_event, midi_state, ledstrip):
        """Optional low-level function for ColorMode

        Called on every midi event, with direct ledstrip access
        If using this function without NoteOn, then
        ledstrip.strip.setPixelColor must be set manually, 
        as well as call ledstrip.set_adjacent_colors
        """
        pass

    def ColorUpdate(self, time_delta, led_pos, old_color):
        """Optional.  Called on every event loop refresh where old_color > 0

        Called prior to fade mode processing.
        Return a color int to be applied to LED, or None for no change
        """
        pass

class VelocityRainbow(ColorMode):
    def LoadSettings(self, ledsettings):
        self.offset = int(ledsettings.velocityrainbow_offset)
        self.scale = int(ledsettings.velocityrainbow_scale)
        self.curve = int(ledsettings.velocityrainbow_scale)

    def NoteOn(self, midi_event: mido.Message, midi_state=None):
        x = int(((255 * powercurve(midi_event.velocity / 127, self.curve / 100)
                    * (self.scale / 100) % 256) + self.offset) % 256)
        x2 = colorsys.hsv_to_rgb(x / 255, 1, (midi_event.velocity / 127) * 0.3 + 0.7)
        return Color(*map(lambda x: round(x * 255), x2))
