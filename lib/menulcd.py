import os

from subprocess import call
from xml.dom import minidom

import webcolors as wc
from PIL import ImageFont, Image, ImageDraw

from lib import LCD_Config, LCD_1in44, LCD_1in3

from lib.functions import *
from lib.rpi_drivers import GPIO

import lib.colormaps as cmap
from lib.log_setup import logger


class MenuLCD:
    def __init__(self, xml_file_name, args, usersettings, ledsettings, ledstrip, learning, saving, midiports, hotspot, platform):
        self.list_count = None
        self.parent_menu = None
        self.current_choice = None
        self.draw = None
        self.t = None
        self.usersettings = usersettings
        self.ledsettings = ledsettings
        self.ledstrip = ledstrip
        self.learning = learning
        self.saving = saving
        self.midiports = midiports
        self.hotspot = hotspot
        self.platform = platform
        self.args = args
        font_dir = "/usr/share/fonts/truetype/freefont"
        if args.fontdir is not None:
            font_dir = args.fontdir
        self.lcd_ttf = font_dir + "/FreeSansBold.ttf"
        if not os.path.exists(self.lcd_ttf):
            raise RuntimeError("Cannot locate font file: %s" % self.lcd_ttf)

        if args.display == '1in3':
            self.LCD = LCD_1in3.LCD()
            self.font = ImageFont.truetype(font_dir + '/FreeMonoBold.ttf', self.scale(10))
            self.image = Image.open('webinterface/static/logo240_240.bmp')
        else:
            self.LCD = LCD_1in44.LCD()
            self.font = ImageFont.load_default()
            self.image = Image.open('webinterface/static/logo128_128.bmp')

        self.LCD.LCD_Init()
        self.LCD.LCD_ShowImage(self.rotate_image(self.image), 0, 0)
        self.DOMTree = minidom.parse(xml_file_name)
        self.current_location = "menu"
        self.scroll_hold = 0
        self.cut_count = 0
        self.pointer_position = 0
        self.background_color = usersettings.get_setting_value("background_color")
        self.text_color = usersettings.get_setting_value("text_color")
        self.update_songs()
        self.update_ports()
        self.update_led_note_offsets()
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

        self.screen_on = int(usersettings.get_setting_value("screen_on"))

        self.screen_status = 1

        self.screensaver_is_running = False
        self.last_activity = time.time()
        self.is_idle_animation_running = False
        self.is_animation_running = False

    def rotate_image(self, image):
        if self.args.rotatescreen != "true":
            return image
        else:
            return image.transpose(3)

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
        # Assume the first node is "Choose song"
        replace_node = self.DOMTree.getElementsByTagName("Play_MIDI")[0]
        choose_song_mc = self.DOMTree.createElement("Play_MIDI")
        choose_song_mc.appendChild(self.DOMTree.createTextNode(""))
        choose_song_mc.setAttribute("text", "Choose song")
        replace_node.parentNode.replaceChild(choose_song_mc, replace_node)
        # Assume the first node is "Load song"
        replace_node = self.DOMTree.getElementsByTagName("Learn_MIDI")[0]
        load_song_mc = self.DOMTree.createElement("Learn_MIDI")
        load_song_mc.appendChild(self.DOMTree.createTextNode(""))
        load_song_mc.setAttribute("text", "Load song")
        replace_node.parentNode.replaceChild(load_song_mc, replace_node)
        songs_list = os.listdir("Songs")
        for song in songs_list:
            # List of songs for Play_MIDI
            element = self.DOMTree.createElement("Choose_song")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", song)
            choose_song_mc.appendChild(element)
            # List of songs for Learn_MIDI
            element = self.DOMTree.createElement("Load_song")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", song)
            load_song_mc.appendChild(element)

    def update_colormap(self):
        # Assume the first node is "Velocity Colormap"
        replace_node = self.DOMTree.getElementsByTagName("Velocity_Rainbow")[0]
        velocity_colormap_mc = self.DOMTree.createElement("Velocity_Rainbow")
        velocity_colormap_mc.appendChild(self.DOMTree.createTextNode(""))
        velocity_colormap_mc.setAttribute("text", "Velocity Colormap")
        replace_node.parentNode.replaceChild(velocity_colormap_mc, replace_node)

        # Assume the first node is "Rainbow Colormap"
        replace_node = self.DOMTree.getElementsByTagName("Rainbow_Colors")[0]
        rainbow_colormap_mc = self.DOMTree.createElement("Rainbow_Colors")
        rainbow_colormap_mc.appendChild(self.DOMTree.createTextNode(""))
        rainbow_colormap_mc.setAttribute("text", "Rainbow Colormap")
        replace_node.parentNode.replaceChild(rainbow_colormap_mc, replace_node)

        # loop through cmap.colormaps_preview with a key
        for key, value in cmap.colormaps_preview.items():
            # List of colormaps for Rainbow colormap
            element = self.DOMTree.createElement("Rainbow_Colormap")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", key)
            rainbow_colormap_mc.appendChild(element)
            # List of colormaps for Velocity colormap
            element = self.DOMTree.createElement("Velocity_Colormap")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", key)
            velocity_colormap_mc.appendChild(element)

    def update_sequence_list(self):
        seq_mc = self.DOMTree.createElement("LED_Strip_Settings")
        seq_mc.appendChild(self.DOMTree.createTextNode(""))
        seq_mc.setAttribute("text", "Sequences")
        mc = self.DOMTree.getElementsByTagName("Sequences")[0]
        mc.parentNode.parentNode.replaceChild(seq_mc, mc.parentNode)
        ret = True
        try:
            sequences_tree = minidom.parse("config/sequences.xml")
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
                    seq_mc.appendChild(element)
                except:
                    break
        except:
            ret = False
        element = self.DOMTree.createElement("Sequences")
        element.appendChild(self.DOMTree.createTextNode(""))
        element.setAttribute("text", "Update")
        seq_mc.appendChild(element)
        return ret

    def update_ports(self):
        ports = list(dict.fromkeys(mido.get_input_names()))
        self.update_sequence_list()

        port_texts = ["Input", "Playback"]
        for index, port_text in enumerate(port_texts):
            element = self.DOMTree.createElement("Ports_Settings")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", port_text)
            mc = self.DOMTree.getElementsByTagName("Ports_Settings")[index]
            mc.parentNode.replaceChild(element, mc)

        for port in ports:
            for index, port_text in enumerate(port_texts):
                element = self.DOMTree.createElement(port_text)
                element.appendChild(self.DOMTree.createTextNode(""))
                element.setAttribute("text", port)
                mc = self.DOMTree.getElementsByTagName("Ports_Settings")[index]
                mc.appendChild(element)

    def update_led_note_offsets(self):
        note_offsets = self.ledsettings.note_offsets
        mc = self.DOMTree.getElementsByTagName("LED_Note_Offsets")[0]
        mc_note_offsets = self.DOMTree.createElement("LED_Strip_Settings")
        mc_note_offsets.appendChild(self.DOMTree.createTextNode(""))
        mc_note_offsets.setAttribute("text", "LED Note Offsets")
        parent = mc.parentNode.parentNode
        parent.replaceChild(mc_note_offsets, mc.parentNode)
        element = self.DOMTree.createElement("LED_Note_Offsets")
        element.appendChild(self.DOMTree.createTextNode(""))
        element.setAttribute("text", "Add Note Offset")
        mc_note_offsets.appendChild(element)
        i = 0
        for i, note_offset in enumerate(note_offsets):
            element = self.DOMTree.createElement("LED_Note_Offsets")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", "Offset%s" % i)
            mc_note_offsets.appendChild(element)
            op_element = self.DOMTree.createElement("Offset%s" % i)
            op_element.appendChild(self.DOMTree.createTextNode(""))
            op_element.setAttribute("text", "LED Number")
            element.appendChild(op_element)
            op_element = self.DOMTree.createElement("Offset%s" % i)
            op_element.appendChild(self.DOMTree.createTextNode(""))
            op_element.setAttribute("text", "LED Offset")
            element.appendChild(op_element)
            op_element = self.DOMTree.createElement("Offset%s" % i)
            op_element.appendChild(self.DOMTree.createTextNode(""))
            op_element.setAttribute("text", "Delete")
            element.appendChild(op_element)
        if i > 0:
            element = self.DOMTree.createElement("LED_Note_Offsets")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", "Append Note Offset")
            mc_note_offsets.appendChild(element)

    def update_multicolor(self, colors_list):
        i = 0
        self.update_ports()
        rgb_names = ["Red", "Green", "Blue"]
        mc = self.DOMTree.getElementsByTagName("Multicolor")[0]
        mc_multicolor = self.DOMTree.createElement("LED_Color")
        mc_multicolor.appendChild(self.DOMTree.createTextNode(""))
        mc_multicolor.setAttribute("text", "Multicolor")
        parent = mc.parentNode.parentNode
        parent.replaceChild(mc_multicolor, mc.parentNode)
        for color in colors_list:
            i = i + 1

            element = self.DOMTree.createElement("Multicolor")
            element.appendChild(self.DOMTree.createTextNode(""))
            element.setAttribute("text", "Color" + str(i))
            # mc = self.DOMTree.getElementsByTagName("LED_Color")[0]
            mc_multicolor.appendChild(element)

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

        # Create the "Cycle colors" element
        element = self.DOMTree.createElement("Multicolor")
        element.appendChild(self.DOMTree.createTextNode(""))
        element.setAttribute("text", "Cycle colors")

        enable_element = self.DOMTree.createElement("Cycle_colors")
        enable_element.appendChild(self.DOMTree.createTextNode(""))
        enable_element.setAttribute("text", "Enable")

        disable_element = self.DOMTree.createElement("Cycle_colors")
        disable_element.appendChild(self.DOMTree.createTextNode(""))
        disable_element.setAttribute("text", "Disable")

        element.appendChild(enable_element)
        element.appendChild(disable_element)

        mc_multicolor.appendChild(element)

        # Add in the "Add Color" and "Confirm" into the replaced child
        element = self.DOMTree.createElement("Multicolor")
        element.appendChild(self.DOMTree.createTextNode(""))
        element.setAttribute("text", "Add Color")
        mc_multicolor.appendChild(element)
        element = self.DOMTree.createElement("Multicolor")
        element.appendChild(self.DOMTree.createTextNode(""))
        element.setAttribute("text", "Confirm")
        mc_multicolor.appendChild(element)

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

    def show(self, position="default", back_pointer_location=None):

        def draw_value(value, x=10, y=35):
            if y < 0:
                return
            self.draw.text((self.scale(x), self.scale(y)), str(value),
                           fill=self.text_color, font=self.font)

        def draw_pointer():
            self.draw.rectangle(
                [
                    (0, text_margin_top),
                    (self.LCD.width, text_margin_top + self.scale(11))
                ],
                fill="Crimson"
            )
            self.draw.text((self.scale(3), text_margin_top), ">", fill=self.text_color, font=self.font)
            self.current_choice = sid

        if self.screen_on == 0:
            return False

        if position == "default" and self.current_location:
            position = self.current_location
            refresh = 1
        elif position == "default" and not self.current_location:
            position = "menu"
            refresh = 1
        else:
            position = position.replace(" ", "_")
            self.current_location = position
            refresh = 0

        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((self.scale(2), self.scale(5)), position.replace("_", " "), fill=self.text_color, font=self.font)

        # getting list of items in current menu
        staffs = self.DOMTree.getElementsByTagName(position)
        text_margin_top = self.scale(15)
        i = 0
        self.list_count = len(staffs)
        self.list_count -= 1

        if self.pointer_position > 9:
            menu_offset = self.pointer_position - 9
        else:
            menu_offset = -1

        # looping through menu list
        for staff in staffs:
            self.pointer_position = clamp(self.pointer_position, 0, self.list_count)
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
                    draw_pointer()
            else:
                if sid == back_pointer_location:
                    try:
                        self.parent_menu = staff.parentNode.tagName
                    except:
                        self.parent_menu = "data"
                    draw_pointer()
                    self.pointer_position = i
            # drawing little arrow to show there are more items below
            if i == 10 and self.pointer_position < self.list_count and self.list_count > 10:
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
                to_be_continued = ".."
                if refresh == 1:
                    try:
                        self.cut_count += 1
                    except AttributeError:
                        self.cut_count = -6
                else:
                    cut = 0
                    self.cut_count = -6
                if self.cut_count > (len(sid) - 16):
                    # hold scrolling on end
                    if self.scroll_hold < 8:
                        self.cut_count -= 1
                        self.scroll_hold += 1
                        to_be_continued = ""
                    else:
                        self.cut_count = -6
                        self.scroll_hold = 0
                    cut = self.cut_count
                else:
                    cut = self.cut_count if self.cut_count >= 0 else 0
            else:
                cut = 0
                to_be_continued = ""

            i += 1

            # displaying screensaver status
            if self.current_location == "Content":
                sid_temp = sid.lower()
                sid_temp = sid_temp.replace(" ", "_")
                if str(self.screensaver_settings[sid_temp]) == "1":
                    sid_temp = " +"
                else:
                    sid_temp = " -"
                sid = sid + sid_temp
            self.draw.text((self.scale(10), text_margin_top), sid[cut:(18 + cut)] + to_be_continued,
                           fill=self.text_color,
                           font=self.font)

            text_margin_top += self.scale(10)

        # displaying color example
        if self.current_location == "RGB":
            draw_value(self.ledsettings.get_colors(), 10, 70)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(self.ledsettings.get_colors()) + ")")

        if "RGB_Color" in self.current_location:
            draw_value(self.ledsettings.get_multicolors(self.current_location.replace('RGB_Color', '')), 10, 70)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)], fill="rgb(" + str(
                self.ledsettings.get_multicolors(self.current_location.replace('RGB_Color', ''))) + ")")

        if "Backlight_Color" in self.current_location:
            draw_value(self.ledsettings.get_backlight_colors(), 10, 70)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(self.ledsettings.get_backlight_colors()) + ")")

        if "Custom_RGB" in self.current_location:
            draw_value(self.ledsettings.get_adjacent_colors(), 10, 70)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(self.ledsettings.get_adjacent_colors()) + ")")

        if "Multicolor" in self.current_location:
            try:
                self.draw.rectangle([(self.scale(115), self.scale(50)), (self.LCD.width, self.scale(80))],
                                    fill="rgb(" + str(
                                        self.ledsettings.get_multicolors(
                                            self.current_choice.replace('Color', ''))) + ")")
            except:
                pass

        def draw_color_example(color_values):
            red, green, blue = color_values.values()
            draw_value(str(red) + ", " + str(green) + ", " + str(blue), 10, 70)
            self.draw.rectangle([(self.scale(0), self.scale(80)), (self.LCD.width, self.LCD.height)],
                                fill="rgb(" + str(red) + ", " + str(green) + ", " + str(blue) + ")")

        if "Color_for_slow_speed" in self.current_location:
            draw_color_example(self.ledsettings.speed_slowest)

        if "Color_for_fast_speed" in self.current_location:
            draw_color_example(self.ledsettings.speed_fastest)

        if "Gradient_start" in self.current_location:
            draw_color_example(self.ledsettings.gradient_start)

        if "Gradient_end" in self.current_location:
            draw_color_example(self.ledsettings.gradient_end)

        if "Color_in_scale" in self.current_location:
            draw_color_example(self.ledsettings.key_in_scale)

        if "Color_not_in_scale" in self.current_location:
            draw_color_example(self.ledsettings.key_not_in_scale)

        # displaying rainbow offset value
        rainbow_attribute_value = None

        if "Rainbow_Colors" in self.current_location:
            if self.current_choice == "Offset":
                rainbow_attribute_value = self.ledsettings.rainbow_offset
            elif self.current_choice == "Scale":
                rainbow_attribute_value = self.ledsettings.rainbow_scale
            elif self.current_choice == "Timeshift":
                rainbow_attribute_value = self.ledsettings.rainbow_timeshift

        elif "Velocity_Rainbow" in self.current_location:
            if self.current_choice == "Offset":
                rainbow_attribute_value = self.ledsettings.velocityrainbow_offset
            elif self.current_choice == "Scale":
                rainbow_attribute_value = self.ledsettings.velocityrainbow_scale
            elif self.current_choice == "Curve":
                rainbow_attribute_value = self.ledsettings.velocityrainbow_curve
        if rainbow_attribute_value is not None:
            self.draw.text((self.scale(10), self.scale(70)), str(rainbow_attribute_value), fill=self.text_color,
                           font=self.font)

        # displaying brightness value
        if self.current_location == "Brightness":
            draw_value(str(self.ledstrip.brightness_percent) + "%")
            miliamps = int(self.ledstrip.led_number) * (60 / (100 / float(self.ledstrip.brightness_percent)))
            amps = round(float(miliamps) / float(1000), 2)
            draw_value("Amps needed to " + "\n" + "power " + str(
                self.ledstrip.led_number) + " LEDS with " + "\n" + "white color: " + str(amps), 10, 50)

        if self.current_location == "Backlight_Brightness":
            draw_value(self.ledsettings.backlight_brightness_percent)

        # displaying led count
        if self.current_location == "Led_count":
            draw_value(self.ledstrip.led_number)

        # displaying leds per meter
        if self.current_location == "Leds_per_meter":
            draw_value(self.ledstrip.leds_per_meter)

        # displaying shift
        if self.current_location == "Shift":
            draw_value(self.ledstrip.shift)

        # displaying reverse
        if self.current_location == "Reverse":
            draw_value(self.ledstrip.reverse)

        if self.current_choice == "LED Number" and self.current_location.startswith("Offset"):
            try:
                draw_value(self.ledsettings.note_offsets[int(self.current_location.replace('Offset', '')) - 1][0], 10,
                           50)
            except:
                pass

        if self.current_choice == "LED Offset" and self.current_location.startswith("Offset"):
            try:
                draw_value(self.ledsettings.note_offsets[int(self.current_location.replace('Offset', '')) - 1][1], 10,
                           50)
            except:
                pass

        if "Key_range" in self.current_location:
            if self.current_choice == "Start":
                try:
                    draw_value(
                        self.ledsettings.multicolor_range[int(self.current_location.replace('Key_range', '')) - 1][0],
                        10, 50)
                except:
                    pass
            else:
                draw_value(
                    self.ledsettings.multicolor_range[int(self.current_location.replace('Key_range', '')) - 1][1], 10,
                    50)

        # displaying screensaver settings
        if self.current_location == "Start_delay":
            draw_value(self.screensaver_delay, 10, 70)

        if self.current_location == "Turn_off_screen_delay":
            draw_value(self.screen_off_delay, 10, 70)

        if self.current_location == "Led_animation_delay":
            draw_value(self.led_animation_delay, 10, 70)

        # displaying speed values
        if self.current_location == "Period":
            draw_value(self.ledsettings.speed_period_in_seconds, 10, 70)

        if self.current_location == "Max_notes_in_period":
            draw_value(self.ledsettings.speed_max_notes, 10, 70)

        # displaying scale key
        if self.current_location == "Scale_Coloring":
            draw_value("scale: " + str(self.ledsettings.scales[self.ledsettings.scale_key]), 10, 70)

        if self.current_location == "Velocity_Rainbow" or self.current_location == "Rainbow_Colors":
            self.update_colormap()

        # Learn MIDI
        if self.current_location == "Learn_MIDI":

            # calculate height so if self.pointer_position is 10 or more the height will be negative
            if self.pointer_position > 9:
                height = 95 - (self.pointer_position * 10)
            else:
                height = 5

            #  Position 1: display Load song
            draw_value(self.learning.loadingList[self.learning.loading], 90, height + 10)
            #  Position 2: display Learning Start/Stop
            draw_value(self.learning.learningList[self.learning.is_started_midi], 90, height + 20)
            #  Position 3: display Practice
            draw_value(self.learning.practiceList[self.learning.practice], 90, height + 30)
            #  Position 4: display Hands
            draw_value(self.learning.handsList[self.learning.hands], 90, height + 40)
            #  Position 5: display Mute hand
            draw_value(self.learning.mute_handList[self.learning.mute_hand], 90, height + 50)
            #  Position 6: display Start point
            draw_value(str(self.learning.start_point) + "%", 90, height + 60)
            #  Position 7: display End point
            draw_value(str(self.learning.end_point) + "%", 90, height + 70)
            #  Position 8: display Set tempo
            draw_value(str(self.learning.set_tempo) + "%", 90, height + 80)
            #  Position 9,10: display Hands colors
            coord_r = height + 2 + 90
            coord_l = height + 2 + 100
            self.draw.rectangle([(self.scale(90), self.scale(coord_r)), (self.LCD.width, self.scale(coord_r + 7))],
                                fill="rgb(" + str(self.learning.hand_colorList[self.learning.hand_colorR])[1:-1] + ")")
            self.draw.rectangle([(self.scale(90), self.scale(coord_l)), (self.LCD.width, self.scale(coord_l + 7))],
                                fill="rgb(" + str(self.learning.hand_colorList[self.learning.hand_colorL])[1:-1] + ")")
            #  Position 11: display wrong notes setting
            wrong_notes_status = "Enabled" if self.learning.show_wrong_notes else "Disabled"
            draw_value(wrong_notes_status, 90, height + 110)
            #  Position 12: display future notes setting
            future_notes_status = "Enabled" if self.learning.show_future_notes else "Disabled"
            draw_value(future_notes_status, 90, height + 120)
            #  Position 13: display number of mistakes setting
            draw_value(self.learning.number_of_mistakes, 90, height + 130)

        self.LCD.LCD_ShowImage(self.rotate_image(self.image), 0, 0)

    def change_pointer(self, direction):
        self.last_activity = time.time()
        self.is_idle_animation_running = False
        if direction == 0:
            if (self.pointer_position - 1) < 0:
                self.pointer_position = self.list_count
            else:
                self.pointer_position -= 1

        elif direction == 1:
            if (self.pointer_position + 1) > self.list_count:
                self.pointer_position = 0
            else:
                self.pointer_position += 1
        self.cut_count = -6
        self.show()

    def enter_menu(self):
        self.last_activity = time.time()
        self.is_idle_animation_running = False
        position = self.current_choice.replace(" ", "_")

        if not self.DOMTree.getElementsByTagName(position):
            self.change_settings(self.current_choice, self.current_location)
        else:
            self.current_location = self.current_choice
            self.pointer_position = 0
            self.cut_count = -6
            self.show(self.current_choice)

    def go_back(self):
        self.last_activity = time.time()
        self.is_idle_animation_running = False
        if self.parent_menu != "data":
            location_readable = self.current_location.replace("_", " ")
            self.cut_count = -6
            self.show(self.parent_menu, location_readable)

    def render_message(self, title, message, delay=500):
        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((self.scale(3), self.scale(55)), title, fill=self.text_color, font=self.font)
        self.draw.text((self.scale(3), self.scale(65)), str(message), fill=self.text_color, font=self.font)
        self.LCD.LCD_ShowImage(self.rotate_image(self.image), 0, 0)
        LCD_Config.Driver_Delay_ms(delay)

    def render_screensaver(self, hour, date, cpu, cpu_average, ram, temp, cpu_history=None, upload=0, download=0,
                           card_space=None, local_ip="0.0.0.0"):
        if cpu_history is None:
            cpu_history = []

        if card_space is None:
            card_space.used = 0
            card_space.total = 0
            card_space.percent = 0

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
            font_hour = ImageFont.truetype(self.lcd_ttf, self.scale(31))
            self.draw.text((self.scale(4), top_offset), hour, fill=self.text_color, font=font_hour)
            top_offset += self.scale(31)

        if self.screensaver_settings["date"] == "1":
            font_date = ImageFont.truetype(self.lcd_ttf, self.scale(13))
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

        font = ImageFont.truetype(self.lcd_ttf, int(info_height_font))

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
            font_network = ImageFont.truetype(self.lcd_ttf,
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

        self.LCD.LCD_ShowImage(self.rotate_image(self.image), 0, 0)

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

        mode_mapping = {
            "Fading": {
                "Very fast": 200,
                "Fast": 500,
                "Medium": 1000,
                "Slow": 2000,
                "Very slow": 4000,
                "Instant": 10
            },
            "Velocity": {
                "Fast": 1000,
                "Medium": 3000,
                "Slow": 4000,
                "Very slow": 6000
            },
            "Pedal": {
                "Fast": 1000,
                "Medium": 3000,
                "Slow": 4000,
                "Very slow": 6000
            }
        }

        if location in mode_mapping:
            self.ledsettings.mode = location
            self.usersettings.change_setting_value("mode", self.ledsettings.mode)
            if choice in mode_mapping[location]:
                self.ledsettings.fadingspeed = mode_mapping[location][choice]
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

            if choice == "Connect ports":
                self.render_message("Connecting ports", "", 2000)
                self.midiports.connectall()

            if choice == "Disconnect ports":
                self.render_message("Disconnecting ports", "", 1000)
                call("sudo aconnect -x", shell=True)

        if location == "LED_animations":
            self.is_animation_running = True
            if choice == "Theater Chase":
                self.t = threading.Thread(target=theaterChase, args=(self.ledstrip, self.ledsettings, self))
                self.t.start()
            if choice == "Theater Chase Rainbow":
                self.t = threading.Thread(target=theaterChaseRainbow, args=(self.ledstrip, self.ledsettings,
                                                                            self, "Medium"))
                self.t.start()
            if choice == "Fireplace":
                self.t = threading.Thread(target=fireplace, args=(self.ledstrip, self.ledsettings,
                                                                            self))
                self.t.start()
            if choice == "Sound of da police":
                self.t = threading.Thread(target=sound_of_da_police, args=(self.ledstrip, self.ledsettings,
                                                                           self, 1))
                self.t.start()
            if choice == "Scanner":
                self.t = threading.Thread(target=scanner, args=(self.ledstrip, self.ledsettings, self, 1))
                self.t.start()
            if choice == "Clear":
                fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
        if location == "Chords":
            chord = self.ledsettings.scales.index(choice)
            self.t = threading.Thread(target=chords, args=(chord, self.ledstrip, self.ledsettings, self))
            self.t.start()

        speed_map = {
            "Rainbow": {
                "Fast": rainbow,
                "Medium": rainbow,
                "Slow": rainbow
            },
            "Rainbow_Cycle": {
                "Fast": rainbowCycle,
                "Medium": rainbowCycle,
                "Slow": rainbowCycle
            },
            "Breathing": {
                "Fast": breathing,
                "Medium": breathing,
                "Slow": breathing
            }
        }

        if location in speed_map and choice in speed_map[location]:
            speed_func = speed_map[location][choice]
            self.t = threading.Thread(target=speed_func, args=(self.ledstrip, self.ledsettings, self, choice))
            self.t.start()

        if location == "LED_animations":
            if choice == "Stop animation":
                self.is_animation_running = False
                self.is_idle_animation_running = False

        if location == "Other_Settings":
            if choice == "System Info":
                screensaver(self, self.midiports, self.saving, self.ledstrip, self.ledsettings)

        if location == "Cycle_colors":
            choice = 1 if choice == "Enable" else 0
            self.usersettings.change_setting_value("multicolor_iteration", choice)
            self.ledsettings.multicolor_iteration = choice

        if choice == "Add Color":
            self.ledsettings.addcolor()

        if choice == "Add Note Offset":
            self.ledsettings.add_note_offset()
            self.update_led_note_offsets()
            self.show()

        if choice == "Append Note Offset":
            self.ledsettings.append_note_offset()
            self.update_led_note_offsets()
            self.show()

        if choice == "Delete":
            if location.startswith('Offset'):
                self.ledsettings.del_note_offset(location.replace('Offset', '').split('_')[0])
                self.update_led_note_offsets()
                self.go_back()
                self.show()
            else:
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

        if location == "Velocity_Rainbow" and choice == "Confirm":
            self.ledsettings.color_mode = "VelocityRainbow"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)

        if location == "Velocity_Colormap":
            self.ledsettings.velocityrainbow_colormap = choice
            self.usersettings.change_setting_value("velocityrainbow_colormap", self.ledsettings.velocityrainbow_colormap)

            self.ledsettings.color_mode = "VelocityRainbow"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)

        if location == "Rainbow_Colors" and choice == "Confirm":
            self.ledsettings.color_mode = "Rainbow"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)

        if location == "Rainbow_Colormap":
            self.ledsettings.rainbow_colormap = choice
            self.usersettings.change_setting_value("rainbow_colormap", self.ledsettings.rainbow_colormap)

            self.ledsettings.color_mode = "Rainbow"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)

        if location == "Scale_key":
            self.ledsettings.scale_key = self.ledsettings.scales.index(choice)
            self.usersettings.change_setting_value("scale_key", self.ledsettings.scale_key)

        if location == "Sequences":
            if choice == "Update":
                refresh_result = self.update_sequence_list()
                if not refresh_result:
                    self.render_message("Something went wrong", "Make sure your sequence file is correct", 1500)
                self.show()
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

        if location == "Restart_Visualizer":
            if choice == "Confirm":
                self.render_message("Restarting...", "", 500)
                self.platform.restart_visualizer()
            else:
                self.go_back()

        if location == "Start_Hotspot":
            if choice == "Confirm":
                self.usersettings.change_setting_value("is_hotspot_active", 1)
                self.render_message("Starting Hotspot...", "It might take a few minutes...", 2000)
                logger.info("Starting Hotspot...")
                time.sleep(2)
                self.platform.disconnect_from_wifi(self.hotspot, self.usersettings)
            else:
                self.go_back()

        if location == "Restart_RTPMidi_service":
            if choice == "Confirm":
                self.render_message("Restarting RTPMidi...", "", 2000)
                self.platform.restart_rtpmidid()
            else:
                self.go_back()

        if location == "Update_visualizer":
            if choice == "Confirm":
                self.render_message("Updating...", "reboot is required", 5000)
                self.platform.update_visualizer()
            self.go_back()

        if location == "Shutdown":
            if choice == "Confirm":
                self.render_message("", "Shutting down...", 5000)
                self.platform.shutdown()
            else:
                self.go_back()

        if location == "Reboot":
            if choice == "Confirm":
                self.render_message("", "Rebooting...", 5000)
                self.platform.reboot()
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
        if self.current_location == "Brightness":
            self.ledstrip.change_brightness(value * self.speed_multiplier)

        if self.current_location == "Led_count":
            self.ledstrip.change_led_count(value)

        if self.current_location == "Leds_per_meter":
            self.ledstrip.leds_per_meter = self.ledstrip.leds_per_meter + value

        if self.current_location == "Shift":
            self.ledstrip.change_shift(value)

        if self.current_location == "Reverse":
            self.ledstrip.change_reverse(value)

        if self.current_location == "Backlight_Brightness":
            if self.current_choice == "Power":
                self.ledsettings.change_backlight_brightness(value * self.speed_multiplier)
        if self.current_location == "Backlight_Color":
            self.ledsettings.change_backlight_color(self.current_choice, value * self.speed_multiplier)

        if self.current_location == "Custom_RGB":
            self.ledsettings.change_adjacent_color(self.current_choice, value * self.speed_multiplier)

        if self.current_location == "RGB":
            self.ledsettings.change_color(self.current_choice, value * self.speed_multiplier)
            self.ledsettings.color_mode = "Single"
            self.usersettings.change_setting_value("color_mode", self.ledsettings.color_mode)

        if "RGB_Color" in self.current_location:
            self.ledsettings.change_multicolor(self.current_choice, self.current_location,
                                               value * self.speed_multiplier)

        if "Key_range" in self.current_location:
            self.ledsettings.change_multicolor_range(self.current_choice, self.current_location,
                                                     value * self.speed_multiplier)
            self.ledsettings.light_keys_in_range(self.current_location)

        if self.current_choice == "LED Number" and self.current_location.startswith("Offset"):
            self.ledsettings.update_note_offset_lcd(self.current_choice, self.current_location,
                                                    value * self.speed_multiplier)
        if self.current_choice == "LED Offset" and self.current_location.startswith("Offset"):
            self.ledsettings.update_note_offset_lcd(self.current_choice, self.current_location,
                                                    value * self.speed_multiplier)

        if "Rainbow_Colors" in self.current_location:
            if self.current_choice == "Offset":
                self.ledsettings.rainbow_offset = self.ledsettings.rainbow_offset + value * 5 * self.speed_multiplier
            if self.current_choice == "Scale":
                self.ledsettings.rainbow_scale = self.ledsettings.rainbow_scale + value * 5 * self.speed_multiplier
            if self.current_choice == "Timeshift":
                self.ledsettings.rainbow_timeshift = self.ledsettings.rainbow_timeshift + value * self.speed_multiplier

        if "Velocity_Rainbow" in self.current_location:
            if self.current_choice == "Offset":
                self.ledsettings.velocityrainbow_offset = \
                    self.ledsettings.velocityrainbow_offset + value * 5 * self.speed_multiplier
            if self.current_choice == "Scale":
                self.ledsettings.velocityrainbow_scale = \
                    self.ledsettings.velocityrainbow_scale + value * 5 * self.speed_multiplier
            if self.current_choice == "Curve":
                self.ledsettings.velocityrainbow_curve = \
                    self.ledsettings.velocityrainbow_curve + value * self.speed_multiplier

        if self.current_location == "Start_delay":
            self.screensaver_delay = int(self.screensaver_delay) + (value * self.speed_multiplier)
            if self.screensaver_delay < 0:
                self.screensaver_delay = 0
            self.usersettings.change_setting_value("screensaver_delay", self.screensaver_delay)

        if self.current_location == "Turn_off_screen_delay":
            self.screen_off_delay = int(self.screen_off_delay) + (value * self.speed_multiplier)
            if self.screen_off_delay < 0:
                self.screen_off_delay = 0
            self.usersettings.change_setting_value("screen_off_delay", self.screen_off_delay)

        if self.current_location == "Led_animation_delay":
            self.led_animation_delay = int(self.led_animation_delay) + (value * self.speed_multiplier)
            if self.led_animation_delay < 0:
                self.led_animation_delay = 0
            self.usersettings.change_setting_value("led_animation_delay", self.led_animation_delay)

        if self.current_location == "Period":
            self.ledsettings.speed_period_in_seconds = round(self.ledsettings.speed_period_in_seconds + (value * .1) *
                                                             self.speed_multiplier, 1)
            if self.ledsettings.speed_period_in_seconds < 0.1:
                self.ledsettings.speed_period_in_seconds = 0.1
            self.usersettings.change_setting_value("speed_period_in_seconds", self.ledsettings.speed_period_in_seconds)

        if self.current_location == "Max_notes_in_period":
            self.ledsettings.speed_max_notes += value * self.speed_multiplier
            if self.ledsettings.speed_max_notes < 2:
                self.ledsettings.speed_max_notes = 2
            self.usersettings.change_setting_value("speed_max_notes", self.ledsettings.speed_max_notes)

        led_settings_map = {
            "Color_for_slow_speed": self.ledsettings.speed_slowest,
            "Color_for_fast_speed": self.ledsettings.speed_fastest,
            "Gradient_start": self.ledsettings.gradient_start,
            "Gradient_end": self.ledsettings.gradient_end,
            "Color_in_scale": self.ledsettings.key_in_scale,
            "Color_not_in_scale": self.ledsettings.key_not_in_scale
        }

        if self.current_location in led_settings_map:
            led_setting = led_settings_map[self.current_location]
            led_setting[self.current_choice.lower()] += value * self.speed_multiplier
            if led_setting[self.current_choice.lower()] > 255:
                led_setting[self.current_choice.lower()] = 255
            if led_setting[self.current_choice.lower()] < 0:
                led_setting[self.current_choice.lower()] = 0
            self.usersettings.change_setting_value(self.current_location.lower() + "_" + self.current_choice.lower(),
                                                   led_setting[self.current_choice.lower()])

        # Learn MIDI
        learning_operations = {
            "Practice": self.learning.change_practice,
            "Hands": self.learning.change_hands,
            "Mute hand": self.learning.change_mute_hand,
            "Start point": self.learning.change_start_point,
            "End point": self.learning.change_end_point,
            "Set tempo": self.learning.change_set_tempo,
            "Hand color R": lambda value: self.learning.change_hand_color(value, 'RIGHT'),
            "Hand color L": lambda value: self.learning.change_hand_color(value, 'LEFT')
        }

        if self.current_location == "Learn_MIDI" and self.current_choice in learning_operations:
            learning_operation = learning_operations[self.current_choice]
            learning_operation(value)

        # changing settings value for Wrong notes and Future notes
        if self.current_location == "Learn_MIDI":
            if self.current_choice == "Wrong notes":
                self.learning.change_show_wrong_notes(value)

            if self.current_choice == "Future notes":
                self.learning.change_show_future_notes(value)

            if self.current_choice == "Max mistakes":
                self.learning.change_number_of_mistakes(value)

        self.show()

    def speed_change(self):
        if self.speed_multiplier == 10:
            self.speed_multiplier = 1
        elif self.speed_multiplier == 1:
            self.speed_multiplier = 10
