import time
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

                # Use mode-specific speed
                if self.ledsettings.mode == "Fading":
                    speed = self.ledsettings.fadingspeed
                elif self.ledsettings.mode == "Velocity":
                    speed = self.ledsettings.velocity_speed
                elif self.ledsettings.mode == "Pedal":
                    speed = self.ledsettings.pedal_speed
                else:
                    speed = self.ledsettings.fadingspeed

                decrease_amount = int((event_loop_time / float(speed / 1000)) * 1000)
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
        
        if self.ledsettings.mode == "Pulse":
            if self.process_pulse_effects():
                any_led_changed = True

        return any_led_changed

    def process_pulse_effects(self):
        if not self.ledstrip.active_pulses:
            return False

        import math

        current_time = time.perf_counter()
        pulses_to_remove = []
        leds_to_update = {}
        
        max_dist = self.ledsettings.pulse_animation_distance
        duration = self.ledsettings.pulse_animation_speed / 1000.0
        flicker_strength = self.ledsettings.pulse_flicker_strength / 100.0
        
        # Base background color (backlight) to blend on top of
        if not self.menu.screensaver_is_running:
            backlight_level = float(self.ledsettings.backlight_brightness_percent) / 100
            br = int(self.ledsettings.get_backlight_color("Red")) * backlight_level
            bg = int(self.ledsettings.get_backlight_color("Green")) * backlight_level
            bb = int(self.ledsettings.get_backlight_color("Blue")) * backlight_level
        else:
            br, bg, bb = 0, 0, 0

        for pulse in self.ledstrip.active_pulses:
            state = pulse.get("state", "attack")
            start_time = pulse["start_time"]
            velocity = pulse["velocity"]
            center = pulse["position"]
            p_r, p_g, p_b = pulse["color"]
            
            elapsed = current_time - start_time
            
            # Determine progress and effective radius
            
            # Attack/Expansion Phase
            # Always calculate outer radius based on time since start to keep it consistent
            attack_progress = elapsed / duration
            if attack_progress > 1.0: attack_progress = 1.0
            
            # Quadratic Ease-out for expansion
            ease_out_progress = attack_progress * (2 - attack_progress)
            current_outer_radius = ease_out_progress * max_dist
            
            # Determine inner radius (for release phase)
            current_inner_radius = 0.0
            
            if state == "release":
                release_time = pulse.get("release_time", current_time)
                release_elapsed = current_time - release_time
                release_progress = release_elapsed / duration
                
                if release_progress >= 1.0:
                    pulses_to_remove.append(pulse)
                    continue
                    
                # Linear expansion of the "hole"
                current_inner_radius = release_progress * max_dist
            
            # Flicker (Sustain Phase)
            # If fully expanded and not yet in release (or early release), add flicker
            current_intensity = velocity
            
            if attack_progress >= 1.0 and state != "release":
                # Sustain phase - apply flicker
                # Simple sine wave flicker
                v_val = (math.sin(current_time * self.ledsettings.pulse_flicker_speed) + 1) / 2  # 0 to 1
                # Modulate intensity down by strength
                current_intensity = velocity * (1.0 - (flicker_strength * v_val))
                
                # Update state to sustain if implicit transition
                if pulse.get("state") == "attack":
                     pulse["state"] = "sustain"
            
            # Determine range to update
            # We update the full max_dist range to ensure we clear previous frames' pixels
            start_led = max(0, int(center - max_dist - 2))
            end_led = min(self.ledstrip.led_number, int(center + max_dist + 3))
            
            for i in range(start_led, end_led):
                dist = abs(i - center)
                
                # Initialize with 0 (background will be added later) if not already visited
                if i not in leds_to_update:
                    leds_to_update[i] = [0, 0, 0]

                # Check if pixel is within the active band (inner < dist < outer)
                if dist < current_inner_radius or dist > current_outer_radius:
                    continue
                
                if current_outer_radius < 0.01:
                    dist_intensity = 1.0 if dist < 0.5 else 0
                else:
                    # Linear falloff from center to outer radius
                    dist_intensity = max(0.0, 1.0 - (dist / current_outer_radius))
                
                final_intensity = current_intensity * dist_intensity
                
                if final_intensity > 0.005:
                    leds_to_update[i][0] += p_r * final_intensity
                    leds_to_update[i][1] += p_g * final_intensity
                    leds_to_update[i][2] += p_b * final_intensity

        # Process "dying" pulses one last time to clear their area
        for pulse in pulses_to_remove:
             center = pulse["position"]
             start_led = max(0, int(center - max_dist - 2))
             end_led = min(self.ledstrip.led_number, int(center + max_dist + 3))
             
             for i in range(start_led, end_led):
                 if i not in leds_to_update:
                     leds_to_update[i] = [0, 0, 0]

        for i, color in leds_to_update.items():
            final_r = min(255, int(color[0] + br))
            final_g = min(255, int(color[1] + bg))
            final_b = min(255, int(color[2] + bb))
            
            self.ledstrip.strip.setPixelColor(i, Color(final_r, final_g, final_b))
            self.ledstrip.set_adjacent_colors(i, Color(final_r, final_g, final_b), False)

        for p in pulses_to_remove:
            if p in self.ledstrip.active_pulses:
                self.ledstrip.active_pulses.remove(p)

        return True
