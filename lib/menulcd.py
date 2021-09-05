import os

from subprocess import call
from xml.dom import minidom

import webcolors as wc
from PIL import ImageFont, Image, ImageDraw

import LCD_1in3
import LCD_1in44
import LCD_Config

from lib.functions import *
import RPi.GPIO as GPIO


class MenuLCD:
    def __init__(self, xml_file_name, args, usersettings, ledsettings, ledstrip, learning, saving, midiports):
        self.usersettings = usersettings
        self.ledsettings = ledsettings
        self.ledstrip = ledstrip
        self.learning = learning
        self.saving = saving
        self.midiports = midiports

        if args.display == '1in3':
            self.LCD = LCD_1in3.LCD()
            self.font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf', self.scale(10))
        else:
            self.LCD = LCD_1in44.LCD()
            self.font = ImageFont.load_default()
        self.LCD.LCD_Init()
        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), "GREEN")
        self.draw = ImageDraw.Draw(self.image)
        self.LCD.LCD_ShowImage(self.image, 0, 0)
        self.xml_file_name = xml_file_name
        self.DOMTree = minidom.parse(xml_file_name)
        self.currentlocation = "menu"
        self.scroll_hold = 0
        self.cut_count = 0
        self.pointer_position = 0
        self.background_color = usersettings.get_setting_value("background_color")
        self.text_color = usersettings.get_setting_value("text_color")
        self.update_songs()
        self.update_ports()
        self.speed_multiplier = 1

        self.screensaver_settings = dict()
        self.screensaver_settings['time'] = usersettings.get_setting_value("time")
        self.screensaver_settings['date'] = usersettings.get_setting_value("date")
        self.screensaver_settings['cpu_chart'] = usersettings.get_setting_value("cpu_chart")
        self.screensaver_settings['cpu'] = usersettings.get_setting_value("cpu")
        self.screensaver_settings['ram'] = usersettings.get_setting_value("ram")
        self.screensaver_settings['temp'] = usersettings.get_setting_value("temp")
        self.screensaver_settings['network_usage'] = usersettings.get_setting_value("network_usage")
        self.screensaver_settings['sd_card_space'] = usersettings.get_setting_value("sd_card_space")
        self.screensaver_settings['local_ip'] = usersettings.get_setting_value("local_ip")

        self.screensaver_delay = usersettings.get_setting_value("screensaver_delay")
        self.screen_off_delay = usersettings.get_setting_value("screen_off_delay")
        self.led_animation_delay = usersettings.get_setting_value("led_animation_delay")

        self.led_animation = usersettings.get_setting_value("led_animation")

        self.screen_on = usersettings.get_setting_value("screen_on")

        self.screen_status = 1

        self.screensaver_is_running = False

    def toggle_screensaver_settings(self, setting):
        setting = setting.lower()
        setting = setting.replace(" ", "_")
        if str(self.screensaver_settings[setting]) == "1":
            self.usersettings.change_setting_value(setting, "0")
            self.screensaver_settings[setting] = "0"
        else:
            self.usersettings.change_setting_value(setting, "1")
            self.screensaver_settings[setting] = "1"

    def update_songs(self):
        songs_list = os.listdir("Songs")
        self.DOMTree = minidom.parse(self.xml_file_name)
        for song in songs_list:
            # List of songs for Play_MIDI
            element = self.DOMTree.createElement("Choose_song")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", song)
            mc = self.DOMTree.getElementsByTagName("Play_MIDI")[0]
            mc.appendChild(element)
            # List of songs for Learn_MIDI
            element = self.DOMTree.createElement("Load_song")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", song)
            mc = self.DOMTree.getElementsByTagName("Learn_MIDI")[0]
            mc.appendChild(element)

    def update_sequence_list(self):
        try:
            sequences_tree = minidom.parse("sequences.xml")
            self.update_songs()
            i = 0
            while True:
                try:
                    i += 1
                    sequence_name = \
                        sequences_tree.getElementsByTagName("sequence_" + str(i))[0].getElementsByTagName(
                            "sequence_name")[
                            0].firstChild.nodeValue
                    element = self.DOMTree.createElement("Sequences")
                    element.appendChild(self.DOMTree.createTextNode(""))
                    element.setAttribute("text", str(sequence_name))
                    mc = self.DOMTree.getElementsByTagName("LED_Strip_Settings")[0]
                    mc.appendChild(element)

                except:
                    break
        except:
            self.render_message("Something went wrong", "Check your sequences file", 1500)

    def update_ports(self):
        ports = mido.get_input_names()
        ports = list(dict.fromkeys(ports))
        self.update_sequence_list()
        for port in ports:
            element = self.DOMTree.createElement("Input")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", port)
            mc = self.DOMTree.getElementsByTagName("Ports_Settings")[0]
            mc.appendChild(element)

            element = self.DOMTree.createElement("Playback")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", port)
            mc = self.DOMTree.getElementsByTagName("Ports_Settings")[2]
            mc.appendChild(element)

    def update_multicolor(self, colors_list):
        i = 0
        self.update_ports()
        rgb_names = ["Red", "Green", "Blue"]
        for color in colors_list:
            i = i + 1

            element = self.DOMTree.createElement("Multicolor")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", "Color" + str(i))
            mc = self.DOMTree.getElementsByTagName("LED_Color")[0]
            mc.appendChild(element)

            element = self.DOMTree.createElement("Color" + str(i))
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", "RGB Color" + str(i))
            mc = self.DOMTree.getElementsByTagName("Multicolor")[0]
            mc.appendChild(element)

            # adding key range to menu
            element = self.DOMTree.createElement("Color" + str(i))
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", "Key range" + str(i))
            mc = self.DOMTree.getElementsByTagName("Multicolor")[0]
            mc.appendChild(element)

            element = self.DOMTree.createElement("Key_range" + str(i))
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", "Start")
            mc = self.DOMTree.getElementsByTagName("Color" + str(i))[0]
            mc.appendChild(element)

            element = self.DOMTree.createElement("Key_range" + str(i))
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", "End")
            mc = self.DOMTree.getElementsByTagName("Color" + str(i))[0]
            mc.appendChild(element)

            # adding delete
            element = self.DOMTree.createElement("Color" + str(i))
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", "Delete")
            mc = self.DOMTree.getElementsByTagName("Multicolor")[0]
            mc.appendChild(element)

            for rgb_name in rgb_names:
                element = self.DOMTree.createElement("RGB_Color" + str(i))
                element.appendChild(self.DOMTree.createTextNode(""))
                element.setAttribute("text", rgb_name)
                mc = self.DOMTree.getElementsByTagName("Color" + str(i))[0]
                mc.appendChild(element)

    def scale(self, size):
        return int(round(size * self.LCD.font_scale))

    def disable_screen(self):
        GPIO.output(24, 0)
        self.screen_on = 0
        self.usersettings.change_setting_value("screen_on", 0)

    def enable_screen(self):
        GPIO.output(24, 1)
        self.screen_on = 1
        self.usersettings.change_setting_value("screen_on", 1)

    def show(self, position="default", back_pointer_location=False):
        if self.screen_on == 0:
            return False

        if position == "default" and self.currentlocation:
            position = self.currentlocation
            refresh = 1
        elif position == "default" and not self.currentlocation:
            position = "menu"
            refresh = 1
        else:
            position = position.replace(" ", "_")
            self.currentlocation = position
            refresh = 0

        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((self.scale(2), self.scale(5)), position.replace("_", " "), fill=self.text_color, font=self.font)

        # getting list of items in current menu
        staffs = self.DOMTree.getElementsByTagName(position)
        text_margin_top = self.scale(15)
        i = 0
        list_count = len(staffs)
        list_count -= 1

        if self.pointer_position > 9:
            menu_offset = self.pointer_position - 9
        else:
            menu_offset = -1

        # looping through menu list
        for staff in staffs:
            self.pointer_position = clamp(self.pointer_position, 0, list_count)
            # drawing little arrow to show there are more items above
            if self.pointer_position > 9 and i < menu_offset:
                self.draw.line(
                    [
                        (self.scale(119), self.scale(20)),
                        (self.scale(125), self.scale(20))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )
                self.draw.line(
                    [
                        (self.scale(119), self.scale(20)),
                        (self.scale(122), self.scale(17))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )
                self.draw.line(
                    [
                        (self.scale(119), self.scale(20)),
                        (self.scale(122), self.scale(17))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )
                i += 1
                continue

            sid = staff.getAttribute("text")

            if not back_pointer_location:
                if i == self.pointer_position:
                    try:
                        self.parent_menu = staff.parentNode.tagName
                    except:
                        self.parent_menu = "end"
                    self.draw.rectangle(
                        [
                            (0, text_margin_top),
                            (self.LCD.width, text_margin_top + self.scale(11))
                        ],
                        fill="Crimson"
                    )
                    self.draw.text((self.scale(3), text_margin_top), ">", fill=self.text_color, font=self.font)
                    self.current_choice = sid
            else:
                if sid == back_pointer_location:
                    try:
                        self.parent_menu = staff.parentNode.tagName
                    except:
                        self.parent_menu = "data"
                    self.draw.rectangle([(0, text_margin_top), (self.LCD.width, text_margin_top + self.scale(11))],
                                        fill="Crimson")
                    self.draw.text((self.scale(3), text_margin_top), ">", fill=self.text_color, font=self.font)
                    self.current_choice = sid
                    self.pointer_position = i
            # drawing little arrow to show there are more items below
            if i == 10 and self.pointer_position < list_count and list_count > 10:
                self.draw.line(
                    [
                        (self.scale(119), self.scale(120)),
                        (self.scale(125), self.scale(120))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )
                self.draw.line(
                    [
                        (self.scale(119), self.scale(120)),
                        (self.scale(122), self.scale(123))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )
                self.draw.line(
                    [
                        (self.scale(122), self.scale(123)),
                        (self.scale(125), self.scale(120))
                    ],
                    fill=self.text_color,
                    width=(self.scale(2))
                )

            # scrolling text if too long
            if self.pointer_position == i and len(sid) > 18:
                tobecontinued = ".."
                if refresh == 1:
                    try:
                        self.cut_count += 1
                    except:
                        self.cut_count = -6
                else:
                    cut = 0
                    self.cut_count = -6
                if self.cut_count > (len(sid) - 16):
                    # hold scrolling on end
                    if self.scroll_hold < 8:
                        self.cut_count -= 1
                        self.scroll_hold += 1
                        tobecontinued = ""
                    else:
                        self.cut_count = -6
                        self.scroll_hold = 0
                    cut = self.cut_count
                if self.cut_count >= 0:
                    cut = self.cut_count
                else:
                    cut = 0
            else:
                cut = 0
                tobecontinued = ""

            i += 1

            # diplaying screensaver status
            if self.currentlocation == "Content":
                sid_temp = sid.lower()
                sid_temp = sid_temp.replace(" ", "_")
                if str(self.screensaver_settings[sid_temp]) == "1":
                    sid_temp = " +"
                else:
                    sid_temp = " -"
                sid = sid + sid_temp
            self.draw.text((self.scale(10), text_margin_top), sid[cut:(18 + cut)] + tobecontinued, fill=self.text_color,
                           font=self.font)

            text_margin_top += self.scale(10)

        # displaying color example
        if self.currentlocation == "RGB":
            self.draw.text((self.scale(10), self.scale(70)), str(self.ledsettings.get_colors()), fill=self.text_color,
                           font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(self.ledsettings.get_colors()) + ")")

        if "RGB_Color" in self.currentlocation:
            self.draw.text((self.scale(10), self.scale(70)),
                           str(self.ledsettings.get_multicolors(self.currentlocation.replace('RGB_Color', ''))),
                           fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)], fill="rgb(" + str(
                self.ledsettings.get_multicolors(self.currentlocation.replace('RGB_Color', ''))) + ")")

        if "Backlight_Color" in self.currentlocation:
            self.draw.text((self.scale(10), self.scale(70)), str(self.ledsettings.get_backlight_colors()),
                           fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(self.ledsettings.get_backlight_colors()) + ")")

        if "Custom_RGB" in self.currentlocation:
            self.draw.text((self.scale(10), self.scale(70)), str(self.ledsettings.get_adjacent_colors()),
                           fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(self.ledsettings.get_adjacent_colors()) + ")")

        if "Multicolor" in self.currentlocation:
            try:
                self.draw.rectangle([(self.scale(115), self.scale(50)), (self.LCD.width, self.scale(80))],
                                    fill="rgb(" + str(
                                        self.ledsettings.get_multicolors(self.current_choice.replace('Color', ''))) + ")")
            except:
                pass

        if "Color_for_slow_speed" in self.currentlocation:
            red = self.ledsettings.speed_slowest["red"]
            green = self.ledsettings.speed_slowest["green"]
            blue = self.ledsettings.speed_slowest["blue"]
            self.draw.text((self.scale(10), self.scale(70)), str(red) + ", " + str(green) + ", " + str(blue),
                           fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(red) + ", " + str(green) + ", " + str(blue) + ")")

        if "Color_for_fast_speed" in self.currentlocation:
            red = self.ledsettings.speed_fastest["red"]
            green = self.ledsettings.speed_fastest["green"]
            blue = self.ledsettings.speed_fastest["blue"]
            self.draw.text((self.scale(10), self.scale(70)), str(red) + ", " + str(green) + ", " + str(blue),
                           fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(red) + ", " + str(green) + ", " + str(blue) + ")")

        if "Gradient_start" in self.currentlocation:
            red = self.ledsettings.gradient_start["red"]
            green = self.ledsettings.gradient_start["green"]
            blue = self.ledsettings.gradient_start["blue"]
            self.draw.text((self.scale(10), self.scale(70)), str(red) + ", " + str(green) + ", " + str(blue),
                           fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(red) + ", " + str(green) + ", " + str(blue) + ")")

        if "Gradient_end" in self.currentlocation:
            red = self.ledsettings.gradient_end["red"]
            green = self.ledsettings.gradient_end["green"]
            blue = self.ledsettings.gradient_end["blue"]
            self.draw.text((self.scale(10), self.scale(70)), str(red) + ", " + str(green) + ", " + str(blue),
                           fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(red) + ", " + str(green) + ", " + str(blue) + ")")

        if "Color_in_scale" in self.currentlocation:
            red = self.ledsettings.key_in_scale["red"]
            green = self.ledsettings.key_in_scale["green"]
            blue = self.ledsettings.key_in_scale["blue"]
            self.draw.text((self.scale(10), self.scale(70)), str(red) + ", " + str(green) + ", " + str(blue),
                           fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(red) + ", " + str(green) + ", " + str(blue) + ")")

        if "Color_not_in_scale" in self.currentlocation:
            red = self.ledsettings.key_not_in_scale["red"]
            green = self.ledsettings.key_not_in_scale["green"]
            blue = self.ledsettings.key_not_in_scale["blue"]
            self.draw.text((self.scale(10), self.scale(70)), str(red) + ", " + str(green) + ", " + str(blue),
                           fill=self.text_color, font=self.font)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(red) + ", " + str(green) + ", " + str(blue) + ")")

        # displaying rainbow offset value
        if self.current_choice == "Offset":
            self.draw.text((self.scale(10), self.scale(70)), str(self.ledsettings.rainbow_offset), fill=self.text_color,
                           font=self.font)

        if self.current_choice == "Scale":
            self.draw.text((self.scale(10), self.scale(70)), str(self.ledsettings.rainbow_scale) + "%",
                           fill=self.text_color,
                           font=self.font)

        if self.current_choice == "Timeshift":
            self.draw.text((self.scale(10), self.scale(70)), str(self.ledsettings.rainbow_timeshift),
                           fill=self.text_color,
                           font=self.font)

        # displaying brightness value
        if self.currentlocation == "Brightness":
            self.draw.text((self.scale(10), self.scale(35)), str(self.ledstrip.brightness_percent) + "%",
                           fill=self.text_color, font=self.font)
            miliamps = int(self.ledstrip.LED_COUNT) * (60 / (100 / float(self.ledstrip.brightness_percent)))
            amps = round(float(miliamps) / float(1000), 2)
            self.draw.text((self.scale(10), self.scale(50)), "Amps needed to " + "\n" + "power " + str(
                self.ledstrip.LED_COUNT) + " LEDS with " + "\n" + "white color: " + str(amps), fill=self.text_color,
                           font=self.font)

        if self.currentlocation == "Backlight_Brightness":
            self.draw.text((self.scale(10), self.scale(35)), str(self.ledsettings.backlight_brightness_percent) + "%",
                           fill=self.text_color, font=self.font)

        # displaying led count
        if self.currentlocation == "Led_count":
            self.draw.text((self.scale(10), self.scale(35)), str(self.ledstrip.led_number), fill=self.text_color,
                           font=self.font)

        # displaying shift
        if self.currentlocation == "Shift":
            self.draw.text((self.scale(10), self.scale(35)), str(self.ledstrip.shift), fill=self.text_color,
                           font=self.font)

        # displaying reverse
        if self.currentlocation == "Reverse":
            self.draw.text((self.scale(10), self.scale(35)), str(self.ledstrip.reverse), fill=self.text_color,
                           font=self.font)

        if "Key_range" in self.currentlocation:
            if self.current_choice == "Start":
                try:
                    self.draw.text((self.scale(10), self.scale(50)), str(
                        self.ledsettings.multicolor_range[int(self.currentlocation.replace('Key_range', '')) - 1][0]),
                                   fill=self.text_color, font=self.font)
                except:
                    pass
            else:
                self.draw.text((self.scale(10), self.scale(50)), str(
                    self.ledsettings.multicolor_range[int(self.currentlocation.replace('Key_range', '')) - 1][1]),
                               fill=self.text_color, font=self.font)

        # displaying screensaver settings
        if self.currentlocation == "Start_delay":
            self.draw.text((self.scale(10), self.scale(70)), str(self.screensaver_delay), fill=self.text_color,
                           font=self.font)

        if self.currentlocation == "Turn_off_screen_delay":
            self.draw.text((self.scale(10), self.scale(70)), str(self.screen_off_delay), fill=self.text_color,
                           font=self.font)

        if self.currentlocation == "Led_animation_delay":
            self.draw.text((self.scale(10), self.scale(70)), str(self.led_animation_delay), fill=self.text_color,
                           font=self.font)

        # displaying speed values
        if self.currentlocation == "Period":
            self.draw.text((self.scale(10), self.scale(70)), str(self.ledsettings.speed_period_in_seconds),
                           fill=self.text_color, font=self.font)

        if self.currentlocation == "Max_notes_in_period":
            self.draw.text((self.scale(10), self.scale(70)), str(self.ledsettings.speed_max_notes), fill=self.text_color,
                           font=self.font)

        # displaying scale key
        if self.currentlocation == "Scale_Coloring":
            self.draw.text((self.scale(10), self.scale(70)), "scale: " + str(
                self.ledsettings.scales[self.ledsettings.scale_key]),
                           fill=self.text_color, font=self.font)

        # Learn MIDI
        if self.currentlocation == "Learn_MIDI":
            #  Position 1: display Load song
            self.draw.text((self.scale(90), self.scale(5 + 10)), str(self.learning.loadingList[self.learning.loading]),
                           fill=self.text_color, font=self.font)
            #  Position 2: display Learning Start/Stop
            self.draw.text((self.scale(90), self.scale(5 + 20)), str(
                self.learning.learningList[self.learning.is_started_midi]),
                           fill=self.text_color, font=self.font)
            #  Position 3: display Practice
            self.draw.text((self.scale(90), self.scale(5 + 30)), str(
                self.learning.practiceList[self.learning.practice]),
                           fill=self.text_color, font=self.font)
            #  Position 4: display Hands
            self.draw.text((self.scale(90), self.scale(5 + 40)), str(self.learning.handsList[self.learning.hands]),
                           fill=self.text_color, font=self.font)
            #  Position 5: display Mute hand
            self.draw.text((self.scale(90), self.scale(5 + 50)), str(
                self.learning.mute_handList[self.learning.mute_hand]),
                           fill=self.text_color, font=self.font)
            #  Position 6: display Start point
            self.draw.text((self.scale(90), self.scale(5 + 60)), str(self.learning.start_point) + "%",
                           fill=self.text_color,
                           font=self.font)
            #  Position 7: display End point
            self.draw.text((self.scale(90), self.scale(5 + 70)), str(self.learning.end_point) + "%",
                           fill=self.text_color,
                           font=self.font)
            #  Position 8: display Set tempo
            self.draw.text((self.scale(90), self.scale(5 + 80)), str(self.learning.set_tempo) + "%",
                           fill=self.text_color,
                           font=self.font)
            #  Position 9,10: display Hands colors
            coordR = 7 + 90
            coordL = 7 + 100
            self.draw.rectangle([(self.scale(90), self.scale(coordR)), (self.LCD.width, self.scale(coordR + 7))],
                                fill="rgb(" + str(self.learning.hand_colorList[self.learning.hand_colorR])[1:-1] + ")")
            self.draw.rectangle([(self.scale(90), self.scale(coordL)), (self.LCD.width, self.scale(coordL + 7))],
                                fill="rgb(" + str(self.learning.hand_colorList[self.learning.hand_colorL])[1:-1] + ")")

        self.LCD.LCD_ShowImage(self.image, 0, 0)

    def change_pointer(self, direction):
        if direction == 0:
            self.pointer_position -= 1
        elif direction == 1:
            self.pointer_position += 1
        self.cut_count = -6
        self.show()

    def enter_menu(self):
        position = self.current_choice.replace(" ", "_")

        if not self.DOMTree.getElementsByTagName(position):
            self.change_settings(self.current_choice, self.currentlocation)
        else:
            self.currentlocation = self.current_choice
            self.pointer_position = 0
            self.cut_count = -6
            self.show(self.current_choice)

    def go_back(self):
        if self.parent_menu != "data":
            location_readable = self.currentlocation.replace("_", " ")
            self.cut_count = -6
            self.show(self.parent_menu, location_readable)

    def render_message(self, title, message, delay=500):
        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((self.scale(3), self.scale(55)), title, fill=self.text_color, font=self.font)
        self.draw.text((self.scale(3), self.scale(65)), message, fill=self.text_color, font=self.font)
        self.LCD.LCD_ShowImage(self.image, 0, 0)
        LCD_Config.Driver_Delay_ms(delay)

    def render_screensaver(self, hour, date, cpu, cpu_average, ram, temp, cpu_history=[], upload=0, download=0,
                           card_space=0, local_ip="0.0.0.0"):
        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)

        total_height = self.scale(1)
        info_count = 0
        height_left = 1
        for key, value in self.screensaver_settings.items():
            if str(key) == "time" and str(value) == "1":
                total_height += self.scale(31)
            elif str(key) == "date" and str(value) == "1":
                total_height += self.scale(13)
            elif str(key) == "cpu_chart" and str(value) == "1":
                total_height += self.scale(35)
            else:
                if str(value) == "1":
                    info_count += 1

            height_left = self.LCD.height - total_height

        if info_count > 0:
            info_height_font = height_left / info_count
        else:
            info_height_font = 0

        top_offset = self.scale(2)

        if self.screensaver_settings["time"] == "1":
            fonthour = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSansBold.ttf', self.scale(31))
            self.draw.text((self.scale(4), top_offset), hour, fill=self.text_color, font=fonthour)
            top_offset += self.scale(31)

        if self.screensaver_settings["date"] == "1":
            font_date = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSansBold.ttf', self.scale(13))
            self.draw.text((self.scale(34), top_offset), date, fill=self.text_color, font=font_date)
            top_offset += self.scale(13)

        if self.screensaver_settings["cpu_chart"] == "1":
            previous_height = 0
            c = self.scale(-5)
            for cpu_chart in cpu_history:
                height = self.scale(((100 - cpu_chart) * 35) / float(100))
                self.draw.line([(c, top_offset + previous_height), (c + self.scale(5), top_offset + height)],
                               fill="Red", width=self.scale(1))
                previous_height = height
                c += self.scale(5)
            top_offset += self.scale(35)

        if info_height_font > self.scale(12):
            info_height_font = self.scale(12)

        font = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSansBold.ttf', int(info_height_font))

        if self.screensaver_settings["cpu"] == "1":
            self.draw.text((self.scale(1), top_offset), "CPU: " + str(cpu) + "% (" + str(cpu_average) + "%)",
                           fill=self.text_color, font=font)
            top_offset += info_height_font

        if self.screensaver_settings["ram"] == "1":
            self.draw.text((self.scale(1), top_offset), "RAM usage: " + str(ram) + "%", fill=self.text_color, font=font)
            top_offset += info_height_font

        if self.screensaver_settings["temp"] == "1":
            self.draw.text((self.scale(1), top_offset), "Temp: " + str(temp) + " C", fill=self.text_color, font=font)
            top_offset += info_height_font

        if self.screensaver_settings["network_usage"] == "1":
            if info_height_font > self.scale(11):
                info_height_font_network = self.scale(11)
            else:
                info_height_font_network = int(info_height_font)
            font_network = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
                                              int(info_height_font_network))
            self.draw.text((self.scale(1), top_offset),
                           "D:" + str("{:.2f}".format(download)) + "Mb/s U:" + str("{:.2f}".format(upload)) + "Mb/s",
                           fill=self.text_color, font=font_network)
            top_offset += info_height_font_network

        if self.screensaver_settings["sd_card_space"] == "1":
            self.draw.text((self.scale(1), top_offset),
                           "SD: " + str(round(card_space.used / (1024.0 ** 3), 1)) + "/" + str(
                               round(card_space.total / (1024.0 ** 3), 1)) + "(" + str(card_space.percent) + "%)",
                           fill=self.text_color, font=font)
            top_offset += info_height_font

        if self.screensaver_settings["local_ip"] == "1":
            self.draw.text((self.scale(1), top_offset), "IP: " + str(local_ip), fill=self.text_color, font=font)
            top_offset += info_height_font

        self.LCD.LCD_ShowImage(self.image, 0, 0)

    def change_settings(self, choice, location):
        if location == "Text_Color":
            self.text_color = choice
            self.usersettings.change_setting_value("text_color", self.text_color)
        if location == "Background_Color":
            self.background_color = choice
            self.usersettings.change_setting_value("background_color", self.background_color)
        if self.text_color == self.background_color:
            self.text_color = "Red"
            self.usersettings.change_setting_value("text_color", self.text_color)

        # Play MIDI
        if location == "Choose_song":
            self.saving.t = threading.Thread(target=play_midi, args=(choice, self.midiports, self.saving, self,
                                                                     self.ledsettings, self.ledstrip))
            self.saving.t.start()
        if location == "Play_MIDI":
            if choice == "Save MIDI":
                now = datetime.datetime.now()
                current_date = now.strftime("%Y-%m-%d %H:%M")
                self.render_message("Recording stopped", "Saved as " + current_date, 2000)
                self.saving.save(current_date)
                self.update_songs()
            if choice == "Start recording":
                self.render_message("Recording started", "", 2000)
                self.saving.start_recording()
            if choice == "Cancel recording":
                self.render_message("Recording canceled", "", 2000)
                self.saving.cancel_recording()
            if choice == "Stop playing":
                self.saving.is_playing_midi.clear()
                self.render_message("Playing stopped", "", 2000)
                fastColorWipe(self.ledstrip.strip, True, self.ledsettings)

        # Learn MIDI
        if location == "Load_song":
            self.learning.t = threading.Thread(target=self.learning.load_midi, args=(choice,))
            self.learning.t.start()
            self.go_back()
        if location == "Learn_MIDI":
            if choice == "Learning":
                if not self.learning.is_started_midi:
                    self.learning.t = threading.Thread(target=self.learning.learn_midi)
                    self.learning.t.start()
                else:
                    self.learning.is_started_midi = False
                    fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
                self.show(location)

        if location == "Solid":
            self.ledsettings.change_color_name(wc.name_to_rgb(choice))
            self.ledsettings.color_mode = "Single"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)

        if location == "Fading":
            self.ledsettings.mode = "Fading"
            self.usersettings.change_setting_value("mode", self.ledsettings.mode)
            if choice == "Very fast":
                self.ledsettings.fadingspeed = 50
            elif choice == "Fast":
                self.ledsettings.fadingspeed = 40
            elif choice == "Medium":
                self.ledsettings.fadingspeed = 20
            elif choice == "Slow":
                self.ledsettings.fadingspeed = 10
            elif choice == "Very slow":
                self.ledsettings.fadingspeed = 2
            elif choice == "Instant":
                self.ledsettings.fadingspeed = 1000
            self.usersettings.change_setting_value("fadingspeed", self.ledsettings.fadingspeed)

        if location == "Velocity":
            self.ledsettings.mode = "Velocity"
            self.usersettings.change_setting_value("mode", self.ledsettings.mode)
            if choice == "Fast":
                self.ledsettings.fadingspeed = 10
            elif choice == "Medium":
                self.ledsettings.fadingspeed = 8
            elif choice == "Slow":
                self.ledsettings.fadingspeed = 6
            elif choice == "Very slow":
                self.ledsettings.fadingspeed = 3
            self.usersettings.change_setting_value("fadingspeed", self.ledsettings.fadingspeed)

        if location == "Light_mode":
            if choice == "Disabled":
                self.ledsettings.mode = "Disabled"
            else:
                self.ledsettings.mode = "Normal"
            self.usersettings.change_setting_value("mode", self.ledsettings.mode)
            fastColorWipe(self.ledstrip.strip, True, self.ledsettings)

        if location == "Input":
            self.midiports.change_port("inport", choice)
        if location == "Playback":
            self.midiports.change_port("playport", choice)

        if location == "Ports_Settings":
            if choice == "Refresh ports" or choice == "Input" or choice == "Playback":
                self.update_ports()

            if choice == "Reset Bluetooth service":
                self.render_message("Reseting BL service", "", 1000)
                os.system("sudo systemctl restart btmidi.service")

            if choice == "Connect ports":
                self.render_message("Connecting ports", "", 2000)
                call("sudo ruby /usr/local/bin/connectall.rb", shell=True)

            if choice == "Disconnect ports":
                self.render_message("Disconnecting ports", "", 1000)
                call("sudo aconnect -x", shell=True)

        if location == "LED_animations":
            if choice == "Theater Chase":
                self.t = threading.Thread(target=theaterChase, args=(self.ledstrip.strip, Color(127, 127, 127),
                                                                     self.ledsettings, self))
                self.t.start()
            if choice == "Theater Chase Rainbow":
                self.t = threading.Thread(target=theaterChaseRainbow, args=(self.ledstrip.strip, self.ledsettings,
                                                                            self, 5))
                self.t.start()
            if choice == "Sound of da police":
                self.t = threading.Thread(target=sound_of_da_police, args=(self.ledstrip.strip, self.ledsettings,
                                                                           self, 1))
                self.t.start()
            if choice == "Scanner":
                self.t = threading.Thread(target=scanner, args=(self.ledstrip.strip, self.ledsettings, self, 1))
                self.t.start()
            if choice == "Clear":
                fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
        if location == "Breathing":
            if choice == "Fast":
                self.t = threading.Thread(target=breathing, args=(self.ledstrip.strip, self.ledsettings, self, 5))
                self.t.start()
            if choice == "Medium":
                self.t = threading.Thread(target=breathing, args=(self.ledstrip.strip, self.ledsettings, self, 10))
                self.t.start()
            if choice == "Slow":
                self.t = threading.Thread(target=breathing, args=(self.ledstrip.strip, self.ledsettings, self, 25))
                self.t.start()
        if location == "Rainbow":
            if choice == "Fast":
                self.t = threading.Thread(target=rainbow, args=(self.ledstrip.strip, self.ledsettings, self, 2))
                self.t.start()
            if choice == "Medium":
                self.t = threading.Thread(target=rainbow, args=(self.ledstrip.strip, self.ledsettings, self, 20))
                self.t.start()
            if choice == "Slow":
                self.t = threading.Thread(target=rainbow, args=(self.ledstrip.strip, self.ledsettings, self, 50))
                self.t.start()
        if location == "Rainbow_Cycle":
            if choice == "Fast":
                self.t = threading.Thread(target=rainbowCycle, args=(self.ledstrip.strip, self.ledsettings, self, 1))
                self.t.start()
            if choice == "Medium":
                self.t = threading.Thread(target=rainbowCycle, args=(self.ledstrip.strip, self.ledsettings, self, 20))
                self.t.start()
            if choice == "Slow":
                self.t = threading.Thread(target=rainbowCycle, args=(self.ledstrip.strip, self.ledsettings, self, 50))
                self.t.start()

        if location == "LED_animations":
            if choice == "Stop animation":
                self.screensaver_is_running = False

        if location == "Other_Settings":
            if choice == "System Info":
                screensaver(self, self.midiports, self.saving, self.ledstrip)

        if location == "Rainbow_Colors":
            self.ledsettings.color_mode = "Rainbow"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)

        if choice == "Add Color":
            self.ledsettings.addcolor()

        if choice == "Delete":
            self.ledsettings.deletecolor(location.replace('Color', ''))

        if location == "Multicolor" and choice == "Confirm":
            self.ledsettings.color_mode = "Multicolor"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)

        if location == "Speed" and choice == "Confirm":
            self.ledsettings.color_mode = "Speed"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)

        if location == "Gradient" and choice == "Confirm":
            self.ledsettings.color_mode = "Gradient"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)

        if location == "Scale_Coloring" and choice == "Confirm":
            self.ledsettings.color_mode = "Scale"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)
            print("color mode set to Scale")

        if location == "Scale_key":
            self.ledsettings.scale_key = self.ledsettings.scales.index(choice)
            self.usersettings.change_setting_value("scale_key", self.ledsettings.scale_key)

        if location == "Sequences":
            if choice == "Update":
                refresh_result = self.update_sequence_list()
                if not refresh_result:
                    self.render_message("Something went wrong", "Make sure your sequence file is correct", 1500)
            else:
                self.ledsettings.set_sequence(self.pointer_position, 0)

        if location == "Sides_Color":
            if choice == "Custom RGB":
                self.ledsettings.adjacent_mode = "RGB"
            if choice == "Same as main":
                self.ledsettings.adjacent_mode = "Main"
            if choice == "Off":
                self.ledsettings.adjacent_mode = "Off"
            self.usersettings.change_setting_value("adjacent_mode", self.ledsettings.adjacent_mode)

        if location == "Reset_to_default_settings":
            if choice == "Confirm":
                self.usersettings.reset_to_default()
            else:
                self.go_back()

        if location == "Update_visualizer":
            if choice == "Confirm":
                self.render_message("Updating...", "reboot is required", 5000)
                call("sudo git reset --hard HEAD", shell=True)
                call("sudo git checkout .", shell=True)
                call("sudo git clean -fdx", shell=True)
                call("sudo git pull origin master", shell=True)
            self.go_back()

        if location == "Shutdown":
            if choice == "Confirm":
                self.render_message("", "Shutting down...", 5000)
                call("sudo shutdown -h now", shell=True)
            else:
                self.go_back()

        if location == "Reboot":
            if choice == "Confirm":
                self.render_message("", "Rebooting...", 5000)
                call("sudo reboot now", shell=True)
            else:
                self.go_back()

        if location == "Skipped_notes":
            self.ledsettings.skipped_notes = choice
            self.usersettings.change_setting_value("skipped_notes", self.ledsettings.skipped_notes)

        if location == "Content":
            self.toggle_screensaver_settings(choice)

        if location == "Led_animation":
            self.led_animation = choice
            self.usersettings.change_setting_value("led_animation", choice)

    def change_value(self, value):
        if value == "LEFT":
            value = -1
        elif value == "RIGHT":
            value = 1
        if self.currentlocation == "Brightness":
            self.ledstrip.change_brightness(value * self.speed_multiplier)

        if self.currentlocation == "Led_count":
            self.ledstrip.change_led_count(value)

        if self.currentlocation == "Shift":
            self.ledstrip.change_shift(value)

        if self.currentlocation == "Reverse":
            self.ledstrip.change_reverse(value)

        if self.currentlocation == "Backlight_Brightness":
            if self.current_choice == "Power":
                self.ledsettings.change_backlight_brightness(value * self.speed_multiplier)
        if self.currentlocation == "Backlight_Color":
            self.ledsettings.change_backlight_color(self.current_choice, value * self.speed_multiplier)

        if self.currentlocation == "Custom_RGB":
            self.ledsettings.change_adjacent_color(self.current_choice, value * self.speed_multiplier)

        if self.currentlocation == "RGB":
            self.ledsettings.change_color(self.current_choice, value * self.speed_multiplier)
            self.ledsettings.color_mode = "Single"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)

        if "RGB_Color" in self.currentlocation:
            self.ledsettings.change_multicolor(self.current_choice, self.currentlocation, value * self.speed_multiplier)

        if "Key_range" in self.currentlocation:
            self.ledsettings.change_multicolor_range(self.current_choice, self.currentlocation,
                                                     value * self.speed_multiplier)
            self.ledsettings.light_keys_in_range(self.currentlocation)

        if self.current_choice == "Offset":
            self.ledsettings.rainbow_offset = self.ledsettings.rainbow_offset + value * 5 * self.speed_multiplier
        if self.current_choice == "Scale":
            self.ledsettings.rainbow_scale = self.ledsettings.rainbow_scale + value * 5 * self.speed_multiplier
        if self.current_choice == "Timeshift":
            self.ledsettings.rainbow_timeshift = self.ledsettings.rainbow_timeshift + value * self.speed_multiplier

        if self.currentlocation == "Start_delay":
            self.screensaver_delay = int(self.screensaver_delay) + (value * self.speed_multiplier)
            if self.screensaver_delay < 0:
                self.screensaver_delay = 0
            self.usersettings.change_setting_value("screensaver_delay", self.screensaver_delay)

        if self.currentlocation == "Turn_off_screen_delay":
            self.screen_off_delay = int(self.screen_off_delay) + (value * self.speed_multiplier)
            if self.screen_off_delay < 0:
                self.screen_off_delay = 0
            self.usersettings.change_setting_value("screen_off_delay", self.screen_off_delay)

        if self.currentlocation == "Led_animation_delay":
            self.led_animation_delay = int(self.led_animation_delay) + (value * self.speed_multiplier)
            if self.led_animation_delay < 0:
                self.led_animation_delay = 0
            self.usersettings.change_setting_value("led_animation_delay", self.led_animation_delay)

        if self.currentlocation == "Color_for_slow_speed":
            self.ledsettings.speed_slowest[self.current_choice.lower()] += value * self.speed_multiplier
            if self.ledsettings.speed_slowest[self.current_choice.lower()] > 255:
                self.ledsettings.speed_slowest[self.current_choice.lower()] = 255
            if self.ledsettings.speed_slowest[self.current_choice.lower()] < 0:
                self.ledsettings.speed_slowest[self.current_choice.lower()] = 0
            self.usersettings.change_setting_value("speed_slowest_" + self.current_choice.lower(),
                                                   self.ledsettings.speed_slowest[self.current_choice.lower()])

        if self.currentlocation == "Color_for_fast_speed":
            self.ledsettings.speed_fastest[self.current_choice.lower()] += value * self.speed_multiplier
            if self.ledsettings.speed_fastest[self.current_choice.lower()] > 255:
                self.ledsettings.speed_fastest[self.current_choice.lower()] = 255
            if self.ledsettings.speed_fastest[self.current_choice.lower()] < 0:
                self.ledsettings.speed_fastest[self.current_choice.lower()] = 0
            self.usersettings.change_setting_value("speed_fastest_" + self.current_choice.lower(),
                                                   self.ledsettings.speed_fastest[self.current_choice.lower()])

        if self.currentlocation == "Period":
            self.ledsettings.speed_period_in_seconds += (value / float(10)) * self.speed_multiplier
            if self.ledsettings.speed_period_in_seconds < 0.1:
                self.ledsettings.speed_period_in_seconds = 0.1
            self.usersettings.change_setting_value("speed_period_in_seconds", self.ledsettings.speed_period_in_seconds)

        if self.currentlocation == "Max_notes_in_period":
            self.ledsettings.speed_max_notes += value * self.speed_multiplier
            if self.ledsettings.speed_max_notes < 2:
                self.ledsettings.speed_max_notes = 2
            self.usersettings.change_setting_value("speed_max_notes", self.ledsettings.speed_max_notes)

        if self.currentlocation == "Gradient_start":
            self.ledsettings.gradient_start[self.current_choice.lower()] += value * self.speed_multiplier
            if self.ledsettings.gradient_start[self.current_choice.lower()] > 255:
                self.ledsettings.gradient_start[self.current_choice.lower()] = 255
            if self.ledsettings.gradient_start[self.current_choice.lower()] < 0:
                self.ledsettings.gradient_start[self.current_choice.lower()] = 0
            self.usersettings.change_setting_value("gradient_start_" + self.current_choice.lower(),
                                                   self.ledsettings.gradient_start[self.current_choice.lower()])

        if self.currentlocation == "Gradient_end":
            self.ledsettings.gradient_end[self.current_choice.lower()] += value * self.speed_multiplier
            if self.ledsettings.gradient_end[self.current_choice.lower()] > 255:
                self.ledsettings.gradient_end[self.current_choice.lower()] = 255
            if self.ledsettings.gradient_end[self.current_choice.lower()] < 0:
                self.ledsettings.gradient_end[self.current_choice.lower()] = 0
            self.usersettings.change_setting_value("gradient_end_" + self.current_choice.lower(),
                                                   self.ledsettings.gradient_end[self.current_choice.lower()])

        if self.currentlocation == "Color_in_scale":
            self.ledsettings.key_in_scale[self.current_choice.lower()] += value * self.speed_multiplier
            if self.ledsettings.key_in_scale[self.current_choice.lower()] > 255:
                self.ledsettings.key_in_scale[self.current_choice.lower()] = 255
            if self.ledsettings.key_in_scale[self.current_choice.lower()] < 0:
                self.ledsettings.key_in_scale[self.current_choice.lower()] = 0
            self.usersettings.change_setting_value("key_in_scale_" + self.current_choice.lower(),
                                                   self.ledsettings.key_in_scale[self.current_choice.lower()])

        if self.currentlocation == "Color_not_in_scale":
            self.ledsettings.key_not_in_scale[self.current_choice.lower()] += value * self.speed_multiplier
            if self.ledsettings.key_not_in_scale[self.current_choice.lower()] > 255:
                self.ledsettings.key_not_in_scale[self.current_choice.lower()] = 255
            if self.ledsettings.key_not_in_scale[self.current_choice.lower()] < 0:
                self.ledsettings.key_not_in_scale[self.current_choice.lower()] = 0
            self.usersettings.change_setting_value("key_not_in_scale_" + self.current_choice.lower(),
                                                   self.ledsettings.key_not_in_scale[self.current_choice.lower()])

        # Learn MIDI
        if self.currentlocation == "Learn_MIDI":
            if self.current_choice == "Practice":
                self.learning.change_practice(value)
            if self.current_choice == "Hands":
                self.learning.change_hands(value)
            if self.current_choice == "Mute hand":
                self.learning.change_mute_hand(value)
            if self.current_choice == "Start point":
                self.learning.change_start_point(value)
            if self.current_choice == "End point":
                self.learning.change_end_point(value)
            if self.current_choice == "Set tempo":
                self.learning.change_set_tempo(value)
            if self.current_choice == "Hand color R":
                self.learning.change_hand_color(value, 'RIGHT')
            if self.current_choice == "Hand color L":
                self.learning.change_hand_color(value, 'LEFT')

        self.show()

    def speed_change(self):
        if self.speed_multiplier == 10:
            self.speed_multiplier = 1
        elif self.speed_multiplier == 1:
            self.speed_multiplier = 10