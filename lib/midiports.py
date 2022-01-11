import mido
import subprocess

class MidiPorts:
    def __init__(self, usersettings):
        self.usersettings = usersettings
        self.pending_queue = []
        self.last_activity = 0
        self.inport = None
        self.playport = None

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
        # Reconnect the input and playports on a connectall
        self.reconnect_ports()
        # Now connect all the remaining ports
        ports = subprocess.check_output(["aconnect", "-i", "-l"], text=True)
        port_list = []
        client = "0"
        for line in str(ports).splitlines():
            if line.startswith("client "):
                client = line[7:].split(":",2)[0]
                if client == "0" or "Through" in line:
                    client = "0"
            else:
                if client == "0" or line.startswith('\t'):
                    continue
                port = line.split()[0]
                port_list.append(client+":"+port)

        for source in port_list:
            for target in port_list:
                if source != target:
                    subprocess.call("sudo aconnect %s %s" % (source, target), shell=True)

    def add_instance(self, menu):
        self.menu = menu

    def change_port(self, port, portname):
        try:
            if port == "inport":
                if self.inport != None:
                    self.inport.close()
                    self.inport = None
                self.inport = mido.open_input(portname)
                self.usersettings.change_setting_value("input_port", portname)
            elif port == "playport":
                if self.playport != None:
                    self.playport.close()
                    self.playport = None
                self.playport = mido.open_output(portname)
                self.usersettings.change_setting_value("play_port", portname)
            self.menu.render_message("Changing " + port + " to:", portname, 1500)
        except:
            self.menu.render_message("Can't change " + port + " to:", portname, 1500)

    def reconnect_ports(self):
        try:
            if self.inport != None:
                self.inport.close()
                self.inport = None
            port = self.usersettings.get_setting_value("input_port")
            self.inport = mido.open_input(port)
        except:
            print("Can't reconnect input port: " + port)
        try:
            if self.playport != None:
                self.playport.close()
                self.playport = None
            port = self.usersettings.get_setting_value("play_port")
            self.playport = mido.open_output(port)
        except:
            print("Can't reconnect play port: " + port)