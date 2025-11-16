import time

from rpi_ws281x import Color

from lib.functions import get_note_position, find_between
from lib.log_setup import logger

OFF_COLOR = Color(0, 0, 0)


class MIDIEventProcessor:
    """
    Processes MIDI events and translates them into LED strip visualizations.
    """
    def __init__(self, midiports, ledstrip, ledsettings, usersettings, saving, learning, menu, color_mode, state_manager=None):

        self.midiports = midiports
        self.ledstrip = ledstrip
        self.ledsettings = ledsettings
        self.usersettings = usersettings
        self.saving = saving
        self.learning = learning
        self.menu = menu
        self.color_mode = color_mode
        self.state_manager = state_manager
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
        if not self.saving.is_playing_midi and not self.learning.is_started_midi:
            # Process live MIDI input
            self.midiports.midipending = self.midiports.midi_queue
        else:
            # Process MIDI file playback
            self.midiports.midipending = self.midiports.midifile_queue

        midi_logging_enabled = int(self.usersettings.get_setting_value("midi_logging")) == 1
        log_sink = self.learning.socket_send if midi_logging_enabled else None
        midiports = self.midiports
        ledstrip = self.ledstrip
        ledsettings = self.ledsettings
        color_mode = self.color_mode
        saving = self.saving
        handle_note_off = self.handle_note_off
        handle_note_on = self.handle_note_on
        handle_control_change = self.handle_control_change
        get_position = get_note_position
        led_count = ledstrip.led_number

        # Process a bounded slice per frame to avoid jitter and keep FPS stable
        # group near-identical timestamps and process notes first
        t0 = time.perf_counter()
        processed = 0

        def _process_one(msg, msg_timestamp):
            """Route one message exactly like before (LEDs/recording/color mode)."""
            if midi_logging_enabled and log_sink is not None and not getattr(msg, "is_meta", False):
                try:
                    log_sink.append("midi_event" + str(msg))
                except Exception as e:
                    logger.warning(f"[process midi events] Unexpected exception occurred: {e}")

            midiports.last_activity = time.time()
            # Update state manager for MIDI activity
            if self.state_manager:
                self.state_manager.update_midi_activity()

            msg_type = getattr(msg, "type", None)
            velocity = getattr(msg, "velocity", 0)

            if ledsettings.mode != "Disabled" and msg_type in ("note_on", "note_off"):
                note_position = get_position(msg.note, ledstrip, ledsettings)
                if 0 <= note_position < led_count:
                    if msg_type == "note_off" or velocity == 0:
                        handle_note_off(msg, msg_timestamp, note_position)
                    elif velocity > 0:
                        handle_note_on(msg, msg_timestamp, note_position)
            elif msg_type == "control_change":
                handle_control_change(msg, msg_timestamp)

            color_mode.MidiEvent(msg, None, ledstrip)
            saving.restart_time()

        # Bounded drain with bursts grouped by timestamp (~1.5ms window)
        BURST_WINDOW = 0.0015  # 1.5 ms
        BURST_LIMIT  = 64      # avoid starving under continuous streams

        midipending = midiports.midipending
        while midipending and processed < 512 and (time.perf_counter() - t0) < 0.003:
            head_msg, head_ts = midipending.popleft()
            burst = [(head_msg, head_ts)]
            # Coalesce a small burst of messages with almost the same timestamp
            while midipending and len(burst) < BURST_LIMIT:
                nxt_msg, nxt_ts = midipending[0]
                if abs(nxt_ts - head_ts) <= BURST_WINDOW:
                    burst.append(midipending.popleft())
                else:
                    break

            # Notes first (reduce visual latency for chords), then others
            for m, ts in burst:
                if getattr(m, "type", None) in ("note_on", "note_off"):
                    _process_one(m, ts)
                    processed += 1
                    if processed >= 512:
                        break

            if processed < 512:
                for m, ts in burst:
                    if getattr(m, "type", None) not in ("note_on", "note_off"):
                        _process_one(m, ts)
                        processed += 1
                        if processed >= 512:
                            break
    
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
            idle_color, use_backlight = self._resolve_idle_color()
            self._apply_idle_color(note_position, idle_color, use_backlight)

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
                idle_color, use_backlight = self._resolve_idle_color()
                for i, sustained in enumerate(self.ledstrip.keylist_sustained):
                    if sustained == 1:
                        # Clear sustained status
                        self.ledstrip.keylist_sustained[i] = 0
                        # If key is not currently pressed, turn it off
                        if self.ledstrip.keylist_status[i] == 0:
                            self.ledstrip.keylist[i] = 0  # Turn off immediately
                            self._apply_idle_color(i, idle_color, use_backlight)

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

    def _resolve_idle_color(self):
        """Compute the color to apply when a key returns to its idle state."""
        if self.ledsettings.backlight_brightness > 0 and not self.menu.screensaver_is_running:
            scale = self.ledsettings.backlight_brightness_percent / 100.0
            return Color(
                int(self.ledsettings.backlight_red * scale),
                int(self.ledsettings.backlight_green * scale),
                int(self.ledsettings.backlight_blue * scale),
            ), True
        return OFF_COLOR, False

    def _apply_idle_color(self, note_position, color_value, is_backlight):
        """Apply either the backlight color or switch LEDs off for a key."""
        self.ledstrip.strip.setPixelColor(note_position, color_value)
        self.ledstrip.set_adjacent_colors(note_position, color_value, True if is_backlight else False)
