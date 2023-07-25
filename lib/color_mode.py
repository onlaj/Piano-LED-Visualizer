from lib.functions import *
from lib.neopixel import Color
import colorsys
import mido

def ColorInt2RGB(color: int):
    return (color >> 16 & 0xFF, color >> 8 & 0xFF, color & 0xFF)

class ColorMode(object):
    def __new__(cls, name, ledsettings):
        """Automagic factory for creating ColorMode

        Adapted from https://stackoverflow.com/questions/3076537/virtual-classes-doing-it-right
        and https://stackoverflow.com/questions/5953759/using-a-class-new-method-as-a-factory-init-gets-called-twice
        """
        if cls is ColorMode:
            if name == 'Single':
                new_cls = SingleColor
            elif name == 'Rainbow':
                new_cls = Rainbow
            elif name == 'Gradient':
                new_cls = Gradient
            elif name == 'VelocityRainbow':
                new_cls = VelocityRainbow
            else:
                new_cls = cls
        else:
            new_cls = cls

        return super(ColorMode, cls).__new__(new_cls)

    def __init__(self, name, ledsettings):
        self.LoadSettings(ledsettings)

    def LoadSettings(self, ledsettings):
        """Called whenever settings change"""
        pass

    def NoteOn(self, midi_event, midi_state, note_position):
        """Primary high-level function for ColorMode

        Called on midi note-on
        Use midi_event and return a color int to be applied to LED
        """
        pass

    def MidiEvent(self, midi_event, midi_state, ledstrip):
        """Optional low-level function for ColorMode

        Called on every midi event, with direct ledstrip access.
        If using this function without NoteOn, then
        ledstrip.strip.setPixelColor must be set manually, 
        as well set ledstrip.keylist_color for fade processing
        and call ledstrip.set_adjacent_colors.
        """
        pass

    def ColorUpdate(self, time_delta, led_pos, old_color):
        """Optional.  Called on every event loop refresh where old_color > 0

        Called prior to fade mode processing.
        Return a color int to be applied to LED, or None for no change
        """
        pass


class SingleColor(ColorMode):
    def LoadSettings(self, ledsettings):
        self.red = ledsettings.get_color("Red")
        self.green = ledsettings.get_color("Green")
        self.blue = ledsettings.get_color("Blue")

    def NoteOn(self, midi_event: mido.Message, midi_state, note_position):
        return Color(self.red, self.green, self.blue)


class Rainbow(ColorMode):
    def LoadSettings(self, ledsettings):
        self.offset = int(ledsettings.rainbow_offset)
        self.scale = int(ledsettings.rainbow_scale)
        self.timeshift = int(ledsettings.rainbow_timeshift)
        self.timeshift_start = time.time()

    def NoteOn(self, midi_event: mido.Message, midi_state, note_position):
        shift = (time.time() - self.timeshift_start) * self.timeshift
        return Color(*self.calculate_rainbow_colors(note_position, shift))

    def ColorUpdate(self, time_delta, led_pos, old_color):
        return self.NoteOn(None, None, led_pos)

    def calculate_rainbow_colors(self, note_position, shift):
        rainbow_value = int((int(note_position) + self.offset + shift) * (
                float(self.scale) / 100)) & 255
        red = get_rainbow_colors(rainbow_value, "red")
        green = get_rainbow_colors(rainbow_value, "green")
        blue = get_rainbow_colors(rainbow_value, "blue")
        return red, green, blue


class Gradient(ColorMode):
    def LoadSettings(self, ledsettings):
        self.led_number = ledsettings.ledstrip.led_number
        self.gradient_start = {"red": int(ledsettings.usersettings.get_setting_value("gradient_start_red")),
                               "green": int(ledsettings.usersettings.get_setting_value("gradient_start_green")),
                               "blue": int(ledsettings.usersettings.get_setting_value("gradient_start_blue"))}

        self.gradient_end = {"red": int(ledsettings.usersettings.get_setting_value("gradient_end_red")),
                             "green": int(ledsettings.usersettings.get_setting_value("gradient_end_green")),
                             "blue": int(ledsettings.usersettings.get_setting_value("gradient_end_blue"))}

    def NoteOn(self, midi_event: mido.Message, midi_state, note_position):
        return Color(*self.gradient_get_colors(note_position))

    def gradient_get_colors(self, position):
        red = ((position / self.led_number) *
               (self.gradient_end["red"] - self.gradient_start["red"])) + self.gradient_start["red"]
        green = ((position / self.led_number) *
                 (self.gradient_end["green"] - self.gradient_start["green"])) + self.gradient_start["green"]
        blue = ((position / self.led_number) *
                (self.gradient_end["blue"] - self.gradient_start["blue"])) + self.gradient_start["blue"]

        return (round(red), round(green), round(blue))


class VelocityRainbow(ColorMode):
    def LoadSettings(self, ledsettings):
        self.offset = int(ledsettings.velocityrainbow_offset)
        self.scale = int(ledsettings.velocityrainbow_scale)
        self.curve = int(ledsettings.velocityrainbow_curve)

    def NoteOn(self, midi_event: mido.Message, midi_state, note_position=None):
        x = int(((255 * powercurve(midi_event.velocity / 127, self.curve / 100)
                    * (self.scale / 100) % 256) + self.offset) % 256)
        x2 = colorsys.hsv_to_rgb(x / 255, 1, (midi_event.velocity / 127) * 0.3 + 0.7)
        return Color(*map(lambda x: round(x * 255), x2))
