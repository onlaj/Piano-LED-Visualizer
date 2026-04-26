import time

from lib import connectall


class MidiConnectionManager:
    def __init__(self, midiports):
        self.midiports = midiports

    def reconnect_ports(self, force=False):
        self.midiports._refresh_port_cache()
        changed_input = self.midiports._reconnect_input(force=force)
        changed_output = self.midiports._reconnect_output(force=force)
        if force or changed_input or changed_output:
            self.midiports.reconnect_count += 1
            self.midiports.last_reconnect_time = time.time()
        return changed_input or changed_output

    def connectall(self):
        self.reconnect_ports(force=False)
        connectall.connectall(self.midiports.usersettings)

    def ports_need_reconnect(self):
        self.midiports._refresh_port_cache()
        available_inputs = self.midiports._get_cached_input_names()
        available_outputs = self.midiports._get_cached_output_names()

        requested_input = self.midiports.usersettings.get_setting_value("input_port")
        requested_output = self.midiports.usersettings.get_setting_value("play_port")

        input_resolution = self.midiports._resolve_input_target(requested_input, available_inputs)
        output_resolution = self.midiports._resolve_output_target(
            requested_output,
            available_outputs,
            available_inputs=available_inputs,
        )

        selected_input = self.midiports._resolve_selected_port(input_resolution)
        selected_output = self.midiports._resolve_selected_port(output_resolution)

        if selected_input != self.midiports.actual_input_port:
            return True
        if selected_output != self.midiports.actual_play_port:
            return True
        if selected_input and not self.midiports.port_is_present(self.midiports.actual_input_port, available_inputs):
            return True
        if selected_output and not self.midiports.port_is_present(self.midiports.actual_play_port, available_outputs):
            return True
        return False
