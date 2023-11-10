import mido
from lib import connectall
import time
from collections import deque
from lib.log_setup import logger

class MidiPorts:
    def __init__(self, usersettings):
        self.usersettings = usersettings
        # midi queues will contain a tuple (midi_msg, timestamp)
        self.midifile_queue = deque()
        self.midi_queue = deque()
        self.last_activity = 0
        self.inport = None
        self.playport = None
        self.midipending = None

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

        # checking if the input port was previously set by the user
        port = self.usersettings.get_setting_value("input_port")
        if port != "default":
            try:
                self.inport = mido.open_input(port, callback=self.msg_callback)
                logger.info("Inport loaded and set to " + port)
            except:
                logger.info("Can't load input port: " + port)
        else:
            # if not, try to find the new midi port
            try:
                for port in mido.get_input_names():
                    if "Through" not in port and "RPi" not in port and "RtMidOut" not in port and "USB-USB" not in port:
                        self.inport = mido.open_input(port, callback=self.msg_callback)
                        self.usersettings.change_setting_value("input_port", port)
                        logger.info("Inport set to " + port)
                        break
            except:
                logger.info("no input port")
        # checking if the play port was previously set by the user
        port = self.usersettings.get_setting_value("play_port")
        if port != "default":
            try:
                self.playport = mido.open_output(port)
                logger.info("Playport loaded and set to " + port)
            except:
                logger.info("Can't load input port: " + port)
        else:
            # if not, try to find the new midi port
            try:
                for port in mido.get_output_names():
                    if "Through" not in port and "RPi" not in port and "RtMidOut" not in port and "USB-USB" not in port:
                        self.playport = mido.open_output(port)
                        self.usersettings.change_setting_value("play_port", port)
                        logger.info("Playport set to " + port)
                        break
            except:
                logger.info("no play port")

        self.portname = "inport"

    def connectall(self):
        # Reconnect the input and playports on a connectall
        self.reconnect_ports()
        # Now connect all the remaining ports
        connectall.connectall()

    def add_instance(self, menu):
        self.menu = menu

    def change_port(self, port, portname):
        try:
            destroy_old = None
            if port == "inport":
                destory_old = self.inport
                self.inport = mido.open_input(portname, callback=self.msg_callback)
                self.usersettings.change_setting_value("input_port", portname)
            elif port == "playport":
                destory_old = self.playport
                self.playport = mido.open_output(portname)
                self.usersettings.change_setting_value("play_port", portname)
            self.menu.render_message("Changing " + port + " to:", portname, 1500)
            if destroy_old is not None:
                destory_old.close()
            self.menu.show()
        except:
            self.menu.render_message("Can't change " + port + " to:", portname, 1500)
            self.menu.show()

    def reconnect_ports(self):
        try:
            destroy_old = self.inport
            port = self.usersettings.get_setting_value("input_port")
            self.inport = mido.open_input(port, callback=self.msg_callback)
            if destroy_old is not None:
                time.sleep(0.002)
                destroy_old.close()
        except:
            logger.info("Can't reconnect input port: " + port)
        try:
            destroy_old = self.playport
            port = self.usersettings.get_setting_value("play_port")
            self.playport = mido.open_output(port)
            if destroy_old is not None:
                time.sleep(0.002)
                destroy_old.close()
        except:
            logger.info("Can't reconnect play port: " + port)

    def msg_callback(self, msg):
        self.midi_queue.append((msg, time.perf_counter()))
