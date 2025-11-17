import mido
from lib import connectall
import time
import threading
from collections import deque
from lib.log_setup import logger

class MidiPorts:
    def __init__(self, usersettings):
        self.usersettings = usersettings
        # midi queues will contain a tuple (midi_msg, timestamp)
        self.midifile_queue = deque(maxlen=500)
        self.midi_queue = deque(maxlen=1000)
        # Count dropped messages when queue is full (diagnostics)
        self.drop_counter = 0
        self.last_activity = 0
        self.inport = None
        self.playport = None
        self.midipending = None
        self.midi_monitor_thread = None
        self.monitor_running = False

        # mido backend python-rtmidi has a bug on some (debian-based) systems
        # involving the library location of alsa plugins
        # https://github.com/SpotlightKid/python-rtmidi/issues/138
        # The bug will cause the first attempt at accessing a port to fail (due to the failed plugin lookup?)
        # but succeed on the second
        # Access once to trigger bug if exists, so open port later will succeed on attempt:
        try:
            mido.get_input_names()
        except Exception as e:
            logger.warning("First access to mido failed.  Possibly from known issue: https://github.com/SpotlightKid/python-rtmidi/issues/138")

        # initial port setup (tries stored settings or first available)
        self.setup_ports()

        self.portname = "inport"

    def setup_ports(self):
        """Try to open the configured or first available ports."""
        # Input port
        port = self.usersettings.get_setting_value("input_port")
        if port and port != "default":
            try:
                self.inport = mido.open_input(port, callback=self.msg_callback)
                logger.info("Inport loaded and set to " + port)
            except Exception as e:
                logger.info("Can't load input port '{}': {}".format(port, e))
                self.inport = None
        else:
            self.find_and_set_input()

        # Output port
        port = self.usersettings.get_setting_value("play_port")
        if port and port != "default":
            try:
                self.playport = mido.open_output(port)
                logger.info("Playport loaded and set to " + port)
            except Exception as e:
                logger.info("Can't load play port '{}': {}".format(port, e))
                self.playport = None
        else:
            self.find_and_set_output()

    def find_and_set_input(self):
        """Find and set an available input port, preferring configured device names."""
        try:
            names = mido.get_input_names()
            logger.info("Available inputs: {}".format(names))
            
            # Get configured port to prefer its device name
            configured_port = self.usersettings.get_setting_value("input_port")
            preferred_device = self._extract_device_name(configured_port) if configured_port and configured_port != "default" else None
            
            for pname in names:
                # Prefer configured device if present; otherwise skip generic/through ports
                if preferred_device and preferred_device in pname:
                    try:
                        self.inport = mido.open_input(pname, callback=self.msg_callback)
                        self.usersettings.change_setting_value("input_port", pname)
                        logger.info("Inport set to " + pname)
                        return
                    except Exception as e:
                        logger.info("Failed to open input '{}' : {}".format(pname, e))
            
            # If preferred device not found, try any non-generic port
            for pname in names:
                if "Through" not in pname and "RPi" not in pname and "RtMidi" not in pname and "USB-USB" not in pname:
                    try:
                        self.inport = mido.open_input(pname, callback=self.msg_callback)
                        self.usersettings.change_setting_value("input_port", pname)
                        logger.info("Inport set to " + pname)
                        return
                    except Exception as e:
                        logger.info("Failed to open input '{}' : {}".format(pname, e))
        except Exception as e:
            logger.info("No input port found: {}".format(e))

    def find_and_set_output(self):
        """Find and set an available output port, preferring configured device names."""
        try:
            names = mido.get_output_names()
            logger.info("Available outputs: {}".format(names))
            
            # Get configured port to prefer its device name
            configured_port = self.usersettings.get_setting_value("play_port")
            preferred_device = self._extract_device_name(configured_port) if configured_port and configured_port != "default" else None
            
            for pname in names:
                # Prefer configured device if present; otherwise skip generic/through ports
                if preferred_device and preferred_device in pname:
                    try:
                        self.playport = mido.open_output(pname)
                        self.usersettings.change_setting_value("play_port", pname)
                        logger.info("Playport set to " + pname)
                        return
                    except Exception as e:
                        logger.info("Failed to open output '{}' : {}".format(pname, e))
            
            # If preferred device not found, try any non-generic port
            for pname in names:
                if "Through" not in pname and "RPi" not in pname and "RtMidi" not in pname and "USB-USB" not in pname:
                    try:
                        self.playport = mido.open_output(pname)
                        self.usersettings.change_setting_value("play_port", pname)
                        logger.info("Playport set to " + pname)
                        return
                    except Exception as e:
                        logger.info("Failed to open output '{}' : {}".format(pname, e))
        except Exception as e:
            logger.info("No play port found: {}".format(e))

    def _extract_device_name(self, port_string):
        """Extract device name from a port string.
        
        Port strings can be in formats like:
        - "CASIO USB-MIDI:0" -> "CASIO"
        - "Yamaha P-125:0" -> "Yamaha"
        - "client_name:port_name 128:0" -> "client_name"
        """
        if not port_string or port_string == "default":
            return None
        
        # Try to extract device name from the port string
        # Format is typically "Device Name:Port" or "Device Name Port"
        parts = port_string.split()
        if parts:
            # Take the first part and remove port number if present
            device_part = parts[0]
            # Remove trailing ":0" or ":1" etc.
            if ":" in device_part:
                device_part = device_part.split(":")[0]
            return device_part
        
        return None

    def connectall(self):
        """Reconnect mido ports and then manage aconnect connections."""
        # Reconnect the input and playports on a connectall
        self.reconnect_ports()
        # Now connect all the remaining ports
        connectall.connectall(self.usersettings)

    def add_instance(self, menu):
        self.menu = menu

    def change_port(self, port, portname):
        try:
            destroy_old = None
            if port == "inport":
                destroy_old = self.inport
                self.inport = mido.open_input(portname, callback=self.msg_callback)
                self.usersettings.change_setting_value("input_port", portname)
            elif port == "playport":
                destroy_old = self.playport
                self.playport = mido.open_output(portname)
                self.usersettings.change_setting_value("play_port", portname)
            self.menu.render_message("Changing " + port + " to:", portname, 1500)
            if destroy_old is not None:
                destroy_old.close()
            self.menu.show()
        except Exception:
            self.menu.render_message("Can't change " + port + " to:", portname, 1500)
            self.menu.show()

    def reconnect_ports(self):
        """Reconnect input and output ports, with fallback to finding available ports."""
        try:
            destroy_old = self.inport
            port = self.usersettings.get_setting_value("input_port")
            if port and port != "default":
                self.inport = mido.open_input(port, callback=self.msg_callback)
                if destroy_old is not None:
                    time.sleep(0.002)
                    try:
                        destroy_old.close()
                    except Exception:
                        pass
                logger.info("Reconnected input port: " + str(port))
            else:
                # No configured port, try to find one
                self.find_and_set_input()
        except Exception as e:
            logger.info("Can't reconnect input port '{}': {}".format(port, e))
            # fallback: try to find any input
            self.find_and_set_input()

        try:
            destroy_old = self.playport
            port = self.usersettings.get_setting_value("play_port")
            if port and port != "default":
                self.playport = mido.open_output(port)
                if destroy_old is not None:
                    time.sleep(0.002)
                    try:
                        destroy_old.close()
                    except Exception:
                        pass
                logger.info("Reconnected play port: " + str(port))
            else:
                # No configured port, try to find one
                self.find_and_set_output()
        except Exception as e:
            logger.info("Can't reconnect play port '{}': {}".format(port, e))
            # fallback: try to find any output
            self.find_and_set_output()

    def msg_callback(self, msg):
        # Bound queue under load: keep notes prioritized; drop others first
        ts = time.perf_counter()
        q = self.midi_queue
        if q.maxlen and len(q) >= q.maxlen:
            self.drop_counter += 1
            # If not a note event, drop silently
            if getattr(msg, 'type', None) not in ('note_on', 'note_off'):
                return
            # Note event: make room by evicting oldest item
            try:
                q.popleft()
            except Exception:
                pass
        q.append((msg, ts))
    
    def start_midi_monitor(self):
        """Start monitoring for MIDI device changes and auto-connect"""
        if self.midi_monitor_thread is None or not self.midi_monitor_thread.is_alive():
            self.monitor_running = True
            self.midi_monitor_thread = threading.Thread(target=self.auto_reconnect_loop, daemon=True)
            self.midi_monitor_thread.start()
            logger.info("MIDI device monitor started")
    
    def stop_midi_monitor(self):
        """Stop monitoring for MIDI device changes"""
        self.monitor_running = False
        if self.midi_monitor_thread and self.midi_monitor_thread.is_alive():
            self.midi_monitor_thread.join(timeout=1)
        logger.info("MIDI device monitor stopped")
    
    def auto_reconnect_loop(self):
        """
        Watch mido port lists and:
        - detect when configured devices appear (transition from absent -> present) and call connectall()
        - detect when the previously opened ports vanish and close them locally so they can be reopened
        """
        last_device_present = False
        
        while self.monitor_running:
            try:
                input_names = mido.get_input_names()
                output_names = mido.get_output_names()
                all_names = list(input_names) + list(output_names)

                # Get configured device names
                input_port = self.usersettings.get_setting_value("input_port")
                play_port = self.usersettings.get_setting_value("play_port")
                
                configured_input_device = self._extract_device_name(input_port) if input_port and input_port != "default" else None
                configured_output_device = self._extract_device_name(play_port) if play_port and play_port != "default" else None

                # Check if configured devices are present in the system port lists now
                device_present = False
                if configured_input_device:
                    device_present = any(configured_input_device in n for n in all_names)
                if not device_present and configured_output_device:
                    device_present = any(configured_output_device in n for n in all_names)
                # If no configured device, consider any non-generic device as present
                if not configured_input_device and not configured_output_device:
                    device_present = any("Through" not in n and "RPi" not in n and "RtMidi" not in n and "USB-USB" not in n for n in all_names)

                # Debug logging of what the watcher sees:
                logger.debug("auto_reconnect: inputs=%s outputs=%s", input_names, output_names)

                # If configured device appeared now but wasn't present before -> trigger connectall()
                if device_present and not last_device_present:
                    logger.info("Configured MIDI device detected (appearance). Triggering connectall()")
                    try:
                        # call the same logic the web UI triggers
                        self.connectall()
                        logger.info("connectall() completed after device appearance")
                    except Exception as e:
                        logger.info("connectall() raised: {}".format(e))

                # If we have an inport object but its name is no longer present in mido's input list, close and clear it.
                try:
                    if self.inport is not None:
                        port_name = getattr(self.inport, 'name', None)
                        if port_name and not any(port_name in n for n in input_names):
                            logger.info("Inport '{}' no longer in mido list -> closing local object".format(port_name))
                            try:
                                self.inport.close()
                            except Exception as e:
                                logger.debug("Error closing stale inport: {}".format(e))
                            self.inport = None
                except Exception as e:
                    logger.debug("Error while checking/closing inport: {}".format(e))

                # Same for playport
                try:
                    if self.playport is not None:
                        port_name = getattr(self.playport, 'name', None)
                        if port_name and not any(port_name in n for n in output_names):
                            logger.info("Playport '{}' no longer in mido list -> closing local object".format(port_name))
                            try:
                                self.playport.close()
                            except Exception as e:
                                logger.debug("Error closing stale playport: {}".format(e))
                            self.playport = None
                except Exception as e:
                    logger.debug("Error while checking/closing playport: {}".format(e))

                last_device_present = device_present
                time.sleep(3)  # shorter interval to react quicker
            except Exception as e:
                logger.info("auto_reconnect_loop error: {}".format(e))
                time.sleep(5)
