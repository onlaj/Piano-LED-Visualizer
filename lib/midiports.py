import mido
import time
import threading
from collections import deque
from lib.log_setup import logger

# Cache for MIDI port names to avoid repeated slow scans
_cached_input_names = None
_cached_output_names = None
_cache_lock = threading.Lock()


def _get_cached_input_names():
    """Get input port names, using cache if available."""
    global _cached_input_names
    with _cache_lock:
        if _cached_input_names is None:
            try:
                _cached_input_names = mido.get_input_names()
            except Exception as e:
                logger.warning(f"Failed to get input names: {e}")
                _cached_input_names = []
        return _cached_input_names.copy()


def _get_cached_output_names():
    """Get output port names, using cache if available."""
    global _cached_output_names
    with _cache_lock:
        if _cached_output_names is None:
            try:
                _cached_output_names = mido.get_output_names()
            except Exception as e:
                logger.warning(f"Failed to get output names: {e}")
                _cached_output_names = []
        return _cached_output_names.copy()


def _refresh_port_cache():
    """Refresh the cached port names."""
    global _cached_input_names, _cached_output_names
    with _cache_lock:
        try:
            _cached_input_names = mido.get_input_names()
        except Exception as e:
            logger.warning(f"Failed to refresh input names: {e}")
            _cached_input_names = []
        try:
            _cached_output_names = mido.get_output_names()
        except Exception as e:
            logger.warning(f"Failed to refresh output names: {e}")
            _cached_output_names = []


def _close_port(port):
    if port is None:
        return
    try:
        port.close()
    except Exception:
        pass


class MidiPorts:
    # suppress quick echoes of notes we just forwarded piano -> computer
    _ECHO_SUPPRESS_SEC = 0.08

    def __init__(self, usersettings):
        self.usersettings = usersettings
        # queue items: (msg, timestamp, source)
        self.midifile_queue = deque(maxlen=500)
        self.midi_queue = deque(maxlen=1000)
        self.websocket_midi_queue = deque(maxlen=1000)
        self.drop_counter = 0
        self.last_activity = 0

        self.piano_in = None
        self.piano_out = None
        self.computer_in = None
        self.computer_out = None
        # old names still used elsewhere
        self.inport = None
        self.playport = None

        self.midipending = None
        self.midi_monitor_thread = None
        self.monitor_running = False
        self.menu = None
        self.portname = "piano"

        # never port.send() from the RtMidi callback - stalls ALSA
        # (note_on only shows up when note_off arrives)
        self._thru_queue = deque(maxlen=2000)
        self._thru_event = threading.Event()
        self._thru_running = True
        self._thru_thread = threading.Thread(
            target=self._thru_loop, name="midi-thru", daemon=True
        )
        self._recent_piano_notes = {}  # note -> perf_counter when forwarded to computer
        self._midi_mode_cache = "light_show"
        self._suppress_computer_control = True
        self._midi_logging = False

        try:
            _get_cached_input_names()
        except Exception:
            logger.warning(
                "First access to mido failed.  Possibly from known issue: "
                "https://github.com/SpotlightKid/python-rtmidi/issues/138"
            )

        self.migrate_port_settings()
        self._midi_mode_cache = self.get_midi_mode()
        self._refresh_suppress_computer_control()
        self._refresh_midi_logging()
        self._thru_thread.start()
        self.setup_ports()

    def migrate_port_settings(self):
        """Copy old input/play/secondary settings onto piano/computer/midi_mode if needed."""
        play = self.usersettings.get_setting_value("play_port")
        inp = self.usersettings.get_setting_value("input_port")
        secondary = self.usersettings.get_setting_value("secondary_input_port")

        piano = self.usersettings.get_setting_value("piano_port")
        if not piano or piano == "default":
            # play_port was usually the piano
            if play and play != "default":
                self.usersettings.change_setting_value("piano_port", play)
            elif inp and inp != "default":
                self.usersettings.change_setting_value("piano_port", inp)

        computer = self.usersettings.get_setting_value("computer_port")
        if not computer or computer == "default":
            if secondary and secondary != "default":
                self.usersettings.change_setting_value("computer_port", secondary)
            elif (
                play
                and play != "default"
                and inp
                and inp != "default"
                and self._extract_descriptive_port_name(play)
                != self._extract_descriptive_port_name(inp)
            ):
                # old synthesia setups put the peer on input_port
                self.usersettings.change_setting_value("computer_port", inp)

        mode = self.usersettings.get_setting_value("midi_mode")
        if not mode or mode == "default":
            self.usersettings.change_setting_value("midi_mode", "light_show")

    def get_midi_mode(self):
        mode = self.usersettings.get_setting_value("midi_mode") or "light_show"
        if mode not in ("light_show", "learning"):
            mode = "light_show"
        self._midi_mode_cache = mode
        return mode

    def setup_ports(self):
        self.open_piano_ports()
        self.open_computer_ports()

    def open_piano_ports(self, portname=None):
        if portname is None:
            portname = self.usersettings.get_setting_value("piano_port")

        opened_in = False
        opened_out = False
        if portname and portname != "default":
            opened_in = self._open_piano_input(portname)
            opened_out = self._open_piano_output(portname)
        if not opened_in:
            self.find_and_set_piano()
        elif not opened_out and self.piano_out is None:
            # some devices use different names for in vs out
            self._recover_piano_output(portname)

        self.inport = self.piano_in
        self.playport = self.piano_out

    def open_computer_ports(self, portname=None):
        if portname is None:
            portname = self.usersettings.get_setting_value("computer_port")

        _close_port(self.computer_in)
        _close_port(self.computer_out)
        self.computer_in = None
        self.computer_out = None

        if not portname or portname == "default":
            return

        piano_port = self.usersettings.get_setting_value("piano_port")
        piano_desc = self._extract_descriptive_port_name(piano_port)
        computer_desc = self._extract_descriptive_port_name(portname)
        if piano_desc and computer_desc and piano_desc == computer_desc:
            logger.info("Computer port matches piano port; skipping computer open to avoid loops")
            return

        resolved_in = self._resolve_port_name(portname, _get_cached_input_names())
        if resolved_in:
            try:
                self.computer_in = mido.open_input(
                    resolved_in, callback=lambda msg: self.route_midi_message(msg, "computer")
                )
                logger.info("Computer input loaded: " + resolved_in)
            except Exception as e:
                logger.info("Can't load computer input '{}': {}".format(resolved_in, e))
                self.computer_in = None

        resolved_out = self._resolve_port_name(portname, _get_cached_output_names())
        if resolved_out:
            try:
                self.computer_out = mido.open_output(resolved_out)
                logger.info("Computer output loaded: " + resolved_out)
            except Exception as e:
                logger.info("Can't load computer output '{}': {}".format(resolved_out, e))
                self.computer_out = None

    def _open_piano_input(self, portname):
        resolved = self._resolve_port_name(portname, _get_cached_input_names())
        if not resolved:
            return False
        try:
            new_in = mido.open_input(
                resolved, callback=lambda msg: self.route_midi_message(msg, "piano")
            )
            old = self.piano_in
            self.piano_in = new_in
            self.inport = self.piano_in
            time.sleep(0.002)
            _close_port(old)
            self._sync_legacy_port_settings(resolved)
            logger.info("Piano input loaded: " + resolved)
            return True
        except Exception as e:
            logger.info("Can't load piano input '{}': {}".format(resolved, e))
            return False

    def _open_piano_output(self, portname):
        resolved = self._resolve_port_name(portname, _get_cached_output_names())
        if not resolved:
            return False
        try:
            new_out = mido.open_output(resolved)
            old = self.piano_out
            self.piano_out = new_out
            self.playport = self.piano_out
            time.sleep(0.002)
            _close_port(old)
            logger.info("Piano output loaded: " + resolved)
            return True
        except Exception as e:
            logger.info("Can't load piano output '{}': {}".format(resolved, e))
            return False

    def _recover_piano_output(self, portname):
        outputs = _get_cached_output_names()
        if not outputs:
            return False

        descriptive = self._extract_descriptive_port_name(portname)
        device = self._extract_device_name(portname)
        candidates = []
        if descriptive:
            for name in outputs:
                if descriptive in name or self._extract_descriptive_port_name(name) == descriptive:
                    candidates.append(name)
        if device:
            for name in outputs:
                if name not in candidates and device in name:
                    candidates.append(name)

        for name in candidates:
            if self._open_piano_output(name):
                return True

        logger.info(
            "Piano output still missing after input open; rediscovering piano ports"
        )
        self.find_and_set_piano()
        return self.piano_out is not None

    def find_and_set_piano(self):
        """Pick an available piano port, preferring the configured device name."""
        try:
            names = _get_cached_input_names()
            logger.info("Available inputs: {}".format(names))

            configured_port = self.usersettings.get_setting_value("piano_port")
            preferred_device = (
                self._extract_device_name(configured_port)
                if configured_port and configured_port != "default"
                else None
            )

            candidates = []
            if preferred_device:
                candidates.extend([n for n in names if preferred_device in n])
            candidates.extend(
                [
                    n
                    for n in names
                    if n not in candidates
                    and "Through" not in n
                    and "RPi" not in n
                    and "RtMidi" not in n
                    and "USB-USB" not in n
                ]
            )

            for pname in candidates:
                if self._open_piano_input(pname):
                    self.usersettings.change_setting_value("piano_port", pname)
                    if not self._open_piano_output(pname):
                        # look for another output name on the same device
                        descriptive = self._extract_descriptive_port_name(pname)
                        device = self._extract_device_name(pname)
                        for out_name in _get_cached_output_names():
                            if out_name == pname:
                                continue
                            if descriptive and (
                                descriptive in out_name
                                or self._extract_descriptive_port_name(out_name) == descriptive
                            ):
                                if self._open_piano_output(out_name):
                                    break
                            elif device and device in out_name:
                                if self._open_piano_output(out_name):
                                    break
                    self._sync_legacy_port_settings(pname)
                    return
        except Exception as e:
            logger.info("No piano port found: {}".format(e))

    def _sync_legacy_port_settings(self, portname):
        """Also write the old input_port / play_port keys."""
        try:
            self.usersettings.change_setting_value("input_port", portname)
            self.usersettings.change_setting_value("play_port", portname)
        except Exception:
            pass

    def _resolve_port_name(self, configured, available_names):
        """Match a saved port name against currently available mido names."""
        if not configured or configured == "default" or not available_names:
            return None
        if configured in available_names:
            return configured

        descriptive = self._extract_descriptive_port_name(configured)
        if descriptive:
            for name in available_names:
                if descriptive in name or name.startswith(descriptive):
                    return name
            for name in available_names:
                if self._extract_descriptive_port_name(name) == descriptive:
                    return name
        return None

    def _extract_device_name(self, port_string):
        """Extract device name from a port string."""
        if not port_string or port_string == "default":
            return None

        parts = port_string.split()
        if parts:
            device_part = parts[0]
            if ":" in device_part:
                device_part = device_part.split(":")[0]
            return device_part
        return None

    def _extract_descriptive_port_name(self, port_string):
        """Port name without the trailing client:port id."""
        if not port_string or port_string == "default":
            return None

        parts = port_string.split()
        if len(parts) > 1:
            last_part = parts[-1]
            if ":" in last_part:
                try:
                    client, port = last_part.split(":")
                    int(client)
                    int(port)
                    return " ".join(parts[:-1])
                except (ValueError, IndexError):
                    pass

        if parts:
            last_part = parts[-1]
            if ":" in last_part and last_part.count(":") == 1:
                try:
                    int(last_part.split(":")[1])
                    parts[-1] = last_part.split(":")[0]
                    return " ".join(parts)
                except ValueError:
                    pass

        return port_string

    def add_instance(self, menu):
        self.menu = menu

    def change_port(self, port, portname):
        try:
            if port in ("piano", "inport", "playport"):
                self.usersettings.change_setting_value("piano_port", portname)
                self.open_piano_ports(portname)
                label = "piano"
            elif port == "computer":
                self.usersettings.change_setting_value("computer_port", portname)
                # also update secondary_input_port
                try:
                    self.usersettings.change_setting_value("secondary_input_port", portname)
                except Exception:
                    pass
                self.open_computer_ports(portname)
                label = "computer"
            else:
                raise ValueError("Unknown port role: " + str(port))

            if self.menu is not None:
                self.menu.render_message("Changing " + label + " to:", portname, 1500)
                self.menu.show()
        except Exception:
            if self.menu is not None:
                self.menu.render_message("Can't change " + str(port) + " to:", portname, 1500)
                self.menu.show()

    def set_midi_mode(self, mode):
        if mode not in ("light_show", "learning"):
            mode = "light_show"
        self.usersettings.change_setting_value("midi_mode", mode)
        self._midi_mode_cache = mode
        # learning needs the computer port open
        if mode == "learning":
            self.open_computer_ports()
        logger.info("MIDI mode set to " + mode)
        return mode

    def _refresh_suppress_computer_control(self):
        value = self.usersettings.get_setting_value("suppress_computer_control")
        self._suppress_computer_control = str(value) in ("1", "true", "True")

    def set_suppress_computer_control(self, enabled):
        value = "1" if enabled else "0"
        self.usersettings.change_setting_value("suppress_computer_control", value)
        self._suppress_computer_control = bool(enabled)
        return self._suppress_computer_control

    def _refresh_midi_logging(self):
        value = self.usersettings.get_setting_value("midi_logging")
        self._midi_logging = str(value) in ("1", "true", "True")

    def set_midi_logging(self, enabled):
        value = "1" if enabled else "0"
        self.usersettings.change_setting_value("midi_logging", value)
        self._midi_logging = bool(enabled)
        return self._midi_logging

    def _log_midi_message(self, msg, source):
        if not self._midi_logging:
            return
        if getattr(msg, "is_meta", False):
            return
        try:
            from webinterface import app_state

            learning = getattr(app_state, "learning", None)
            if learning is None or not hasattr(learning, "socket_send"):
                return
            sink = learning.socket_send
            # trim if nobody is reading
            if len(sink) > 500:
                del sink[:250]
            sink.append("midi_event[{}] {}".format(source, msg))
        except Exception:
            pass

    def reconnect_ports(self):
        self.open_piano_ports()
        self.open_computer_ports()

    def _enqueue_for_leds(self, msg, source):
        ts = time.perf_counter()
        q = self.midi_queue
        if q.maxlen and len(q) >= q.maxlen:
            self.drop_counter += 1
            if getattr(msg, "type", None) not in ("note_on", "note_off"):
                return
            try:
                q.popleft()
            except Exception:
                pass
        q.append((msg, ts, source))

    def _forward_to_port(self, port, msg):
        if port is None:
            return
        try:
            port.send(msg)
        except Exception as e:
            logger.debug(f"Skipping MIDI forward: {e}")

    def _queue_thru(self, destination, msg):
        # destination: "piano" or "computer"
        try:
            payload = msg.copy()
        except Exception:
            payload = msg
        if self._thru_queue.maxlen and len(self._thru_queue) >= self._thru_queue.maxlen:
            try:
                self._thru_queue.popleft()
            except Exception:
                pass
        self._thru_queue.append((destination, payload))
        self._thru_event.set()

    def _thru_loop(self):
        # runs outside the RtMidi callback so send() can't stall input
        while self._thru_running:
            self._thru_event.wait(timeout=0.05)
            self._thru_event.clear()
            while self._thru_queue:
                try:
                    destination, msg = self._thru_queue.popleft()
                except IndexError:
                    break
                if destination == "computer":
                    self._forward_to_port(self.computer_out, msg)
                elif destination == "piano":
                    self._forward_to_port(self.piano_out, msg)

    def _is_light_cue(self, msg):
        # synthesia finger channels, or velocity=1 silent guide notes
        msg_type = getattr(msg, "type", None)
        if msg_type not in ("note_on", "note_off"):
            return False
        channel = getattr(msg, "channel", None)
        if channel in (11, 12):
            return True
        if msg_type == "note_on" and getattr(msg, "velocity", 0) == 1:
            return True
        return False

    def _is_likely_echo_from_computer(self, msg):
        # our own piano note coming back from the computer side
        if self._is_light_cue(msg):
            return False
        msg_type = getattr(msg, "type", None)
        if msg_type not in ("note_on", "note_off"):
            return False
        note = getattr(msg, "note", None)
        if note is None:
            return False
        sent_at = self._recent_piano_notes.get(note)
        if sent_at is None:
            return False
        return (time.perf_counter() - sent_at) < self._ECHO_SUPPRESS_SEC

    def route_midi_message(self, msg, source):
        # light_show: piano -> LEDs
        # learning: soft thru between piano and computer, guide lights -> LEDs
        mode = self._midi_mode_cache
        self._log_midi_message(msg, source)

        if source == "piano":
            if mode == "learning":
                note = getattr(msg, "note", None)
                if note is not None and getattr(msg, "type", None) in ("note_on", "note_off"):
                    self._recent_piano_notes[note] = time.perf_counter()
                self._queue_thru("computer", msg)
                # still needed for LearnMIDI matching / note-off
                self._enqueue_for_leds(msg, "piano")
            else:
                self._enqueue_for_leds(msg, "piano")

            self._maybe_forward_to_websocket(msg)
            return

        if source == "computer":
            if mode != "learning":
                return

            if self._is_light_cue(msg):
                self._enqueue_for_leds(msg, "computer")

            # all-notes-off should clear LEDs even if CC thru is blocked
            is_all_notes_off = (
                getattr(msg, "type", None) == "control_change"
                and getattr(msg, "control", None) == 123
            )
            if is_all_notes_off:
                self._enqueue_for_leds(msg, "computer")

            if self._suppress_computer_control and getattr(msg, "type", None) == "control_change":
                return
            if not self._is_likely_echo_from_computer(msg):
                self._queue_thru("piano", msg)
            return

    def _maybe_forward_to_websocket(self, msg):
        try:
            from webinterface import app_state, webinterface

            if hasattr(app_state, "practice_active") and app_state.practice_active:
                msg_type = getattr(msg, "type", "")
                if msg_type in ("note_on", "note_off"):
                    channel = getattr(msg, "channel", 0)
                    note = getattr(msg, "note", 0)
                    velocity = getattr(msg, "velocity", 0)
                    time_val = getattr(msg, "time", 0)
                    midi_string = (
                        f"midi_event{msg_type} channel={channel} note={note} "
                        f"velocity={velocity} time={time_val}"
                    )
                    if len(webinterface.websocket_midi_send) < 100:
                        webinterface.websocket_midi_send.append(midi_string)
        except Exception:
            pass

    def msg_callback(self, msg):
        # old name, still treated as piano input
        self.route_midi_message(msg, "piano")

    def add_websocket_midi_message(self, msg_string):
        """
        Parse a MIDI message string from websocket and add to websocket_midi_queue.

        Format: "midi_eventnote_on channel=0 note=60 velocity=127 time=0"
        or: "midi_eventnote_off channel=0 note=60 velocity=0 time=0"
        """
        try:
            if msg_string.startswith("midi_event"):
                msg_string = msg_string[10:]

            parts = msg_string.strip().split()
            if not parts:
                return

            msg_type = parts[0]
            if msg_type not in ("note_on", "note_off"):
                logger.debug(f"Unsupported MIDI message type from websocket: {msg_type}")
                return

            channel = 0
            note = 0
            velocity = 0
            time_val = 0

            for part in parts[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    try:
                        if key == "channel":
                            channel = int(value)
                        elif key == "note":
                            note = int(value)
                        elif key == "velocity":
                            velocity = int(value)
                        elif key == "time":
                            time_val = float(value)
                    except ValueError:
                        logger.warning(f"Invalid value in websocket MIDI message: {part}")
                        continue

            if msg_type == "note_on":
                msg = mido.Message(
                    "note_on", channel=channel, note=note, velocity=velocity, time=time_val
                )
            else:
                msg = mido.Message(
                    "note_off", channel=channel, note=note, velocity=velocity, time=time_val
                )

            ts = time.perf_counter()
            q = self.websocket_midi_queue
            if q.maxlen and len(q) >= q.maxlen:
                try:
                    q.popleft()
                except Exception:
                    pass
            q.append((msg, ts, "websocket"))

            if self.playport is not None:
                try:
                    self.playport.send(msg)
                except Exception as e:
                    logger.debug(f"Skipping playport send: {e}")

        except Exception as e:
            logger.warning(f"Error parsing websocket MIDI message: {msg_string}, error: {e}")

    def clear_websocket_midi_queue(self):
        self.websocket_midi_queue.clear()

    def start_midi_monitor(self):
        if self.midi_monitor_thread is None or not self.midi_monitor_thread.is_alive():
            self.monitor_running = True
            self.midi_monitor_thread = threading.Thread(
                target=self.auto_reconnect_loop, daemon=True
            )
            self.midi_monitor_thread.start()
            logger.info("MIDI device monitor started")

    def stop_midi_monitor(self):
        self.monitor_running = False
        if self.midi_monitor_thread and self.midi_monitor_thread.is_alive():
            self.midi_monitor_thread.join(timeout=1)
        logger.info("MIDI device monitor stopped")

    def auto_reconnect_loop(self):
        # reopen ports when a configured device reappears
        last_piano_present = None
        last_computer_present = None

        while self.monitor_running:
            try:
                _refresh_port_cache()
                input_names = _get_cached_input_names()

                piano_port = self.usersettings.get_setting_value("piano_port")
                computer_port = self.usersettings.get_setting_value("computer_port")

                piano_descriptive = (
                    self._extract_descriptive_port_name(piano_port)
                    if piano_port and piano_port != "default"
                    else None
                )
                computer_descriptive = (
                    self._extract_descriptive_port_name(computer_port)
                    if computer_port and computer_port != "default"
                    else None
                )

                piano_present = False
                if piano_descriptive:
                    piano_present = any(piano_descriptive in n for n in input_names)

                computer_present = False
                if computer_descriptive:
                    computer_present = any(computer_descriptive in n for n in input_names)

                piano_restored = piano_present and (last_piano_present is False)
                computer_restored = computer_present and (last_computer_present is False)

                if piano_restored:
                    logger.info("Piano MIDI port restored. Reopening piano ports.")
                    try:
                        self.open_piano_ports()
                    except Exception as e:
                        logger.info("Piano reconnect raised: {}".format(e))

                if computer_restored:
                    logger.info("Computer MIDI port restored. Reopening computer ports.")
                    try:
                        self.open_computer_ports()
                    except Exception as e:
                        logger.info("Computer reconnect raised: {}".format(e))

                last_piano_present = piano_present
                last_computer_present = computer_present
                time.sleep(3)
            except Exception as e:
                logger.info("auto_reconnect_loop error: {}".format(e))
                time.sleep(5)
