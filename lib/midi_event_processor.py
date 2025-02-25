import time

from rpi_ws281x import Color

from lib.functions import get_note_position, find_between
from lib.log_setup import logger


class MIDIEventProcessor:
    def __init__(self, midiports, ledstrip, ledsettings, usersettings, saving, learning, menu, color_mode):
        self.midiports = midiports
        self.ledstrip = ledstrip
        self.ledsettings = ledsettings
        self.usersettings = usersettings
        self.saving = saving
        self.learning = learning
        self.menu = menu
        self.color_mode = color_mode
        self.last_sustain = 0  # Initialize last_sustain
        # Add a timestamp for the last sequence advance
        self.last_sequence_advance = 0

    def process_midi_events(self):
        if len(self.saving.is_playing_midi) == 0 and self.learning.is_started_midi is False:
            self.midiports.midipending = self.midiports.midi_queue
        else:
            self.midiports.midipending = self.midiports.midifile_queue

        while self.midiports.midipending:
            msg, msg_timestamp = self.midiports.midipending.popleft()

            if int(self.usersettings.get_setting_value("midi_logging")) == 1:
                if not msg.is_meta:
                    try:
                        self.learning.socket_send.append("midi_event" + str(msg))
                    except Exception as e:
                        logger.warning(f"[process midi events] Unexpected exception occurred: {e}")

            self.midiports.last_activity = time.time()

            if (msg.type == "note_off" or (
                    msg.type == "note_on" and msg.velocity == 0)) and self.ledsettings.mode != "Disabled":
                note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                if 0 <= note_position < self.ledstrip.led_number:
                    self.handle_note_off(msg, msg_timestamp, note_position)

            elif msg.type == 'note_on' and msg.velocity > 0 and self.ledsettings.mode != "Disabled":
                note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                if 0 <= note_position < self.ledstrip.led_number:
                    self.handle_note_on(msg, msg_timestamp, note_position)

            elif msg.type == "control_change":
                self.handle_control_change(msg, msg_timestamp)

            self.color_mode.MidiEvent(msg, None, self.ledstrip)

            self.saving.restart_time()

    def handle_note_off(self, msg, msg_timestamp, note_position):
        velocity = 0
        self.ledstrip.keylist_status[note_position] = 0

        if self.ledsettings.mode == "Fading":
            self.ledstrip.keylist[note_position] = 1000
        elif self.ledsettings.mode == "Normal":
            self.ledstrip.keylist[note_position] = 0
        elif self.ledsettings.mode == "Pedal":
            self.ledstrip.keylist[note_position] *= (100 - self.ledsettings.fadepedal_notedrop) / 100

        if self.ledstrip.keylist[note_position] <= 0:
            if self.ledsettings.backlight_brightness > 0 and self.menu.screensaver_is_running is not True:
                red_backlight = int(
                    self.ledsettings.get_backlight_color("Red")) * self.ledsettings.backlight_brightness_percent / 100
                green_backlight = int(
                    self.ledsettings.get_backlight_color("Green")) * self.ledsettings.backlight_brightness_percent / 100
                blue_backlight = int(
                    self.ledsettings.get_backlight_color("Blue")) * self.ledsettings.backlight_brightness_percent / 100
                color_backlight = Color(int(red_backlight), int(green_backlight), int(blue_backlight))
                self.ledstrip.strip.setPixelColor(note_position, color_backlight)
                self.ledstrip.set_adjacent_colors(note_position, color_backlight, True)
            else:
                self.ledstrip.strip.setPixelColor(note_position, Color(0, 0, 0))
                self.ledstrip.set_adjacent_colors(note_position, Color(0, 0, 0), False)

        if self.saving.is_recording:
            self.saving.add_track("note_off", msg.note, velocity, msg_timestamp)

    def handle_note_on(self, msg, msg_timestamp, note_position):
        velocity = msg.velocity

        color = self.color_mode.NoteOn(msg, msg_timestamp, None, note_position)
        if color is not None:
            red, green, blue = color
        else:
            red, green, blue = (0, 0, 0)

        self.ledstrip.keylist_color[note_position] = [red, green, blue]

        self.ledstrip.keylist_status[note_position] = 1
        if self.ledsettings.mode == "Velocity":
            brightness = (100 / (float(velocity) / 127)) / 100
        else:
            brightness = 1

        if self.ledsettings.mode == "Fading":
            self.ledstrip.keylist[note_position] = 1001
        elif self.ledsettings.mode == "Velocity":
            self.ledstrip.keylist[note_position] = 999 / float(brightness)
        elif self.ledsettings.mode == "Normal":
            self.ledstrip.keylist[note_position] = 1000
        elif self.ledsettings.mode == "Pedal":
            self.ledstrip.keylist[note_position] = 999

        channel = find_between(str(msg), "channel=", " ")
        if channel == "12" or channel == "11":
            if self.ledsettings.skipped_notes != "Finger-based":
                if channel == "12":
                    hand_color = self.learning.hand_colorR
                else:
                    hand_color = self.learning.hand_colorL

                red, green, blue = map(int, self.learning.hand_colorList[hand_color])
                s_color = Color(red, green, blue)
                self.ledstrip.strip.setPixelColor(note_position, s_color)
                self.ledstrip.set_adjacent_colors(note_position, s_color, False)
        else:
            if self.ledsettings.skipped_notes != "Normal":
                s_color = Color(int(int(red) / float(brightness)), int(int(green) / float(brightness)),
                                int(int(blue) / float(brightness)))
                self.ledstrip.strip.setPixelColor(note_position, s_color)
                self.ledstrip.set_adjacent_colors(note_position, s_color, False)

        if self.saving.is_recording:
            if self.ledsettings.color_mode == "Multicolor":
                import webcolors as wc
                self.saving.add_track("note_on", msg.note, velocity, msg_timestamp,
                                      wc.rgb_to_hex((red, green, blue)))
            else:
                self.saving.add_track("note_on", msg.note, velocity, msg_timestamp)

    def handle_control_change(self, msg, msg_timestamp):
        control = msg.control
        value = msg.value

        # Check if the control change is for the sustain pedal
        if control == 64:  # Sustain pedal
            self.last_sustain = value

        current_time = time.time()
        # Check if the sequence is active and next_step is defined
        if self.ledsettings.sequence_active and self.ledsettings.next_step is not None:
            try:
                # Ensure the control number matches the expected control number for sequence advancement
                if int(control) == int(self.ledsettings.control_number):
                    # Logic to advance the sequence:
                    # - If next_step is positive, advance when the pedal value exceeds next_step
                    # - If next_step is -1, advance when the pedal is released (value is 0)
                    if (int(self.ledsettings.next_step) > 0 and int(value) > int(self.ledsettings.next_step)) or \
                       (int(self.ledsettings.next_step) == -1 and int(value) == 0):
                        # Ensure at least 1 second has passed since the last sequence advancement
                        if (current_time - self.last_sequence_advance) > 1:
                            self.ledsettings.set_sequence(0, 1)
                            self.last_sequence_advance = current_time
            except TypeError:
                logger.warning("TypeError encountered in sequence logic")
            except Exception as e:
                logger.warning(f"[handle control change] Unexpected exception occurred: {e}")

        # Record the control change if recording is active
        if self.saving.is_recording:
            self.saving.add_control_change("control_change", 0, control, value, msg_timestamp)
