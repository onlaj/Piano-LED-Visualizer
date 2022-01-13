import mido
import subprocess
import connectall


class MidiPorts:
    def __init__(self, usersettings):
        self.usersettings = usersettings
        self.pending_queue = []
        self.last_activity = 0

        # checking if the input port was previously set by the user
        port = self.usersettings.get_setting_value("input_port")
        if port != "default":
            try:
                self.inport = mido.open_input(port)
                print("Inport loaded and set to " + port)
            except:
                print("Can't load input port: " + port)
        else:
            # if not, try to find the new midi port
            try:
                for port in mido.get_input_names():
                    if "Through" not in port and "RPi" not in port and "RtMidOut" not in port and "USB-USB" not in port:
                        self.inport = mido.open_input(port)
                        self.usersettings.change_setting_value("input_port", port)
                        print("Inport set to " + port)
                        break
            except:
                print("no input port")
        # checking if the play port was previously set by the user
        port = self.usersettings.get_setting_value("play_port")
        if port != "default":
            try:
                self.playport = mido.open_output(port)
                print("Playport loaded and set to " + port)
            except:
                print("Can't load input port: " + port)
        else:
            # if not, try to find the new midi port
            try:
                for port in mido.get_output_names():
                    if "Through" not in port and "RPi" not in port and "RtMidOut" not in port and "USB-USB" not in port:
                        self.playport = mido.open_output(port)
                        self.usersettings.change_setting_value("play_port", port)
                        print("Playport set to " + port)
                        break
            except:
                print("no play port")

        self.portname = "inport"

    def connectall(self):
        connectall.connectall()

    def add_instance(self, menu):
        self.menu = menu

    def change_port(self, port, portname):
        try:
            if port == "inport":
                self.inport = mido.open_input(portname)
                self.usersettings.change_setting_value("input_port", portname)
            elif port == "playport":
                self.playport = mido.open_output(portname)
                self.usersettings.change_setting_value("play_port", portname)
            self.menu.render_message("Changing " + port + " to:", portname, 1500)
        except:
            self.menu.render_message("Can't change " + port + " to:", portname, 1500)

    def reconnect_ports(self):
        try:
            port = self.usersettings.get_setting_value("input_port")
            self.inport = mido.open_input(port)
        except:
            print("Can't reconnect input port: " + port)
        try:
            port = self.usersettings.get_setting_value("play_port")
            self.playport = mido.open_output(port)
        except:
            print("Can't reconnect play port: " + port)