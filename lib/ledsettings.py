import ast
import random
import time
from xml.dom import minidom

from lib.functions import fastColorWipe, find_between, clamp
from neopixel import Color

class LedSettings:
    def __init__(self, usersettings):

        self.usersettings = usersettings

        self.red = int(usersettings.get_setting_value("red"))
        self.green = int(usersettings.get_setting_value("green"))
        self.blue = int(usersettings.get_setting_value("blue"))
        self.mode = usersettings.get_setting_value("mode")
        self.fadingspeed = int(usersettings.get_setting_value("fadingspeed"))
        self.color_mode = usersettings.get_setting_value("color_mode")
        self.rainbow_offset = int(usersettings.get_setting_value("rainbow_offset"))
        self.rainbow_scale = int(usersettings.get_setting_value("rainbow_scale"))
        self.rainbow_timeshift = int(usersettings.get_setting_value("rainbow_timeshift"))

        self.multicolor = ast.literal_eval(usersettings.get_setting_value("multicolor"))
        self.multicolor_range = ast.literal_eval(usersettings.get_setting_value("multicolor_range"))

        self.sequence_active = usersettings.get_setting_value("sequence_active")

        self.backlight_brightness = int(usersettings.get_setting_value("backlight_brightness"))
        self.backlight_brightness_percent = int(usersettings.get_setting_value("backlight_brightness_percent"))

        self.backlight_red = int(usersettings.get_setting_value("backlight_red"))
        self.backlight_green = int(usersettings.get_setting_value("backlight_green"))
        self.backlight_blue = int(usersettings.get_setting_value("backlight_blue"))

        self.adjacent_mode = usersettings.get_setting_value("adjacent_mode")
        self.adjacent_red = int(usersettings.get_setting_value("adjacent_red"))
        self.adjacent_green = int(usersettings.get_setting_value("adjacent_green"))
        self.adjacent_blue = int(usersettings.get_setting_value("adjacent_blue"))

        self.skipped_notes = usersettings.get_setting_value("skipped_notes")

        self.notes_in_last_period = []
        self.speed_period_in_seconds = 0.8

        self.speed_slowest = {}
        self.speed_slowest["red"] = int(usersettings.get_setting_value("speed_slowest_red"))
        self.speed_slowest["green"] = int(usersettings.get_setting_value("speed_slowest_green"))
        self.speed_slowest["blue"] = int(usersettings.get_setting_value("speed_slowest_blue"))

        self.speed_fastest = {}
        self.speed_fastest["red"] = int(usersettings.get_setting_value("speed_fastest_red"))
        self.speed_fastest["green"] = int(usersettings.get_setting_value("speed_fastest_green"))
        self.speed_fastest["blue"] = int(usersettings.get_setting_value("speed_fastest_blue"))

        self.speed_period_in_seconds = float(usersettings.get_setting_value("speed_period_in_seconds"))
        self.speed_max_notes = int(usersettings.get_setting_value("speed_max_notes"))

        self.gradient_start = {}
        self.gradient_start["red"] = int(usersettings.get_setting_value("gradient_start_red"))
        self.gradient_start["green"] = int(usersettings.get_setting_value("gradient_start_green"))
        self.gradient_start["blue"] = int(usersettings.get_setting_value("gradient_start_blue"))

        self.gradient_end = {}
        self.gradient_end["red"] = int(usersettings.get_setting_value("gradient_end_red"))
        self.gradient_end["green"] = int(usersettings.get_setting_value("gradient_end_green"))
        self.gradient_end["blue"] = int(usersettings.get_setting_value("gradient_end_blue"))

        self.key_in_scale = {}
        self.key_in_scale["red"] = int(usersettings.get_setting_value("key_in_scale_red"))
        self.key_in_scale["green"] = int(usersettings.get_setting_value("key_in_scale_green"))
        self.key_in_scale["blue"] = int(usersettings.get_setting_value("key_in_scale_blue"))

        self.key_not_in_scale = {}
        self.key_not_in_scale["red"] = int(usersettings.get_setting_value("key_not_in_scale_red"))
        self.key_not_in_scale["green"] = int(usersettings.get_setting_value("key_not_in_scale_green"))
        self.key_not_in_scale["blue"] = int(usersettings.get_setting_value("key_not_in_scale_blue"))

        self.scales = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
        self.scale_key = int(usersettings.get_setting_value("scale_key"))

        self.sequence_number = 0

        #if self.mode == "Disabled" and self.color_mode != "disabled":
        #    usersettings.change_setting_value("color_mode", "disabled")
            

    def add_instance(self, menu, ledstrip):
        self.menu = menu
        self.ledstrip = ledstrip
        menu.update_multicolor(self.multicolor)

    def addcolor(self):
        self.multicolor.append([0, 255, 0])
        self.multicolor_range.append([20, 108])

        self.usersettings.change_setting_value("multicolor", self.multicolor)
        self.usersettings.change_setting_value("multicolor_range", self.multicolor_range)

        self.menu.update_multicolor(self.multicolor)

    def deletecolor(self, key):
        del self.multicolor[int(key) - 1]
        del self.multicolor_range[int(key) - 1]

        self.usersettings.change_setting_value("multicolor", self.multicolor)
        self.usersettings.change_setting_value("multicolor_range", self.multicolor_range)

        self.menu.update_multicolor(self.multicolor)
        self.menu.go_back()

    def change_multicolor(self, choice, location, value):
        self.sequence_active = False
        location = location.replace('RGB_Color', '')
        location = int(location) - 1
        if choice == "Red":
            choice = 0
        elif choice == "Green":
            choice = 1
        else:
            choice = 2
        self.multicolor[int(location)][choice] += int(value)
        self.multicolor[int(location)][choice] = clamp(self.multicolor[int(location)][choice], 0, 255)

        self.usersettings.change_setting_value("multicolor", self.multicolor)

    def change_multicolor_range(self, choice, location, value):
        location = location.replace('Key_range', '')
        location = int(location) - 1
        if choice == "Start":
            choice = 0
        else:
            choice = 1

        self.multicolor_range[int(location)][choice] += int(value)
        self.usersettings.change_setting_value("multicolor_range", self.multicolor_range)

    def get_multicolors(self, number):
        number = int(number) - 1
        return str(self.multicolor[int(number)][0]) + ", " + str(self.multicolor[int(number)][1]) + ", " + str(
            self.multicolor[int(number)][2])

    def get_random_multicolor_in_range(self, note):
        temporary_multicolor = []
        i = 0
        for range in self.multicolor_range:
            if note >= range[0] and note <= range[1]:
                temporary_multicolor.append(self.multicolor[i])
            i += 1
        try:
            choosen_color = random.choice(temporary_multicolor)
        except:
            choosen_color = [0, 0, 0]
        return choosen_color

    def light_keys_in_range(self, location):
        fastColorWipe(self.ledstrip.strip, True, self)

        color_counter = 0
        for i in self.multicolor:

            start = self.multicolor_range[int(color_counter)][0]
            end = self.multicolor_range[int(color_counter)][1]

            if start > 92:
                note_offset_start = 2
            elif start > 55:
                note_offset_start = 1
            else:
                note_offset_start = 0

            if end > 92:
                note_offset_end = 2
            elif end > 55:
                note_offset_end = 1
            else:
                note_offset_end = 0

            red = self.multicolor[int(color_counter)][0]
            green = self.multicolor[int(color_counter)][1]
            blue = self.multicolor[int(color_counter)][2]

            self.ledstrip.strip.setPixelColor(int(((start - 20) * 2 - note_offset_start)),
                                              Color(int(green), int(red), int(blue)))
            self.ledstrip.strip.setPixelColor(int(((end - 20) * 2 - note_offset_end)),
                                              Color(int(green), int(red), int(blue)))

            color_counter += 1

    def change_color(self, color, value):
        self.sequence_active = False
        self.usersettings.change_setting_value("sequence_active", self.sequence_active)
        self.color_mode = "Single"
        self.usersettings.change_setting_value("color_mode", self.color_mode)
        if color == "Red":
            if self.red <= 255 and self.red >= 0:
                self.red += int(value)
                self.red = clamp(self.red, 0, 255)
                self.usersettings.change_setting_value("red", self.red)
        elif color == "Green":
            if self.green <= 255 and self.green >= 0:
                self.green += int(value)
                self.green = clamp(self.green, 0, 255)
                self.usersettings.change_setting_value("green", self.green)
        elif color == "Blue":
            if self.blue <= 255 and self.blue >= 0:
                self.blue += int(value)
                self.blue = clamp(self.blue, 0, 255)
                self.usersettings.change_setting_value("blue", self.blue)

    def change_color_name(self, color):
        self.sequence_active = False
        self.usersettings.change_setting_value("sequence_active", self.sequence_active)
        self.color_mode = "Single"
        self.usersettings.change_setting_value("color_mode", self.color_mode)
        self.red = int(find_between(str(color), "red=", ","))
        self.green = int(find_between(str(color), "green=", ","))
        self.blue = int(find_between(str(color), "blue=", ")"))

        self.usersettings.change_setting_value("red", self.red)
        self.usersettings.change_setting_value("green", self.green)
        self.usersettings.change_setting_value("blue", self.blue)

    def get_color(self, color):
        if color == "Red":
            return self.red
        elif color == "Green":
            return self.green
        elif color == "Blue":
            return self.blue

    def get_colors(self):
        return str(self.red) + ", " + str(self.green) + ", " + str(self.blue)

    def get_backlight_color(self, color):
        if color == "Red":
            return self.backlight_red
        elif color == "Green":
            return self.backlight_green
        elif color == "Blue":
            return self.backlight_blue

    def get_backlight_colors(self):
        return str(self.backlight_red) + ", " + str(self.backlight_green) + ", " + str(self.backlight_blue)

    def get_adjacent_color(self, color):
        if color == "Red":
            return self.adjacent_red
        elif color == "Green":
            return self.adjacent_green
        elif color == "Blue":
            return self.adjacent_blue

    def get_adjacent_colors(self):
        return str(self.adjacent_red) + ", " + str(self.adjacent_green) + ", " + str(self.adjacent_blue)

    def set_sequence(self, sequence, step, direct_step = False):
        try:
            if int(step) == 0 or direct_step == True:
                if direct_step == True:
                    self.step_number = int(step) + 1
                else:
                    self.step_number = 1
                self.sequences_tree = minidom.parse("sequences.xml")

                self.sequence_number = str(int(sequence) + 1)

                self.next_step = self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                    0].getElementsByTagName("next_step")[0].firstChild.nodeValue
                self.control_number = self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                    0].getElementsByTagName("control_number")[0].firstChild.nodeValue
                self.count_steps = 1
                #if(direct_step == False):
                self.sequence_active = True
                self.sequence_active_name = sequence
                while True:
                    try:
                        temp_step = self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                            0].getElementsByTagName("step_" + str(self.count_steps))[0].getElementsByTagName("color")[
                            0].firstChild.nodeValue
                        self.count_steps += 1
                    except:
                        self.count_steps -= 1
                        break
            else:
                self.step_number += 1
                if self.step_number > self.count_steps:
                    self.step_number = 1
            self.color_mode = \
                self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                    0].getElementsByTagName(
                    "step_" + str(self.step_number))[0].getElementsByTagName("color")[0].firstChild.nodeValue
            self.mode = \
                self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                    0].getElementsByTagName(
                    "step_" + str(self.step_number))[0].getElementsByTagName("light_mode")[0].firstChild.nodeValue

            if self.mode == "Velocity" or self.mode == "Fading":
                self.fadingspeed = self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                    0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName("speed")[
                    0].firstChild.nodeValue
                if self.mode == "Fading":
                    if self.fadingspeed == "Very fast":
                        self.fadingspeed = 50
                    elif self.fadingspeed == "Fast":
                        self.fadingspeed = 40
                    elif self.fadingspeed == "Medium":
                        self.fadingspeed = 20
                    elif self.fadingspeed == "Slow":
                        self.fadingspeed = 10
                    elif self.fadingspeed == "Very slow":
                        self.fadingspeed = 2
                    elif self.fadingspeed == "Instant":
                        self.fadingspeed = 1000

                if self.mode == "Velocity":
                    if self.fadingspeed == "Fast":
                        self.fadingspeed = 10
                    elif self.fadingspeed == "Medium":
                        self.fadingspeed = 8
                    elif self.fadingspeed == "Slow":
                        self.fadingspeed = 6
                    elif self.fadingspeed == "Very slow":
                        self.fadingspeed = 3
            if self.color_mode == "RGB":
                self.color_mode = "Single"
                self.red = int(self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                                   0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                    "Red")[0].firstChild.nodeValue)
                self.green = int(self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                                     0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                    "Green")[0].firstChild.nodeValue)
                self.blue = int(self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                                    0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                    "Blue")[0].firstChild.nodeValue)

            if self.color_mode == "Rainbow":
                self.rainbow_offset = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName("Offset")[
                        0].firstChild.nodeValue)
                self.rainbow_scale = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName("Scale")[
                        0].firstChild.nodeValue)
                self.rainbow_timeshift = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName("Timeshift")[
                        0].firstChild.nodeValue)

            if self.color_mode == "Speed":
                self.speed_slowest["red"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "speed_slowest_red")[0].firstChild.nodeValue)
                self.speed_slowest["green"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "speed_slowest_green")[0].firstChild.nodeValue)
                self.speed_slowest["blue"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "speed_slowest_blue")[0].firstChild.nodeValue)

                self.speed_fastest["red"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "speed_fastest_red")[0].firstChild.nodeValue)
                self.speed_fastest["green"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "speed_fastest_green")[0].firstChild.nodeValue)
                self.speed_fastest["blue"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "speed_fastest_blue")[0].firstChild.nodeValue)

                self.speed_period_in_seconds = float(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "speed_period_in_seconds")[0].firstChild.nodeValue)
                self.speed_max_notes = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "speed_max_notes")[0].firstChild.nodeValue)

            if self.color_mode == "Gradient":
                self.gradient_start["red"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "gradient_start_red")[0].firstChild.nodeValue)
                self.gradient_start["green"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "gradient_start_green")[0].firstChild.nodeValue)
                self.gradient_start["blue"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "gradient_start_blue")[0].firstChild.nodeValue)

                self.gradient_end["red"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "gradien_end_red")[0].firstChild.nodeValue)
                self.gradient_end["green"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "gradien_end_green")[0].firstChild.nodeValue)
                self.gradient_end["blue"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "gradien_end_blue")[0].firstChild.nodeValue)

            if self.color_mode == "Scale":
                self.key_in_scale["red"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "key_in_scale_red")[0].firstChild.nodeValue)
                self.key_in_scale["green"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "key_in_scale_green")[0].firstChild.nodeValue)
                self.key_in_scale["blue"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "key_in_scale_blue")[0].firstChild.nodeValue)

                self.key_not_in_scale["red"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "key_not_in_scale_red")[0].firstChild.nodeValue)
                self.key_not_in_scale["green"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "key_not_in_scale_green")[0].firstChild.nodeValue)
                self.key_not_in_scale["blue"] = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                        "key_not_in_scale_blue")[0].firstChild.nodeValue)

                self.scale_key = int(
                    self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                        0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName("scale_key")[
                        0].firstChild.nodeValue)

            if self.color_mode == "Multicolor":
                self.multicolor = []
                self.multicolor_range = []
                multicolor_number = 1
                multicolor_range_number = 1
                while True:
                    try:
                        colors = self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                            0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                            "color_" + str(multicolor_number))[0].firstChild.nodeValue
                        colors = colors.split(',')
                        red = colors[0].replace(" ", "")
                        green = colors[1].replace(" ", "")
                        blue = colors[2].replace(" ", "")
                        self.multicolor.append([int(red), int(green), int(blue)])
                        multicolor_number += 1
                    except:
                        break
                while True:
                    try:
                        colors_range = \
                            self.sequences_tree.getElementsByTagName("sequence_" + str(self.sequence_number))[
                                0].getElementsByTagName("step_" + str(self.step_number))[0].getElementsByTagName(
                                "color_range_" + str(multicolor_range_number))[0].firstChild.nodeValue
                        colors_range = colors_range.split(',')
                        start = colors_range[0].replace(" ", "")
                        end = colors_range[1].replace(" ", "")
                        self.multicolor_range.append([int(start), int(end)])
                        multicolor_range_number += 1
                    except:
                        break
        except:
            return False

    def change_backlight_brightness(self, value):
        self.backlight_brightness_percent += value
        self.backlight_brightness_percent = clamp(self.backlight_brightness_percent, 0, 100)
        self.backlight_brightness = 255 * self.backlight_brightness_percent / 100
        self.usersettings.change_setting_value("backlight_brightness", int(self.backlight_brightness))
        self.usersettings.change_setting_value("backlight_brightness_percent", self.backlight_brightness_percent)
        fastColorWipe(self.ledstrip.strip, True, self)

    def change_backlight_color(self, color, value):
        if color == "Red":
            if self.backlight_red <= 255 and self.backlight_red >= 0:
                self.backlight_red += int(value)
                self.backlight_red = clamp(self.backlight_red, 0, 255)
        elif color == "Green":
            if self.backlight_green <= 255 and self.backlight_green >= 0:
                self.backlight_green += int(value)
                self.backlight_green = clamp(self.backlight_green, 0, 255)
        elif color == "Blue":
            if self.backlight_blue <= 255 and self.backlight_blue >= 0:
                self.backlight_blue += int(value)
                self.backlight_blue = clamp(self.backlight_blue, 0, 255)
        self.usersettings.change_setting_value("backlight_red", self.backlight_red)
        self.usersettings.change_setting_value("backlight_green", self.backlight_green)
        self.usersettings.change_setting_value("backlight_blue", self.backlight_blue)

        fastColorWipe(self.ledstrip.strip, True, self)

    def change_adjacent_color(self, color, value):
        self.adjacent_mode = "RGB"
        self.usersettings.change_setting_value("adjacent_mode", self.adjacent_mode)
        if color == "Red":
            if self.adjacent_red <= 255 and self.adjacent_red >= 0:
                self.adjacent_red += int(value)
                self.adjacent_red = clamp(self.adjacent_red, 0, 255)
        elif color == "Green":
            if self.adjacent_green <= 255 and self.adjacent_green >= 0:
                self.adjacent_green += int(value)
                self.adjacent_green = clamp(self.adjacent_green, 0, 255)
        elif color == "Blue":
            if self.adjacent_blue <= 255 and self.adjacent_blue >= 0:
                self.adjacent_blue += int(value)
                self.adjacent_blue = clamp(self.adjacent_blue, 0, 255)
        self.usersettings.change_setting_value("adjacent_red", self.adjacent_red)
        self.usersettings.change_setting_value("adjacent_green", self.adjacent_green)
        self.usersettings.change_setting_value("adjacent_blue", self.adjacent_blue)
        fastColorWipe(self.ledstrip.strip, True, self)

    def speed_add_note(self):
        current_time = time.time()
        self.notes_in_last_period.append(current_time)

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
            red = ((self.speed_fastest["red"] - self.speed_slowest["red"]) * float(speed_percent)) + self.speed_slowest[
                "red"]
            green = ((self.speed_fastest["green"] - self.speed_slowest["green"]) * float(speed_percent)) + \
                    self.speed_slowest["green"]
            blue = ((self.speed_fastest["blue"] - self.speed_slowest["blue"]) * float(speed_percent)) + \
                   self.speed_slowest["blue"]
        return [round(red), round(green), round(blue)]

    def gradient_get_colors(self, position):

        red = ((position / self.ledstrip.led_number) * (self.gradient_end["red"] - self.gradient_start["red"])) + \
              self.gradient_start["red"]
        green = ((position / self.ledstrip.led_number) * (self.gradient_end["green"] - self.gradient_start["green"])) + \
                self.gradient_start["green"]
        blue = ((position / self.ledstrip.led_number) * (self.gradient_end["blue"] - self.gradient_start["blue"])) + \
               self.gradient_start["blue"]

        return [round(red), round(green), round(blue)]