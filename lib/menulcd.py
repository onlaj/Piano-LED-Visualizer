import os
from subprocess import call
from xml.dom import minidom
import webcolors as wc
from PIL import ImageFont, Image, ImageDraw
import time
from lib import LCD_Config, LCD_1in44, LCD_1in3
from lib.functions import *
from lib.rpi_drivers import GPIO
import lib.colormaps as cmap
from lib.log_setup import logger


# ============================================================================
#                          🥖 UI Theme Configuration 🥖
# ============================================================================
class UITheme:
    """Centralized UI theme configuration"""
    def __init__(self, lcd_scale_func):
        self.scale = lcd_scale_func
        
        # Menu item styling
        self.item_gap = 5  # Vertical spacing between items
        self.item_padding_v = 5  # Vertical padding inside item box
        self.item_padding_h = 5  # Horizontal padding inside item box
        self.item_corner_radius = 15  # Rounded corner radius
        self.item_bg_color = (63, 63, 70)  # Grey background for items
        self.item_border_color = (63, 63, 70, 200)  # Border color RGBA
        self.item_border_width = 1  # Constant border width
        
        # Pointer (selection highlight)
        self.pointer_color = (14, 165, 233)  # Default: Blue-Like
        self.pointer_width = 1  # Constant outline thickness
        self.pointer_padding = 1  # Extra padding around item for pointer
        
        # Scrolling
        self.viewport_margin_top = 5  # Keep selection this far from top
        self.viewport_margin_bottom = 5  # Keep selection this far from bottom
        self.scroll_indicator_width = 3  # Width of scroll arrows
        
        # Title area
        self.title_height = 15  # Height reserved for title
        self.title_padding = 5
        self.title_width_percent = 90 # Percentage of screen width to use (1-100)
        self.menu_title_png = "webinterface/static/menu_title.png"  # Path to title image
        
        # Value display
        self.value_right_margin = 5  # Right margin for values
        self.value_gap = 5  # Gap between label and value


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
        self._font_cache = {}
        self._title_image_cache = {}
        
        font_dir = "/usr/share/fonts/truetype/freefont"
        if args.fontdir is not None:
            font_dir = args.fontdir
        self.lcd_ttf = os.path.join(font_dir, "FreeSansBold.ttf")
        if not os.path.exists(self.lcd_ttf):
            raise RuntimeError("Cannot locate font file: %s" % self.lcd_ttf)

        if args.display == '1in3':
            self.LCD = LCD_1in3.LCD()
            mono_bold = os.path.join(font_dir, 'FreeMonoBold.ttf')
            self.font = self._get_font_cached(mono_bold, self.scale(10))
            self.image = Image.open('webinterface/static/logo240_240.bmp')
        else:
            self.LCD = LCD_1in44.LCD()
            self.font = ImageFont.load_default()
            self.image = Image.open('webinterface/static/logo128_128.bmp')

        # Initialize UI theme
        self.theme = UITheme(self.scale)
        
        self.LCD.LCD_Init()
        self.LCD.LCD_ShowImage(self.rotate_image(self.image), 0, 0)
        self.DOMTree = minidom.parse(xml_file_name)
        self.current_location = "menu"
        self.scroll_hold = 0
        self.cut_count = 0
        self.pointer_position = 0
        self.scroll_offset = 0  # New: track scroll position
        
        self.background_color = usersettings.get_setting_value("background_color")
        self.text_color = usersettings.get_setting_value("text_color")
        
        # Load pointer color from settings
        pointer_color_str = None
        try:
            pointer_color_str = usersettings.get_setting_value("pointer_color")
        except Exception as e:
            logger.debug(f"pointer_color not found in settings; using default {self.theme.pointer_color}")

        if pointer_color_str:
            self.theme.pointer_color = self._parse_color(pointer_color_str)

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
        self.idle_timeout_minutes = usersettings.get_setting_value("idle_timeout_minutes")
        self.led_animation = usersettings.get_setting_value("led_animation")
        self.screen_on = int(usersettings.get_setting_value("screen_on"))
        self.screen_status = 1
        self.screensaver_is_running = False
        self.last_activity = time.time()
        self.is_idle_animation_running = False
        self.is_animation_running = False
        
        # Load menu title image
        self.menu_title_image = None
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            candidates = [
                getattr(self.theme, "menu_title_png", None),                         # theme override
                os.path.join("webinterface", "static", "menu_title.png"),            # relative default
                os.path.join(base_path, "webinterface", "static", "menu_title.png"), # absolute default
            ]
            for p in candidates:
                if not p:
                    continue
                path = p if os.path.isabs(p) else os.path.join(base_path, p)
                if os.path.exists(path):
                    # Force RGBA to keep transparency
                    self.menu_title_image = Image.open(path).convert("RGBA")
                    logger.debug(f"Menu title PNG loaded: {path}")
                    break
            if self.menu_title_image is None:
                logger.debug("Menu title PNG not found (no JPG fallback by design).")
        except Exception as e:
            self.menu_title_image = None
            logger.debug(f"Failed to load menu title PNG: {e}")


    def _parse_color(self, color_str):
            """Parse 'R,G,B', '#RRGGBB', color names, or 'Default Grey'. Fallback to #27272a."""
            DEFAULT_GREY = (39, 39, 42)  # #27272a
            if color_str is None:
                return DEFAULT_GREY

            if not isinstance(color_str, str):
                color_str = str(color_str)
            s = color_str.strip()
            low = s.lower()

            # Handle "Default Grey/Gray" tokens
            if any(x in low for x in ("default grey", "default gray", "defaultgrey", "defaultgray")):
                return DEFAULT_GREY

            # Hex (#RRGGBB)
            if s.startswith("#") and len(s.lstrip("#")) == 6:
                h = s.lstrip("#")
                try:
                    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                except Exception:
                    pass

            # "R,G,B"
            if "," in s:
                try:
                    parts = [int(x.strip()) for x in s.split(",")]
                    if len(parts) >= 3:
                        r, g, b = [max(0, min(255, v)) for v in parts[:3]]
                        return (r, g, b)
                except Exception:
                    pass

            # Named colors (via webcolors), with simple grey fallback
            try:
                from webcolors import name_to_rgb
                rgb = name_to_rgb(low)
                return (rgb.red, rgb.green, rgb.blue)
            except Exception:
                if low in ("grey", "gray"):
                    return (128, 128, 128)
            return DEFAULT_GREY

    def _color_to_string(self, color):
        """Convert RGB tuple to string for storage"""
        return f"{color[0]},{color[1]},{color[2]}"

    def _get_font_cached(self, path, size):
        """Load and cache TrueType fonts keyed by (path, size)."""
        if not path or not os.path.exists(path):
            return ImageFont.load_default()
        try:
            size_int = max(1, int(round(size)))
        except (TypeError, ValueError):
            size_int = 1
        cache_key = (path, size_int)
        font = self._font_cache.get(cache_key)
        if font is None:
            try:
                font = ImageFont.truetype(path, size_int)
            except Exception as exc:
                logger.debug(f"Falling back to default font for {path} ({exc})")
                font = ImageFont.load_default()
            self._font_cache[cache_key] = font
        return font

    @staticmethod
    def _split_color_components(color_str):
        """Return at least three components (as strings) from a comma-separated RGB string."""
        if color_str is None:
            return ["0", "0", "0"]
        parts = [p.strip() for p in str(color_str).split(",")]
        if len(parts) < 3:
            parts.extend(["0"] * (3 - len(parts)))
        return parts[:3]

    def _get_menu_title_art(self):
        """Return a cached, resized version of the menu title art if available."""
        if not self.menu_title_image:
            return None
        width_percent = getattr(self.theme, "title_width_percent", 80)
        width_percent = max(1, min(100, int(width_percent)))
        max_height = max(1, self.scale(25))
        cache_key = (width_percent, self.LCD.width, max_height)
        cached = self._title_image_cache.get(cache_key)
        if cached is not None:
            return cached
        img_w, img_h = self.menu_title_image.size
        if img_w == 0 or img_h == 0:
            return None
        new_w = max(1, int(self.LCD.width * (width_percent / 100.0)))
        ratio = img_h / float(img_w)
        new_h = max(1, int(round(new_w * ratio)))
        if new_h > max_height:
            new_h = max_height
        try:
            resample_attr = getattr(Image, "Resampling", None)
            if resample_attr is not None:
                resized = self.menu_title_image.resize((new_w, new_h), resample_attr.LANCZOS)
            else:
                resized = self.menu_title_image.resize((new_w, new_h))
        except Exception as exc:
            logger.debug(f"Failed to resize menu title art: {exc}")
            return None
        self._title_image_cache[cache_key] = resized
        return resized

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

    def _draw_rounded_rect(self, xy, radius, fill=None, outline=None, width=1):
        """Draw an anti-aliased rounded rectangle (fill + optional outline)."""

        """Draw a rounded rectangle with anti-aliasing and complete outline"""
        x0, y0, x1, y1 = xy
        
        # Add padding for the outline to prevent clipping
        padding = width + 1
        img_w = int(x1 - x0 + padding * 2)
        img_h = int(y1 - y0 + padding * 2)
        
        # Create a temporary image with padding for anti-aliasing
        temp_img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Draw with offset to account for padding
        rect_coords = [(padding, padding), (img_w - padding, img_h - padding)]
        
        # Draw fill first if specified
        if fill:
            temp_draw.rounded_rectangle(rect_coords, radius=radius, fill=fill)
            
        # Draw outline separately to ensure it's complete
        if outline:
            temp_draw.rounded_rectangle(rect_coords, radius=radius, outline=outline, width=width)
        
        # Paste onto main image, adjusting position for padding
        self.image.paste(temp_img, (int(x0 - padding), int(y0 - padding)), temp_img)

    def _truncate_text(self, text, max_width, font):
        """Truncate text with ellipsis if it exceeds max_width"""
        if self.draw.textlength(text, font=font) <= max_width:
            return text
        
        ellipsis = "..."
        while text and self.draw.textlength(text + ellipsis, font=font) > max_width:
            text = text[:-1]
        return text + ellipsis

    def _draw_label_with_legacy_scroll(self, text, x, y, max_w, font, is_selected, refresh):
        """Legacy character-based scrolling (exactly like menulcd(old).py).
        Fixed 18-char window; only selected row scrolls; cut_count/scroll_hold; start delay -6; end hold 8 ticks.
        max_w is intentionally ignored to keep legacy behavior."""
        if text is None:
            return
        s = str(text)
        window_len = 18
        cut = 0
        to_be_continued = ""

        if is_selected and len(s) > window_len:
            to_be_continued = ".."
            if refresh == 1:
                try:
                    self.cut_count += 1
                except Exception:
                    self.cut_count = -6
            else:
                cut = 0
                self.cut_count = -6

            if self.cut_count > (len(s) - 16):
                if getattr(self, "scroll_hold", 0) < 8:
                    self.cut_count -= 1
                    self.scroll_hold = getattr(self, "scroll_hold", 0) + 1
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

        visible = s[cut:cut + window_len] + to_be_continued
        self.draw.text((int(x), int(y)), visible, fill=self.text_color, font=font)
    

    def _get_item_value(self, location, choice):
            """Get the display value for a menu item if it has an adjustable value"""
            value = None

            # Map locations to their corresponding values
            if location == "Brightness" and choice == "Power":
                value = f"{self.ledstrip.brightness_percent}%"

            elif location == "Backlight_Brightness" and choice == "Power":
                value = self.ledsettings.backlight_brightness_percent

            elif location == "Led_count":
                value = self.ledstrip.led_number

            elif location == "Leds_per_meter":
                value = self.ledstrip.leds_per_meter

            elif location == "Shift":
                value = self.ledstrip.shift

            elif location == "Reverse":
                value = self.ledstrip.reverse

            elif location == "Start_delay":
                value = self.screensaver_delay

            elif location == "Turn_off_screen_delay":
                value = self.screen_off_delay

            elif location == "Led_animation_delay":
                value = self.led_animation_delay

            elif location == "Idle_timeout":
                value = self.idle_timeout_minutes

            elif location == "Period":
                value = self.ledsettings.speed_period_in_seconds

            elif location == "Max_notes_in_period":
                value = self.ledsettings.speed_max_notes

            elif location == "Content":
                sid_temp = choice.lower().replace(" ", "_")
                value = "+" if str(self.screensaver_settings.get(sid_temp)) == "1" else "-"
        
            # --- Scale Coloring: show selected key name on the "Scale key" row ---
            elif location == "Scale_Coloring" and choice == "Scale key":
                try:
                    value = self.ledsettings.scales[self.ledsettings.scale_key]
                except Exception:
                    value = None

            # --- Key_rangeX: show Start/End values in their boxes ---
            elif location.startswith("Key_range"):
                idx_str = location.replace("Key_range", "")
                if idx_str.isdigit():
                    idx = int(idx_str) - 1  # ColorX -> 0-based
                    try:
                        start_val, end_val = self.ledsettings.multicolor_range[idx]
                        if choice == "Start":
                            value = start_val
                        elif choice == "End":
                            value = end_val
                    except Exception:
                        value = None

            # --- LED Note Offsets: show "LED Number" / "LED Offset" values ---
            elif location.startswith("Offset"):
                # location like "Offset0", "Offset1", ...
                idx_digits = "".join(ch for ch in location if ch.isdigit())
                if idx_digits:
                    idx = int(idx_digits)
                    try:
                        led_num, led_off = self.ledsettings.note_offsets[idx]
                        if choice == "LED Number":
                            value = led_num
                        elif choice == "LED Offset":
                            value = led_off
                    except Exception:
                        value = None

            # --- Rainbow_Colors: show Offset / Scale / Timeshift values ---
            elif location == "Rainbow_Colors":
                if choice == "Offset":
                    value = self.ledsettings.rainbow_offset
                elif choice == "Scale":
                    value = self.ledsettings.rainbow_scale
                elif choice == "Timeshift":
                    value = self.ledsettings.rainbow_timeshift

            # --- Velocity_Rainbow: show Offset / Scale / Curve values ---
            elif location == "Velocity_Rainbow":
                if choice == "Offset":
                    value = self.ledsettings.velocityrainbow_offset
                elif choice == "Scale":
                    value = self.ledsettings.velocityrainbow_scale
                elif choice == "Curve":
                    value = self.ledsettings.velocityrainbow_curve
        
            # RGB color values (existing logic)
            elif location == "RGB":
                color_str = self.ledsettings.get_colors()
                try:
                    r, g, b = [c.strip() for c in color_str.split(',')]
                except Exception:
                    r, g, b = "0", "0", "0"
                color_dict = {"Red": r, "Green": g, "Blue": b}
                value = color_dict.get(choice)
        
            elif "RGB_Color" in location:
                color_str = self.ledsettings.get_multicolors(location.replace('RGB_Color', ''))
                parts = [p.strip() for p in color_str.split(',')]
                while len(parts) < 3: parts.append("0")
                color_dict = {"Red": parts[0], "Green": parts[1], "Blue": parts[2]}
                value = color_dict.get(choice)
    

            elif location == "Backlight_Color":
                color_str = self.ledsettings.get_backlight_colors()
                parts = [p.strip() for p in color_str.split(',')]
                while len(parts) < 3: parts.append("0")
                color_dict = {"Red": parts[0], "Green": parts[1], "Blue": parts[2]}
                value = color_dict.get(choice)

            elif location == "Custom_RGB":
                color_str = self.ledsettings.get_adjacent_colors()
                parts = [p.strip() for p in color_str.split(',')]
                while len(parts) < 3: parts.append("0")
                color_dict = {"Red": parts[0], "Green": parts[1], "Blue": parts[2]}
                value = color_dict.get(choice)

            elif location == "Pointer_Color_RGB":
                r, g, b = self.theme.pointer_color
                color_dict = {"Red": str(r), "Green": str(g), "Blue": str(b)}
                value = color_dict.get(choice)
        
            elif location == "Color_for_slow_speed":
                color_dict = {
                    "Red": str(self.ledsettings.speed_slowest.get('red', 0)),
                    "Green": str(self.ledsettings.speed_slowest.get('green', 0)),
                    "Blue": str(self.ledsettings.speed_slowest.get('blue', 0)),
                }
                value = color_dict.get(choice)

            elif location == "Color_for_fast_speed":
                color_dict = {
                    "Red": str(self.ledsettings.speed_fastest.get('red', 0)),
                    "Green": str(self.ledsettings.speed_fastest.get('green', 0)),
                    "Blue": str(self.ledsettings.speed_fastest.get('blue', 0)),
                }
                value = color_dict.get(choice)
        
            elif location == "Gradient_start":
                color_dict = {
                    "Red": str(self.ledsettings.gradient_start.get('red', 0)),
                    "Green": str(self.ledsettings.gradient_start.get('green', 0)),
                    "Blue": str(self.ledsettings.gradient_start.get('blue', 0)),
                }
                value = color_dict.get(choice)
        
            elif location == "Gradient_end":
                color_dict = {
                    "Red": str(self.ledsettings.gradient_end.get('red', 0)),
                    "Green": str(self.ledsettings.gradient_end.get('green', 0)),
                    "Blue": str(self.ledsettings.gradient_end.get('blue', 0)),
                }
                value = color_dict.get(choice)

            elif location == "Color_in_scale":
                color_dict = {
                    "Red": str(self.ledsettings.key_in_scale.get('red', 0)),
                    "Green": str(self.ledsettings.key_in_scale.get('green', 0)),
                    "Blue": str(self.ledsettings.key_in_scale.get('blue', 0)),
                }
                value = color_dict.get(choice)

            elif location == "Color_not_in_scale":
                color_dict = {
                    "Red": str(self.ledsettings.key_not_in_scale.get('red', 0)),
                    "Green": str(self.ledsettings.key_not_in_scale.get('green', 0)),
                    "Blue": str(self.ledsettings.key_not_in_scale.get('blue', 0)),
                }
                value = color_dict.get(choice)

            elif location == "Learn_MIDI":
                learn_values = {
                    "Load song": self.learning.loadingList[self.learning.loading],
                    "Learning": self.learning.learningList[self.learning.is_started_midi],
                    "Practice": self.learning.practiceList[self.learning.practice],
                    "Hands": self.learning.handsList[self.learning.hands],
                    "Mute hand": self.learning.mute_handList[self.learning.mute_hand],
                    "Start point": f"{self.learning.start_point}%",
                    "End point": f"{self.learning.end_point}%",
                    "Hand color R": " ",
                    "Hand color L": " ",
                    "Set tempo": f"{self.learning.set_tempo}%",
                    "Wrong notes": "Enabled" if self.learning.show_wrong_notes else "Disabled",
                    "Future notes": "Enabled" if self.learning.show_future_notes else "Disabled",
                    "Max mistakes": self.learning.number_of_mistakes,
                }
                value = learn_values.get(choice)
            return str(value) if value is not None else None

    def show(self, position="default", back_pointer_location=None):
        selected_sid = None
        if self.screen_on == 0:
            return False
        
        if self.current_location in ("Velocity_Rainbow", "Rainbow_Colors"):
            self.update_colormap()

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
            self.scroll_offset = 0  # Reset scroll when entering new menu

        self.image = Image.new("RGB", (self.LCD.width, self.LCD.height), self.background_color)
        self.draw = ImageDraw.Draw(self.image)
        scale = self.scale
        theme = self.theme
        draw = self.draw
        lcd_width = self.LCD.width
        lcd_height = self.LCD.height
        # Extra: show estimated current draw under Brightness -> Power
        # displaying brightness value
        
        if self.current_location == "Brightness":

            # Compute the current draw
            miliamps = int(self.ledstrip.led_number) * (60 / (100 / float(self.ledstrip.brightness_percent)))
            amps = round(float(miliamps) / 1000.0, 2)

            # Render the text on three lines at (10, 50)
            draw.multiline_text(
                (10, 50),
                "Amps needed to\n"
                f"power {self.ledstrip.led_number} LEDS with\n"
                f"white color: {amps}",
                fill=self.text_color,
                font=self.font,
                spacing=scale(2)
            )


        # Draw title area (PNG in main menu only, text in submenus)
        title_y = scale(theme.title_padding)
        title_height_px = scale(theme.title_height)
        title_art = self._get_menu_title_art() if position == "menu" else None
        if title_art is not None:
            art_w, art_h = title_art.size
            x_pos = (lcd_width - art_w) // 2
            y_pos = title_y + (title_height_px - art_h) // 2
            if title_art.mode == 'RGBA':
                self.image.paste(title_art, (x_pos, y_pos), title_art)
            else:
                self.image.paste(title_art, (x_pos, y_pos))
        else:
            # Fallback to text
            title_text = position.replace("_", " ")
            draw.text((scale(5), title_y), title_text, fill=self.text_color, font=self.font)

        # Get menu items
        staffs = self.DOMTree.getElementsByTagName(position)
        self.list_count = len(staffs) - 1
        
        # Setup viewport dimensions
        content_start_y = scale(theme.title_height + theme.title_padding * 2)
        viewport_height_orig = lcd_height - content_start_y
        max_visible_items = 4
        # Set item dimensions
        item_height = scale(theme.item_padding_v * 2) + self.font.size
        total_item_height = item_height + scale(theme.item_gap)
        # Limit viewport height
        viewport_height = min(viewport_height_orig, total_item_height * max_visible_items)
        content_bottom = content_start_y + viewport_height
        margin_top_px = scale(theme.viewport_margin_top)
        margin_bottom_px = scale(theme.viewport_margin_bottom)
        padding_h_px = scale(theme.item_padding_h)
        padding_v_px = scale(theme.item_padding_v)
        pointer_padding_px = scale(theme.pointer_padding)
        pointer_radius_px = scale(theme.item_corner_radius)
        outer_margin_px = scale(5)
        label_value_spacing_px = scale(theme.item_padding_h * 2 + theme.value_gap)
        value_right_margin_px = scale(theme.value_right_margin)
        swatch_width_px = scale(30)
        swatch_gap_px = scale(6)
        learn_color_extra_px = scale(35)
        color_box_radius_px = scale(4)
         
        # Update scroll position for selection
        if back_pointer_location is None:
            self.pointer_position = clamp(self.pointer_position, 0, self.list_count)
            selected_item_y = self.pointer_position * total_item_height
            
            # Auto-scroll logic
            if selected_item_y < self.scroll_offset + margin_top_px:
                self.scroll_offset = max(0, selected_item_y - margin_top_px)
            elif selected_item_y + item_height > self.scroll_offset + viewport_height - margin_bottom_px:
                self.scroll_offset = selected_item_y + item_height - viewport_height + margin_bottom_px
        
        # Draw menu items
        current_y = int(round(content_start_y - self.scroll_offset))
        displayed_items = 0
        max_items = 4
        
        for i, staff in enumerate(staffs):
            sid = staff.getAttribute("text")
            
            # Check if this item is the selected one
            is_selected = False
            if back_pointer_location:
                if sid == back_pointer_location:
                    is_selected = True
                    self.pointer_position = i
                    try:
                        self.parent_menu = staff.parentNode.tagName
                    except:
                        self.parent_menu = "data"
            else:
                if i == self.pointer_position:
                    is_selected = True
                    self.current_choice = sid
                    try:
                        self.parent_menu = staff.parentNode.tagName
                    except:
                        self.parent_menu = "end"
            
            # Calculate item bounds
            item_x0 = outer_margin_px
            item_x1 = lcd_width - outer_margin_px
            item_y0 = current_y
            item_y1 = current_y + item_height
            
            # Calculate if the item would be fully visible
            is_fully_visible = (item_y0 >= content_start_y and 
                              item_y1 <= content_bottom and 
                              displayed_items < max_items)
            
            # Skip if item is not fully visible or we've reached max items
            if not is_fully_visible:
                current_y += total_item_height
                continue
            
            displayed_items += 1
            
            # Draw item background box
            self._draw_rounded_rect(
                (item_x0, item_y0, item_x1, item_y1),
                radius=pointer_radius_px,
                fill=theme.item_bg_color,
                outline=theme.item_border_color,
                width=1  # Constant width for crisp borders
            )
            
            # Draw selection highlight (outline only)
            if is_selected:
                selected_sid = sid
                pointer_x0 = item_x0 - pointer_padding_px
                pointer_y0 = item_y0 - pointer_padding_px
                pointer_x1 = item_x1 + pointer_padding_px
                pointer_y1 = item_y1 + pointer_padding_px
                
                self._draw_rounded_rect(
                    (pointer_x0, pointer_y0, pointer_x1, pointer_y1),
                    radius=pointer_radius_px,  # Same radius as item
                    fill=None,
                    outline=theme.pointer_color,
                    width=theme.pointer_width  # Use the configured pointer width
                )
            
            # Get value if applicable
            value_text = self._get_item_value(self.current_location, sid)
            
            # Calculate text areas
            text_x = item_x0 + padding_h_px
            text_y = item_y0 + padding_v_px
            
            # Handle special case for Learn MIDI hand colors first - always draw the color box
            if self.current_location == "Learn_MIDI" and sid in ["Hand color R", "Hand color L"]:
                # Calculate the color preview box dimensions and position first
                box_width = swatch_width_px
                box_height = item_y1 - item_y0 - swatch_gap_px  # Slightly smaller for better visual
                
                # Center the box vertically
                box_y = item_y0 + (item_y1 - item_y0 - box_height) // 2
                box_x = item_x1 - box_width - outer_margin_px  # outer margin from right edge
                
                # Draw the color preview box
                hand_idx = self.learning.hand_colorR if sid == "Hand color R" else self.learning.hand_colorL
                color = self.learning.hand_colorList[hand_idx]
                
                self._draw_rounded_rect(
                    (box_x, box_y, box_x + box_width, box_y + box_height),
                    radius=color_box_radius_px,
                    fill=f"rgb({color[0]}, {color[1]}, {color[2]})"
                )
            
            # Multicolor: one swatch per ColorX row (scroll/clip within the box)
            if self.current_location == "Multicolor":
                if sid.startswith("Color"):
                    idx = sid[5:]
                    if idx.isdigit():
                        color_str = self.ledsettings.get_multicolors(idx)

                        # Rounded-rectangle dimensions inside the box (right side)
                        swatch_w = swatch_width_px
                        swatch_h = (item_y1 - item_y0) - swatch_gap_px
                        swatch_x = item_x1 - swatch_w - outer_margin_px
                        swatch_y = item_y0 + ((item_y1 - item_y0) - swatch_h) // 2

                        self._draw_rounded_rect(
                            (swatch_x, swatch_y, swatch_x + swatch_w, swatch_y + swatch_h),
                            radius=color_box_radius_px,          # rounded rectangle
                            fill=f"rgb({color_str})"
                        )

            # Handle text display
            if value_text is not None:
                # Calculate space for value, accounting for color box in Learn MIDI menu
                value_width = draw.textlength(value_text, font=self.font)
                extra_space = learn_color_extra_px if self.current_location == "Learn_MIDI" and sid in ["Hand color R", "Hand color L"] else 0
                
                label_max_width = (item_x1 - item_x0 -
                                   label_value_spacing_px -
                                   value_width - extra_space)
                # Truncate label if needed
                label_text = self._truncate_text(sid, label_max_width, self.font)
                # Draw label
                self._draw_label_with_legacy_scroll(sid, text_x, text_y, label_max_width, self.font, is_selected, refresh)

                # Calculate value position, accounting for color box if needed
                value_right_margin = value_right_margin_px
                if self.current_location == "Learn_MIDI" and sid in ["Hand color R", "Hand color L"]:
                    value_right_margin += learn_color_extra_px  # Add space for color box
                value_x = item_x1 - value_right_margin - value_width
                draw.text((value_x, text_y), value_text, fill=self.text_color, font=self.font)
            else:
                # Just draw label centered vertically
                label_max_width = item_x1 - item_x0 - scale(theme.item_padding_h * 2)
                label_text = self._truncate_text(sid, label_max_width, self.font)
                self._draw_label_with_legacy_scroll(sid, text_x, text_y, label_max_width, self.font, is_selected, refresh)

            current_y += total_item_height
        # Update scroll_needed flag based on actually selected item (legacy rule >18 chars)
        try:
            if isinstance(selected_sid, str) and len(selected_sid) > 18 and self.screen_on == 1:
                self.scroll_needed = True
            else:
                self.scroll_needed = False
        except Exception:
            self.scroll_needed = False
        
        # Draw scroll indicators
        total_content_height = (self.list_count + 1) * total_item_height
        if total_content_height > viewport_height:
            # Draw up arrow for scrolling
            if self.scroll_offset > 0:
                arrow_x = lcd_width - scale(5)
                arrow_y = content_start_y - scale(8)
                # Left line
                draw.line(
                    [(arrow_x + scale(3), arrow_y + scale(3)), 
                     (arrow_x, arrow_y)],
                    fill=self.text_color, width=scale(2)
                )
                # Right line
                draw.line(
                    [(arrow_x, arrow_y), 
                     (arrow_x - scale(3), arrow_y + scale(3))],
                    fill=self.text_color, width=scale(2)
                )
            
            # Draw down arrow for scrolling
            if self.scroll_offset + viewport_height < total_content_height:
                arrow_x = lcd_width - scale(5)
                arrow_y = content_bottom
                # Left line
                draw.line(
                    [(arrow_x - scale(3), arrow_y - scale(3)), 
                     (arrow_x, arrow_y)],
                    fill=self.text_color, width=scale(2)
                )
                # Right line
                draw.line(
                    [(arrow_x, arrow_y), 
                     (arrow_x + scale(3), arrow_y - scale(3))],
                    fill=self.text_color, width=scale(2)
                )
        
        # Handle special displays (color previews, etc.)
        self._draw_special_displays()
        
        self.LCD.LCD_ShowImage(self.rotate_image(self.image), 0, 0)

    def update(self):
       self.show("default")

    def _draw_special_displays(self):
        """Draw bottom preview bars for color-related submenus."""

        scale = self.scale
        lcd_width = self.LCD.width
        lcd_height = self.LCD.height

        # Set preview dimensions
        preview_y = lcd_height - scale(25)  # Y position from bottom
        preview_height = scale(12)  # Height of preview box
        preview_bottom = preview_y + preview_height
        preview_left = scale(20)
        preview_right = lcd_width - scale(20)
        preview_box = (preview_left, preview_y, preview_right, preview_bottom)

        # RGB color preview
        if self.current_location == "RGB":
            color_str = self.ledsettings.get_colors()
            self._draw_rounded_rect(
                preview_box,
                radius=scale(6),
                fill=f"rgb({color_str})"
            )

        # Multicolor preview
        if "RGB_Color" in self.current_location:
            color_str = self.ledsettings.get_multicolors(self.current_location.replace('RGB_Color', ''))
            self._draw_rounded_rect(
                preview_box,
                radius=scale(6),
                fill=f"rgb({color_str})"
            )

        # Backlight color preview
        if "Backlight_Color" in self.current_location:
            color_str = self.ledsettings.get_backlight_colors()
            self._draw_rounded_rect(
                preview_box,
                radius=scale(6),
                fill=f"rgb({color_str})"
            )

        # Custom RGB preview
        if "Custom_RGB" in self.current_location:
            color_str = self.ledsettings.get_adjacent_colors()
            self._draw_rounded_rect(
                preview_box,
                radius=scale(6),
                fill=f"rgb({color_str})"
            )

        # Pointer Color RGB preview
        if self.current_location == "Pointer_Color_RGB":
            r, g, b = self.theme.pointer_color
            self._draw_rounded_rect(
                (self.scale(20), preview_y, self.LCD.width - self.scale(10), preview_bottom),
                radius=self.scale(6),
                fill=f"rgb({r}, {g}, {b})"
            )

        # Helper to draw small color previews for speed/gradient/etc.
        def draw_small_color_preview(color_dict):
            r, g, b = color_dict['red'], color_dict['green'], color_dict['blue']
            self._draw_rounded_rect(
                (self.scale(10), preview_y, self.LCD.width - self.scale(10), preview_bottom),
                radius=self.scale(8),
                fill=f"rgb({r}, {g}, {b})"
            )

        if "Color_for_slow_speed" in self.current_location:
            draw_small_color_preview(self.ledsettings.speed_slowest)
        elif "Color_for_fast_speed" in self.current_location:
            draw_small_color_preview(self.ledsettings.speed_fastest)
        elif "Gradient_start" in self.current_location:
            draw_small_color_preview(self.ledsettings.gradient_start)
        elif "Gradient_end" in self.current_location:
            draw_small_color_preview(self.ledsettings.gradient_end)
        elif "Color_in_scale" in self.current_location:
            draw_small_color_preview(self.ledsettings.key_in_scale)
        elif "Color_not_in_scale" in self.current_location:
            draw_small_color_preview(self.ledsettings.key_not_in_scale)


    def change_pointer(self, direction):
        self.last_activity = time.time()
        self.is_idle_animation_running = False
        
        if direction == 0:  # Up
            if self.pointer_position > 0:
                self.pointer_position -= 1
            else:
                self.pointer_position = self.list_count
        elif direction == 1:  # Down
            if self.pointer_position < self.list_count:
                self.pointer_position += 1
            else:
                self.pointer_position = 0
        
        self.cut_count = -6
        self.show()
    
    def page_up(self):
        """Move selection up by a page and refresh."""

        """Jump up by multiple items (PageUp functionality)"""
        self.last_activity = time.time()
        self.is_idle_animation_running = False
        
        page_size = 5  # Jump by 5 items
        self.pointer_position = max(0, self.pointer_position - page_size)
        self.show()
    
    def page_down(self):
        """Move selection down by a page and refresh."""

        """Jump down by multiple items (PageDown functionality)"""
        self.last_activity = time.time()
        self.is_idle_animation_running = False
        
        page_size = 5  # Jump by 5 items
        self.pointer_position = min(self.list_count, self.pointer_position + page_size)
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
            self.scroll_offset = 0
            self.cut_count = -6
            self.show(self.current_choice)

    def go_back(self):
        self.last_activity = time.time()
        self.is_idle_animation_running = False
        if self.parent_menu != "data":
            location_readable = self.current_location.replace("_", " ")
            self.cut_count = -6
            self.scroll_offset = 0
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
            font_network = ImageFont.truetype(self.lcd_ttf, int(info_height_font_network))
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
        # Pointer color setting
        if location == "Display_Settings" and choice == "Pointer Color":
            # This would open a submenu for pointer color selection
            # For now, we'll handle it in the existing color change mechanism
            pass
        
        if location == "Pointer_Color_RGB":
            # Handle RGB adjustment for pointer color
            pass
        
        # All existing change_settings logic remains the same...
        if location == "Text_Color":
            self.text_color = choice
            self.usersettings.change_setting_value("text_color", self.text_color)
        if location == "Background_Color":
            # Parse the color before assigning it
            parsed_color = self._parse_color(choice)
            # Convert to hex format for storage
            hex_color = "#{:02x}{:02x}{:02x}".format(*parsed_color)
            self.background_color = hex_color
            self.usersettings.change_setting_value("background_color", hex_color)
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
                self.t = threading.Thread(target=fireplace, args=(self.ledstrip, self.ledsettings, self))
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
        
        # Pointer color presets
        if location == "Presets":
            self.set_pointer_color(choice)

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

        if self.current_location == "Idle_timeout":
            self.idle_timeout_minutes = int(self.idle_timeout_minutes) + (value * self.speed_multiplier)
            if self.idle_timeout_minutes < 1:
                self.idle_timeout_minutes = 1
            self.usersettings.change_setting_value("idle_timeout_minutes", self.idle_timeout_minutes)

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

        # Pointer color adjustment
        if self.current_location == "Pointer_Color_RGB":
            r, g, b = self.theme.pointer_color
            if self.current_choice == "Red":
                r = clamp(r + value * self.speed_multiplier, 0, 255)
            elif self.current_choice == "Green":
                g = clamp(g + value * self.speed_multiplier, 0, 255)
            elif self.current_choice == "Blue":
                b = clamp(b + value * self.speed_multiplier, 0, 255)
            
            self.theme.pointer_color = (r, g, b)
            self.usersettings.change_setting_value("pointer_color", self._color_to_string(self.theme.pointer_color))

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
    
    def set_pointer_color(self, color):
        """Set selection outline color (RGB tuple, name, or hex)."""
        if isinstance(color, str) and color.strip().lower() in ("default blue", "default_blue", "defaultblue"):
            self.theme.pointer_color = (14, 165, 233)
        elif isinstance(color, (tuple, list)) and len(color) >= 3:
            r, g, b = color[:3]
            self.theme.pointer_color = (
                int(max(0, min(255, r))),
                int(max(0, min(255, g))),
                int(max(0, min(255, b))),
            )
        else:
            self.theme.pointer_color = self._parse_color(color)
        try:
            self.usersettings.change_setting_value("pointer_color", self._color_to_string(self.theme.pointer_color))
        except Exception as e:
            logger.debug(f"Could not persist pointer_color: {e}")
        self.show()  
        
    def get_pointer_color(self):
        """Get the current pointer color as RGB tuple"""
        return self.theme.pointer_color

