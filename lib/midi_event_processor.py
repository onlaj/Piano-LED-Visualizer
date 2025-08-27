import time

from rpi_ws281x import Color

from lib.functions import get_note_position, find_between
from lib.log_setup import logger


class MIDIEventProcessor:
    """
    Processes MIDI events and translates them into LED strip visualizations.
    """
    def __init__(self, midiports, ledstrip, ledsettings, usersettings, saving, learning, menu, color_mode):

        self.midiports = midiports
        self.ledstrip = ledstrip
        self.ledsettings = ledsettings
        self.usersettings = usersettings
        self.saving = saving
        self.learning = learning
        self.menu = menu
        self.color_mode = color_mode
        self.last_sustain = 0  # Track sustain pedal state
        # Time tracking for sequence advancement to prevent rapid triggering
        self.last_sequence_advance = 0

    def process_midi_events(self):
        """
        Main method to process pending MIDI events from the queue.
        Handles different event types and routes them to appropriate handlers.
        Selects input source based on playback/learning state.
        """
        # Determine which MIDI queue to process based on playback state
        if len(self.saving.is_playing_midi) == 0 and self.learning.is_started_midi is False:
            # Process live MIDI input
            self.midiports.midipending = self.midiports.midi_queue
        else:
            # Process MIDI file playback
            self.midiports.midipending = self.midiports.midifile_queue

        # Process all pending MIDI messages
        while self.midiports.midipending:
            msg, msg_timestamp = self.midiports.midipending.popleft()

            # Log MIDI events if enabled in settings
            if int(self.usersettings.get_setting_value("midi_logging")) == 1:
                if not msg.is_meta:
                    try:
                        self.learning.socket_send.append("midi_event" + str(msg))
                    except Exception as e:
                        logger.warning(f"[process midi events] Unexpected exception occurred: {e}")

            # Update last activity timestamp
            self.midiports.last_activity = time.time()

            # Route different MIDI event types to their handlers
            if (msg.type == "note_off" or (
                    msg.type == "note_on" and msg.velocity == 0)) and self.ledsettings.mode != "Disabled":
                # Handle note-off or note-on with zero velocity (equivalent to note-off)
                note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                if 0 <= note_position < self.ledstrip.led_number:
                    self.handle_note_off(msg, msg_timestamp, note_position)

            elif msg.type == 'note_on' and msg.velocity > 0 and self.ledsettings.mode != "Disabled":
                # Handle note-on with positive velocity
                note_position = get_note_position(msg.note, self.ledstrip, self.ledsettings)
                if 0 <= note_position < self.ledstrip.led_number:
                    self.handle_note_on(msg, msg_timestamp, note_position)

            elif msg.type == "control_change":
                # Handle control change messages (e.g., sustain pedal)
                self.handle_control_change(msg, msg_timestamp)

            # Pass the MIDI event to the color mode handler for additional processing
            self.color_mode.MidiEvent(msg, None, self.ledstrip)

            # Restart recording timer if recording
            self.saving.restart_time()

    def handle_note_off(self, msg, msg_timestamp, note_position):
        """
        Handle note-off MIDI events.
        
        Turns off the corresponding LED or applies fading effects based on the current mode.
        
        Args:
            msg: The MIDI message object
            msg_timestamp: Timestamp when the message was received
            note_position: Position on the LED strip corresponding to the note
        """
        velocity = 0
        self.ledstrip.keylist_status[note_position] = 0

        # Check if sustain pedal is active for Velocity and Pedal modes
        pedal_deadzone = 10  # Standard MIDI deadzone for sustain pedal
        sustain_active = (self.ledsettings.mode in ["Velocity", "Pedal"] and 
                         self.last_sustain >= pedal_deadzone)

        if sustain_active:
            # Mark note as sustained instead of turning off
            self.ledstrip.keylist_sustained[note_position] = 1
        else:
            # Apply different effects based on the current LED mode
            if self.ledsettings.mode == "Fading":
                # Set to fading state (1000+ indicates fading)
                self.ledstrip.keylist[note_position] = 1000
            elif self.ledsettings.mode == "Normal":
                # Turn off immediately
                self.ledstrip.keylist[note_position] = 0
            elif self.ledsettings.mode == "Pedal":
                # Gradually reduce brightness based on pedal settings
                self.ledstrip.keylist[note_position] *= (100 - self.ledsettings.fadepedal_notedrop) / 100

        # If LED is completely off, set appropriate color
        if self.ledstrip.keylist[note_position] <= 0:
            if self.ledsettings.backlight_brightness > 0 and self.menu.screensaver_is_running is not True:
                # Apply backlight color if backlight is enabled
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
                # Turn LED completely off
                self.ledstrip.strip.setPixelColor(note_position, Color(0, 0, 0))
                self.ledstrip.set_adjacent_colors(note_position, Color(0, 0, 0), False)

        # Record the note-off event if recording is active
        if self.saving.is_recording:
            self.saving.add_track("note_off", msg.note, velocity, msg_timestamp)

    def handle_note_on(self, msg, msg_timestamp, note_position):
        """
        Handle note-on MIDI events.
        
        Illuminates the corresponding LED with appropriate color based on current settings,
        velocity sensitivity, and various modes.
        
        Args:
            msg: The MIDI message object
            msg_timestamp: Timestamp when the message was received
            note_position: Position on the LED strip corresponding to the note
        """
        velocity = msg.velocity

        # Get color from color mode handler
        color = self.color_mode.NoteOn(msg, msg_timestamp, None, note_position)
        if color is not None:
            red, green, blue = color
        else:
            red, green, blue = (0, 0, 0)

        # Store the note color
        self.ledstrip.keylist_color[note_position] = [red, green, blue]

        # Set this key as active and clear sustained status
        self.ledstrip.keylist_status[note_position] = 1
        self.ledstrip.keylist_sustained[note_position] = 0
        
        # Calculate brightness based on velocity if in velocity mode
        if self.ledsettings.mode == "Velocity":
            brightness = velocity / 127.0  # Linear mapping: 0-127 velocity -> 0-1 brightness
        else:
            brightness = 1

        # Apply different effects based on the current LED mode
        if self.ledsettings.mode == "Fading":
            # 1001 indicates the key is active and will start fading when released
            self.ledstrip.keylist[note_position] = 1001
        elif self.ledsettings.mode == "Velocity":
            # Brightness varies with velocity (999 * brightness for linear scaling)
            self.ledstrip.keylist[note_position] = 999 * brightness
        elif self.ledsettings.mode == "Normal":
            # Standard mode - full brightness while key is pressed
            self.ledstrip.keylist[note_position] = 1000
        elif self.ledsettings.mode == "Pedal":
            # For pedal mode, start at 999 (will be affected by pedal status)
            self.ledstrip.keylist[note_position] = 999

        # Handle special channels for hand coloring (channels 11 and 12)
        channel = find_between(str(msg), "channel=", " ")
        if channel == "12" or channel == "11":
            if self.ledsettings.skipped_notes != "Finger-based":
                # Apply right hand or left hand color
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
                # Apply standard note color with velocity-based brightness
                s_color = Color(int(int(red) / float(brightness)), int(int(green) / float(brightness)),
                                int(int(blue) / float(brightness)))
                self.ledstrip.strip.setPixelColor(note_position, s_color)
                self.ledstrip.set_adjacent_colors(note_position, s_color, False)

        # Record the note-on event if recording is active
        if self.saving.is_recording:
            if self.ledsettings.color_mode == "Multicolor":
                import webcolors as wc
                # Include color information in multicolor mode
                self.saving.add_track("note_on", msg.note, velocity, msg_timestamp,
                                      wc.rgb_to_hex((red, green, blue)))
            else:
                self.saving.add_track("note_on", msg.note, velocity, msg_timestamp)

    def handle_control_change(self, msg, msg_timestamp):
        """
        Handle control change MIDI events.
        
        Processes pedal events, sequence advancement triggers, and other control messages.
        
        Args:
            msg: The MIDI message object
            msg_timestamp: Timestamp when the message was received
        """
        control = msg.control
        value = msg.value

        # Track sustain pedal state (MIDI CC 64)
        if control == 64:  # Sustain pedal
            self.last_sustain = value
            
            # Handle sustain pedal release - clear all sustained notes
            pedal_deadzone = 10  # Standard MIDI deadzone for sustain pedal
            if value < pedal_deadzone and self.ledsettings.mode in ["Velocity", "Pedal"]:
                for i in range(len(self.ledstrip.keylist_sustained)):
                    if self.ledstrip.keylist_sustained[i] == 1:
                        # Clear sustained status
                        self.ledstrip.keylist_sustained[i] = 0
                        # If key is not currently pressed, turn it off
                        if self.ledstrip.keylist_status[i] == 0:
                            self.ledstrip.keylist[i] = 0  # Turn off immediately
                            
                            # Apply appropriate LED color (backlight or off)
                            if self.ledsettings.backlight_brightness > 0 and self.menu.screensaver_is_running is not True:
                                # Apply backlight color if backlight is enabled
                                red_backlight = int(
                                    self.ledsettings.get_backlight_color("Red")) * self.ledsettings.backlight_brightness_percent / 100
                                green_backlight = int(
                                    self.ledsettings.get_backlight_color("Green")) * self.ledsettings.backlight_brightness_percent / 100
                                blue_backlight = int(
                                    self.ledsettings.get_backlight_color("Blue")) * self.ledsettings.backlight_brightness_percent / 100
                                color_backlight = Color(int(red_backlight), int(green_backlight), int(blue_backlight))
                                self.ledstrip.strip.setPixelColor(i, color_backlight)
                                self.ledstrip.set_adjacent_colors(i, color_backlight, True)
                            else:
                                # Turn LED completely off
                                self.ledstrip.strip.setPixelColor(i, Color(0, 0, 0))
                                self.ledstrip.set_adjacent_colors(i, Color(0, 0, 0), False)

        current_time = time.time()
        # Handle sequence advancement based on control values
        if self.ledsettings.sequence_active and self.ledsettings.next_step is not None:
            try:
                # Check if the incoming control matches the configured control for sequence advancement
                if int(control) == int(self.ledsettings.control_number):
                    # Sequence advancement logic:
                    # - If next_step > 0: advance when control value exceeds threshold
                    # - If next_step = -1: advance when control value = 0 (released)
                    if (int(self.ledsettings.next_step) > 0 and int(value) > int(self.ledsettings.next_step)) or \
                       (int(self.ledsettings.next_step) == -1 and int(value) == 0):
                        # Limit advancement frequency to prevent rapid triggering
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
