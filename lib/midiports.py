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

    def _extract_descriptive_port_name(self, port_string):
        """Extract descriptive port name without the trailing client:port ID.
        
        Port strings can be in formats like:
        - "mio:mio MIDI 1 16:0" -> "mio:mio MIDI 1"
        - "MIDI USB-USB:MIDI USB-USB Puerto 1 20:0" -> "MIDI USB-USB:MIDI USB-USB Puerto 1"
        - "CASIO USB-MIDI:0" -> "CASIO USB-MIDI"
        """
        if not port_string or port_string == "default":
            return None
        
        # Remove the trailing "client:port" ID (format: "number:number")
        # This is typically the last space-separated part
        parts = port_string.split()
        if len(parts) > 1:
            # Check if the last part matches the pattern "number:number"
            last_part = parts[-1]
            if ':' in last_part:
                try:
                    # Try to parse as client:port (e.g., "16:0", "20:0")
                    client, port = last_part.split(':')
                    int(client)
                    int(port)
                    # If successful, remove this trailing part
                    return ' '.join(parts[:-1])
                except (ValueError, IndexError):
                    # Not a client:port format, return full string
                    pass
        
        # If no client:port ID found, return the original string
        # but remove any trailing ":number" from the last part
        if parts:
            last_part = parts[-1]
            if ':' in last_part and not last_part.count(':') > 1:
                # Simple format like "CASIO USB-MIDI:0"
                parts[-1] = last_part.split(':')[0]
                return ' '.join(parts)
        
        return port_string

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
        Monitor input_port and secondary_input_port by name.
        When either port is restored (absent -> present), call connectall() to restore the connection.
        """
        last_input_present = None  # None indicates first run
        last_secondary_present = None
        
        while self.monitor_running:
            try:
                input_names = mido.get_input_names()

                # Get configured ports
                input_port = self.usersettings.get_setting_value("input_port")
                secondary_input_port = self.usersettings.get_setting_value("secondary_input_port")
                
                # Extract descriptive port names (without client:port ID)
                input_descriptive_name = self._extract_descriptive_port_name(input_port) if input_port and input_port != "default" else None
                secondary_descriptive_name = self._extract_descriptive_port_name(secondary_input_port) if secondary_input_port and secondary_input_port != "default" else None

                # Check if ports are present by matching descriptive names
                input_present = False
                if input_descriptive_name:
                    input_present = any(input_descriptive_name in n for n in input_names)
                
                secondary_present = False
                if secondary_descriptive_name:
                    secondary_present = any(secondary_descriptive_name in n for n in input_names)

                # If either port transitions from absent -> present, call connectall()
                # Skip on first run (when last_*_present is None) to avoid false triggers
                input_restored = input_present and (last_input_present is False)
                secondary_restored = secondary_present and (last_secondary_present is False)
                
                if input_restored or secondary_restored:
                    logger.info("MIDI port restored. Triggering connectall()")
                    try:
                        self.connectall()
                        logger.info("connectall() completed after port restoration")
                    except Exception as e:
                        logger.info("connectall() raised: {}".format(e))

                last_input_present = input_present
                last_secondary_present = secondary_present
                time.sleep(3)
            except Exception as e:
                logger.info("auto_reconnect_loop error: {}".format(e))
                time.sleep(5)
