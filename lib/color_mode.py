from lib.functions import *
import lib.colormaps as cmap
from lib.rpi_drivers import Color
import colorsys
import mido
import random

class ColorMode(object):
    def __new__(cls, name, ledsettings):
        """Automagic factory for creating ColorMode

        Adapted from https://stackoverflow.com/questions/3076537/virtual-classes-doing-it-right
        and https://stackoverflow.com/questions/5953759/using-a-class-new-method-as-a-factory-init-gets-called-twice
        """
        if cls is ColorMode:
            if name == 'Single':
                new_cls = SingleColor
            elif name == 'Multicolor':
                new_cls = Multicolor
            elif name == 'Rainbow':
                new_cls = Rainbow
            elif name == 'Speed':
                new_cls = SpeedColor
            elif name == 'Gradient':
                new_cls = Gradient
            elif name == 'Scale':
                new_cls = ScaleColoring
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

    def NoteOn(self, midi_event, midi_time, midi_state, note_position):
        """Primary high-level function for ColorMode

        Called on midi note-on
        Use midi_event and return a color tuple to be applied to LED
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
        Return a color tuple to be applied to LED, or None for no change
        """
        pass


class SingleColor(ColorMode):
    def LoadSettings(self, ledsettings):
        self.red = ledsettings.get_color("Red")
        self.green = ledsettings.get_color("Green")
        self.blue = ledsettings.get_color("Blue")

    def NoteOn(self, midi_event: mido.Message, midi_time, midi_state, note_position):
        return (self.red, self.green, self.blue)


class Multicolor(ColorMode):
    def LoadSettings(self, ledsettings):
        self.multicolor = ledsettings.multicolor
        self.multicolor_range = ledsettings.multicolor_range
        self.multicolor_index = 0
        self.multicolor_iteration = ledsettings.multicolor_iteration

    def NoteOn(self, midi_event: mido.Message, midi_time, midi_state, note_position):
            chosen_color = self.get_random_multicolor_in_range(midi_event.note)
            return chosen_color

    def get_random_multicolor_in_range(self, note):
        temporary_multicolor = []
        color_on_the_right = {}
        color_on_the_left = {}

        for i, range in enumerate(self.multicolor_range):
            if range[0] <= note <= range[1]:
                temporary_multicolor.append(self.multicolor[i])

            # get colors on the left and right
            if range[0] > note:
                color_on_the_right[range[0]] = self.multicolor[i]
            if range[1] < note:
                color_on_the_left[range[1]] = self.multicolor[i]

        if self.multicolor_iteration == 1:
            if self.multicolor_index >= len(self.multicolor):
                self.multicolor_index = 0
            chosen_color = self.multicolor[self.multicolor_index]
            self.multicolor_index += 1
        elif temporary_multicolor:
            chosen_color = random.choice(temporary_multicolor)
        else:
            # mix colors from left and right

            if color_on_the_right and color_on_the_left:
                right = min(color_on_the_right)
                left = max(color_on_the_left)

                left_to_right_distance = right - left
                percent_value = (note - left) / left_to_right_distance

                red = (percent_value * (color_on_the_right[right][0] -
                                        color_on_the_left[left][0])) + color_on_the_left[left][0]
                green = (percent_value * (color_on_the_right[right][1] -
                                          color_on_the_left[left][1])) + color_on_the_left[left][1]
                blue = (percent_value * (color_on_the_right[right][2] -
                                         color_on_the_left[left][2])) + color_on_the_left[left][2]

                chosen_color = [int(red), int(green), int(blue)]
            else:
                chosen_color = [0, 0, 0]

        return chosen_color

class Rainbow(ColorMode):
    def LoadSettings(self, ledsettings):
        self.offset = int(ledsettings.rainbow_offset)
        self.scale = int(ledsettings.rainbow_scale)
        self.timeshift = int(ledsettings.rainbow_timeshift)
        self.timeshift_start = time.time()
        self.colormap = ledsettings.rainbow_colormap
        if self.colormap not in cmap.colormaps:
            self.colormaps = "Rainbow"

    def NoteOn(self, midi_event: mido.Message, midi_time, midi_state, note_position):
        shift = (time.time() - self.timeshift_start) * self.timeshift
        rainbow_value = int((int(note_position) + self.offset + shift) * (
                float(self.scale) / 100)) & 255
        return cmap.colormaps[self.colormap][rainbow_value]

    def ColorUpdate(self, time_delta, led_pos, old_color):
        return self.NoteOn(None, None, None, led_pos)


class SpeedColor(ColorMode):
    def LoadSettings(self, ledsettings):
        self.notes_in_last_period = []
        self.speed_slowest = ledsettings.speed_slowest
        self.speed_fastest = ledsettings.speed_fastest
        self.speed_period_in_seconds = ledsettings.speed_period_in_seconds
        self.speed_max_notes = ledsettings.speed_max_notes

    def NoteOn(self, midi_event: mido.Message, midi_time, midi_state, note_position):
        current_time = time.time()
        self.notes_in_last_period.append(current_time)
        return self.speed_get_colors()

    def speed_get_colors(self):
        for note_time in self.notes_in_last_period[:]:
            if (time.time() - self.speed_period_in_seconds) > note_time:
                self.notes_in_last_period.remove(note_time)

        notes_count = len(self.notes_in_last_period)
        max_notes = self.speed_max_notes
        speed_percent = notes_count / float(max_notes)

        if notes_count > max_notes:
            red = self.speed_fastest["red"]
            green = self.speed_fastest["green"]
            blue = self.speed_fastest["blue"]
        else:
            red = ((self.speed_fastest["red"] - self.speed_slowest["red"]) *
                   float(speed_percent)) + self.speed_slowest["red"]
            green = ((self.speed_fastest["green"] - self.speed_slowest["green"]) *
                     float(speed_percent)) + self.speed_slowest["green"]
            blue = ((self.speed_fastest["blue"] - self.speed_slowest["blue"]) *
                    float(speed_percent)) + self.speed_slowest["blue"]
        return (round(red), round(green), round(blue))


class Gradient(ColorMode):
    def LoadSettings(self, ledsettings):
        self.led_number = int(ledsettings.usersettings.get_setting_value("led_count"))
        self.gradient_start = {"red": int(ledsettings.usersettings.get_setting_value("gradient_start_red")),
                               "green": int(ledsettings.usersettings.get_setting_value("gradient_start_green")),
                               "blue": int(ledsettings.usersettings.get_setting_value("gradient_start_blue"))}

        self.gradient_end = {"red": int(ledsettings.usersettings.get_setting_value("gradient_end_red")),
                             "green": int(ledsettings.usersettings.get_setting_value("gradient_end_green")),
                             "blue": int(ledsettings.usersettings.get_setting_value("gradient_end_blue"))}

    def NoteOn(self, midi_event: mido.Message, midi_time, midi_state, note_position):
        return self.gradient_get_colors(note_position)

    def gradient_get_colors(self, position):
        red = ((position / self.led_number) *
               (self.gradient_end["red"] - self.gradient_start["red"])) + self.gradient_start["red"]
        green = ((position / self.led_number) *
                 (self.gradient_end["green"] - self.gradient_start["green"])) + self.gradient_start["green"]
        blue = ((position / self.led_number) *
                (self.gradient_end["blue"] - self.gradient_start["blue"])) + self.gradient_start["blue"]

        return (round(red), round(green), round(blue))


class ScaleColoring(ColorMode):
    def LoadSettings(self, ledsettings):
        self.scale_key = int(ledsettings.scale_key)
        self.key_in_scale = ledsettings.key_in_scale
        self.key_not_in_scale = ledsettings.key_not_in_scale

    def NoteOn(self, midi_event: mido.Message, midi_time, midi_state, note_position):
        scale_colors = get_scale_color(self.scale_key, midi_event.note, self.key_in_scale, self.key_not_in_scale)
        return scale_colors


class VelocityRainbow(ColorMode):
    def LoadSettings(self, ledsettings):
        self.offset = int(ledsettings.velocityrainbow_offset)
        self.scale = int(ledsettings.velocityrainbow_scale)
        self.curve = int(ledsettings.velocityrainbow_curve)
        self.colormap = ledsettings.velocityrainbow_colormap

    def NoteOn(self, midi_event: mido.Message, midi_time, midi_state, note_position):
        if self.colormap not in cmap.colormaps:
            return None

        x = int(((255 * powercurve(midi_event.velocity / 127, self.curve / 100)
                    * (self.scale / 100) % 256) + self.offset) % 256)
        return cmap.colormaps[self.colormap][x]
