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
        # Snapshot the current palette/ranges so we can work without repeatedly
        # touching LedSettings during fast MIDI bursts.
        self.multicolor = tuple(
            tuple(int(channel) for channel in color)
            for color in ledsettings.multicolor
        )
        self.multicolor_range = tuple(
            tuple(int(bound) for bound in color_range)
            for color_range in ledsettings.multicolor_range
        )
        self.multicolor_index = 0
        self.multicolor_iteration = ledsettings.multicolor_iteration
        self._build_note_cache()

    def NoteOn(self, midi_event: mido.Message, midi_time, midi_state, note_position):
        if not self.multicolor:
            return (0, 0, 0)

        if self.multicolor_iteration == 1:
            color = self.multicolor[self.multicolor_index]
            self.multicolor_index = (self.multicolor_index + 1) % len(self.multicolor)
            return color

        return self.get_random_multicolor_in_range(midi_event.note)

    def get_random_multicolor_in_range(self, note):
        note_index = clamp(int(note), 0, len(self._note_color_cache) - 1)
        colors_for_note = self._note_color_cache[note_index]
        if colors_for_note:
            return random.choice(colors_for_note)

        left_neighbor = self._left_neighbors[note_index]
        right_neighbor = self._right_neighbors[note_index]

        if left_neighbor and right_neighbor:
            left_pos, left_color = left_neighbor
            right_pos, right_color = right_neighbor
            distance = max(right_pos - left_pos, 1)
            percent_value = (note_index - left_pos) / distance

            red = int(round(left_color[0] + percent_value * (right_color[0] - left_color[0])))
            green = int(round(left_color[1] + percent_value * (right_color[1] - left_color[1])))
            blue = int(round(left_color[2] + percent_value * (right_color[2] - left_color[2])))
            return (clamp(red, 0, 255), clamp(green, 0, 255), clamp(blue, 0, 255))

        if right_neighbor:
            return right_neighbor[1]

        if left_neighbor:
            return left_neighbor[1]

        return self.multicolor[random.randrange(len(self.multicolor))]

    def _build_note_cache(self):
        """Precompute color candidates and nearest neighbors for every MIDI note."""
        max_note = 128
        note_cache = [[] for _ in range(max_note)]
        cleaned_ranges = []

        for color, color_range in zip(self.multicolor, self.multicolor_range):
            if not color_range or len(color_range) < 2:
                continue
            start, end = color_range
            start, end = sorted((int(start), int(end)))
            if end < 0 or start > 127:
                continue
            start = clamp(start, 0, 127)
            end = clamp(end, 0, 127)
            color_tuple = tuple(color)
            cleaned_ranges.append((start, end, color_tuple))
            for midi_note in range(start, end + 1):
                note_cache[midi_note].append(color_tuple)

        self._note_color_cache = tuple(tuple(colors) for colors in note_cache)

        ranges_by_end = sorted(cleaned_ranges, key=lambda item: item[1])
        left_neighbors = [None] * max_note
        end_idx = -1
        for midi_note in range(max_note):
            while end_idx + 1 < len(ranges_by_end) and ranges_by_end[end_idx + 1][1] < midi_note:
                end_idx += 1
            left_neighbors[midi_note] = (
                (ranges_by_end[end_idx][1], ranges_by_end[end_idx][2]) if end_idx >= 0 else None
            )

        ranges_by_start = sorted(cleaned_ranges, key=lambda item: item[0])
        right_neighbors = [None] * max_note
        start_idx = 0
        for midi_note in range(max_note):
            while start_idx < len(ranges_by_start) and ranges_by_start[start_idx][0] <= midi_note:
                start_idx += 1
            right_neighbors[midi_note] = (
                (ranges_by_start[start_idx][0], ranges_by_start[start_idx][2])
                if start_idx < len(ranges_by_start) else None
            )

        self._left_neighbors = tuple(left_neighbors)
        self._right_neighbors = tuple(right_neighbors)

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
