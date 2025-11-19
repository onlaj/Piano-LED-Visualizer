from rpi_ws281x import Color


class LEDEffectsProcessor:
    def __init__(self, ledstrip, ledsettings, menu, color_mode, last_sustain, pedal_deadzone):
        self.ledstrip = ledstrip
        self.ledsettings = ledsettings
        self.menu = menu
        self.color_mode = color_mode
        self.last_sustain = last_sustain
        self.pedal_deadzone = pedal_deadzone

    def process_fade_effects(self, event_loop_time):
        any_led_changed = False
        for n, strength in enumerate(self.ledstrip.keylist):
            if strength <= 0:
                continue

            if type(self.ledstrip.keylist_color[n]) is list:
                red = self.ledstrip.keylist_color[n][0]
                green = self.ledstrip.keylist_color[n][1]
                blue = self.ledstrip.keylist_color[n][2]
            else:
                red, green, blue = (0, 0, 0)

            led_changed = False
            new_color = self.color_mode.ColorUpdate(None, n, (red, green, blue))
            if new_color is not None:
                red, green, blue = new_color
                led_changed = True

            fading = 1

            if self.ledsettings.mode == "Velocity" or self.ledsettings.mode == "Pedal" or (
                    self.ledsettings.mode == "Fading" and self.ledstrip.keylist_status[n] == 0):
                fading = (strength / float(100)) / 10
                red = int(red * fading)
                green = int(green * fading)
                blue = int(blue * fading)

                decrease_amount = int((event_loop_time / float(self.ledsettings.fadingspeed / 1000)) * 1000)
                self.ledstrip.keylist[n] = max(0, self.ledstrip.keylist[n] - decrease_amount)
                led_changed = True

            if self.ledsettings.mode == "Velocity" or self.ledsettings.mode == "Pedal":
                # Check if key is pressed or sustained
                key_active = self.ledstrip.keylist_status[n] == 1 or self.ledstrip.keylist_sustained[n] == 1
                
                if int(self.last_sustain) >= self.pedal_deadzone and not key_active:
                    # Keep the lights on when the pedal is pressed and key was released
                    self.ledstrip.keylist[n] = 1000
                    led_changed = True
                elif int(self.last_sustain) < self.pedal_deadzone and self.ledstrip.keylist_status[n] == 0 and self.ledstrip.keylist_sustained[n] == 0:
                    # Turn off if pedal is not pressed and key is not active or sustained
                    self.ledstrip.keylist[n] = 0
                    red, green, blue = (0, 0, 0)
                    led_changed = True

            if self.ledstrip.keylist[n] <= 0 and self.menu.screensaver_is_running is not True:
                backlight_level = float(self.ledsettings.backlight_brightness_percent) / 100
                red = int(self.ledsettings.get_backlight_color("Red")) * backlight_level
                green = int(self.ledsettings.get_backlight_color("Green")) * backlight_level
                blue = int(self.ledsettings.get_backlight_color("Blue")) * backlight_level
                led_changed = True

            if led_changed:
                self.ledstrip.strip.setPixelColor(n, Color(int(red), int(green), int(blue)))
                self.ledstrip.set_adjacent_colors(n, Color(int(red), int(green), int(blue)), False, fading)
                any_led_changed = True
        return any_led_changed
